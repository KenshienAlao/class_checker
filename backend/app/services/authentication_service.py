"""Authentication use cases. Credentials are stored as argon2 hashes only."""

from uuid import uuid4

from fastapi import HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.repositories.authentication_repository import AuthenticationRepository
from app.schemas.authentication_schema import Login, Register

_password_hasher = PasswordHash.recommended()


class AuthenticationService:
    """Auth use cases; plaintext passwords never outlive the request."""

    def __init__(self, repository: AuthenticationRepository) -> None:
        self.repository = repository

    def register(self, data: Register) -> User:
        """Create a profile whose ``password`` holds an argon2 hash of the input."""
        if self.repository.exist_by_email(data.email):
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

        user = User(
            id=uuid4(),
            name=data.name,
            email=data.email,
            password=_password_hasher.hash(data.password),
        )

        try:
            return self.repository.create_user(user)
        except IntegrityError as exc:
            # The pre-check is only advisory; the database unique constraint is
            # the final guard against concurrent registrations.
            self.repository.db.rollback()

            if not self._is_duplicate_email_race(exc):
                raise

            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Email already registered"
            ) from None

    @staticmethod
    def _is_duplicate_email_race(exc: IntegrityError) -> bool:
        """Identify PostgreSQL's ``users.email`` unique constraint.

        The check uses driver diagnostics, not human-readable error text.
        """
        orig = exc.orig
        diagnostic = getattr(orig, "diag", None)
        constraint_name = getattr(orig, "constraint_name", None)

        if constraint_name is None and diagnostic is not None:
            constraint_name = getattr(diagnostic, "constraint_name", None)

        return constraint_name == "ix_users_email"

    def login(self, data: Login) -> User:
        """Return the profile when credentials match, else a generic 401.

        The same message for an unknown email and a wrong password prevents
        user enumeration.
        """
        user = self.repository.get_user_by_email(data.email)
        if user is None or not _password_hasher.verify(data.password, user.password):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        return user
