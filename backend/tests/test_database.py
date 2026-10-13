"""Tests for the SQLAlchemy engine and session dependency."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, build_session_factory, engine, get_db


def test_engine_uses_psycopg_driver() -> None:
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"


def test_session_factory_returns_sessions() -> None:
    session = SessionLocal()

    try:
        assert isinstance(session, Session)
    finally:
        session.close()


def test_build_session_factory_binds_engine() -> None:
    factory = build_session_factory(engine)
    session = factory()

    try:
        assert session.get_bind() is engine
    finally:
        session.close()


def test_get_db_yields_session_and_closes() -> None:
    dependency = get_db()
    session = next(dependency)

    assert isinstance(session, Session)

    dependency.close()


def test_local_database_accepts_connections() -> None:
    """Integration check against the Docker Compose PostgreSQL instance.

    Skipped when the local database is not reachable (for example in CI).
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
    except OperationalError:
        pytest.skip("local PostgreSQL is not reachable")

    assert result == 1
