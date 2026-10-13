"""Unit tests for ``AuthenticationService`` (no database required)."""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.authentication_repository import AuthenticationRepository
from app.schemas.authentication_schema import Login, Register
from app.services.authentication_service import AuthenticationService


class FakeRepository(AuthenticationRepository):
    """In-memory stand-in for the persistence layer."""

    def __init__(self) -> None:
        self.users_by_email: dict[str, User] = {}

    def create_user(self, user: User) -> User:
        self.users_by_email[user.email] = user
        return user

    def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email)

    def exist_by_email(self, email: str) -> bool:
        return email in self.users_by_email


def _register(service: AuthenticationService, email: str = "jane@example.com") -> User:
    return service.register(
        Register(
            name="Jane Doe",
            email=email,
            password="Sup3r!Secret",
            confirm="Sup3r!Secret",
        )
    )


def test_register_never_stores_plaintext_password() -> None:
    fake = FakeRepository()
    service = AuthenticationService(fake)
    plaintext = "Sup3r!Secret"

    user = _register(service)

    assert len(fake.users_by_email) == 1
    assert user.password != plaintext
    assert user.password.startswith("$argon2")
    assert PasswordHash.recommended().verify(plaintext, user.password)
    assert isinstance(user.id, UUID)
    assert user.name == "Jane Doe"
    assert user.email == "jane@example.com"


def test_register_rejects_duplicate_email() -> None:
    fake = FakeRepository()
    service = AuthenticationService(fake)
    _register(service)

    with pytest.raises(HTTPException) as exc:
        _register(service)

    assert exc.value.status_code == 409
    assert len(fake.users_by_email) == 1


def test_login_succeeds_with_correct_password() -> None:
    fake = FakeRepository()
    service = AuthenticationService(fake)
    _register(service)

    user = service.login(Login(email="jane@example.com", password="Sup3r!Secret"))

    assert user.email == "jane@example.com"


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("jane@example.com", "Wrong!Pass1"),
        ("nobody@example.com", "Sup3r!Secret"),
    ],
)
def test_login_rejects_bad_credentials(email: str, password: str) -> None:
    fake = FakeRepository()
    service = AuthenticationService(fake)
    _register(service)

    with pytest.raises(HTTPException) as exc:
        service.login(Login(email=email, password=password))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid credentials"


class _DatabaseSession:
    def __init__(self) -> None:
        self.rollback_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1


class _RacingRepository(FakeRepository):
    db: _DatabaseSession  # type: ignore[assignment]

    def __init__(self, error: IntegrityError) -> None:
        super().__init__()
        self.db = _DatabaseSession()
        self._error = error

    def create_user(self, user: User) -> User:
        raise self._error


def _duplicate_email_integrity_error(constraint_name: str) -> IntegrityError:
    from typing import cast

    exception = IntegrityError("insert duplicate", {}, RuntimeError("constraint"))
    diagnostic = SimpleNamespace(constraint_name=constraint_name)
    orig = SimpleNamespace(diag=diagnostic)
    exception.orig = cast(Exception, orig)
    return exception


def test_register_translates_duplicate_email_race() -> None:
    error = _duplicate_email_integrity_error("ix_users_email")
    repository = _RacingRepository(error)
    repository.exist_by_email = lambda email: False  # type: ignore[method-assign]
    service = AuthenticationService(repository)

    with pytest.raises(HTTPException) as exc:
        _register(service, email="race@example.com")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Email already registered"
    assert repository.db.rollback_calls == 1


def test_register_re_raises_unrelated_integrity_error() -> None:
    error = _duplicate_email_integrity_error("users_pkey")
    repository = _RacingRepository(error)
    repository.exist_by_email = lambda email: False  # type: ignore[method-assign]
    service = AuthenticationService(repository)

    with pytest.raises(IntegrityError) as exc:
        _register(service, email="race@example.com")

    assert exc.value is error
    assert repository.db.rollback_calls == 1


def test_register_duplicate_email_race_rolls_back_and_leaves_session_usable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.repositories.authentication_repository import AuthenticationRepository

    repository = AuthenticationRepository(db_session)
    repository.create_user(
        User(
            id=uuid4(),
            name="Existing Race User",
            email="race@example.com",
            password="stored-hash",
        )
    )

    monkeypatch.setattr(repository, "exist_by_email", lambda email: False)

    service = AuthenticationService(repository)

    with pytest.raises(HTTPException) as exc:
        service.register(
            Register(
                name="Race User",
                email="race@example.com",
                password="Sup3r!Secret",
                confirm="Sup3r!Secret",
            )
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "Email already registered"

    assert len(db_session.query(User).filter(User.email == "race@example.com").all()) == 1

    other = service.register(
        Register(
            name="Later User",
            email="later@example.com",
            password="Sup3r!Secret",
            confirm="Sup3r!Secret",
        )
    )

    assert other.email == "later@example.com"
