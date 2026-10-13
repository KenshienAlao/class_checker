"""Shared pytest fixtures.

Database integration tests run against a dedicated schema inside a dedicated
``{POSTGRES_DB}_test`` database. Only that schema is created and dropped, so
tables that may exist elsewhere in the database are never touched. The schema is
only created after the connection is positively verified to be the dedicated
database; the development database and Supabase are never modified. Setup skips
locally when PostgreSQL is unavailable but fails in CI, so CI cannot pass
without exercising the database.
"""

import os
from collections.abc import Callable, Iterator
from typing import NoReturn
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    create_session_token,
    generate_csrf_token,
)
from app.main import app
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.classroom_service import ClassroomService
from app.services.student_service import StudentService

# A project-owned schema used only by tests. Cleaning up this schema cannot
# remove unrelated tables that happen to live in the same database.
_TEST_SCHEMA = "class_checker_test"

_ENV_KEYS = (
    "APP_NAME",
    "APP_VERSION",
    "ENVIRONMENT",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_URL",
    "SESSION_SECRET",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove environment overrides so config tests are deterministic."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _running_in_ci() -> bool:
    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _skip_or_fail(reason: str) -> NoReturn:
    """Skip when running locally, but fail the suite when running in CI."""
    if _running_in_ci():
        pytest.fail(reason)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    """A session-scoped engine bound to the dedicated test database and schema."""
    settings = get_settings()
    if settings.uses_supabase_database:
        pytest.skip("refusing to run integration tests against Supabase")

    test_db = f"{settings.postgres_db}_test"
    if test_db == settings.postgres_db:
        pytest.fail("refusing to run against the development database")

    base_url = settings.database_url.rsplit("/", 1)[0]
    admin_engine = create_engine(f"{base_url}/postgres", isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_db},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{test_db}"'))
    except OperationalError as err:
        _skip_or_fail(f"PostgreSQL is unavailable: {err}")
    finally:
        admin_engine.dispose()

    engine = create_engine(f"{base_url}/{test_db}", poolclass=NullPool).execution_options(
        schema_translate_map={None: _TEST_SCHEMA}
    )
    try:
        with engine.connect() as connection:
            current_db = connection.execute(text("SELECT current_database()")).scalar_one()
    except OperationalError as err:
        engine.dispose()
        _skip_or_fail(f"test database is unreachable: {err}")

    if current_db != test_db:
        engine.dispose()
        pytest.fail(f"refusing to modify unexpected database: {current_db}")

    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_TEST_SCHEMA}"'))
        Base.metadata.create_all(connection)

    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{_TEST_SCHEMA}" CASCADE'))
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Iterator[Session]:
    """A session enclosed in a transaction that is rolled back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """A test client whose routes share the guarded rollback transaction."""
    overrides = app.dependency_overrides

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        overrides.pop(get_db, None)


@pytest.fixture
def make_user(db_session: Session) -> Callable[[], User]:
    """Create a user row inside the guarded transaction."""

    def create() -> User:
        user = User(
            id=uuid4(),
            name="Owner",
            email=f"{uuid4()}@example.com",
            password="n/a",
        )
        db_session.add(user)
        db_session.flush()
        return user

    return create


@pytest.fixture
def auth_headers() -> Callable[[UUID], dict[str, str]]:
    """Return matching session + CSRF cookies and the CSRF header."""

    def make(user_id: UUID) -> dict[str, str]:
        session_token = create_session_token(user_id)
        csrf_token = generate_csrf_token()
        return {
            "Cookie": f"{SESSION_COOKIE_NAME}={session_token}; {CSRF_COOKIE_NAME}={csrf_token}",
            "X-CSRF-Token": csrf_token,
        }

    return make


@pytest.fixture
def make_classroom(db_session: Session) -> Callable[[UUID, str], Classroom]:
    """Create a classroom through the service, not the API."""

    def create(owner_id: UUID, name: str) -> Classroom:
        return ClassroomService(ClassroomRepository(db_session)).create(owner_id, name)

    return create


@pytest.fixture
def make_student(db_session: Session) -> Callable[[int, UUID, str, str, str | None], Student]:
    """Create a student through the service, not the API."""

    def create(
        classroom_id: int,
        owner_id: UUID,
        student_id: str,
        full_name: str,
        program: str | None = None,
    ) -> Student:
        return StudentService(
            StudentRepository(db_session),
            ClassroomRepository(db_session),
        ).create(
            classroom_id,
            owner_id,
            student_id=student_id,
            full_name=full_name,
            program=program,
        )

    return create
