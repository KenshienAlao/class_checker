"""Tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core import database
from app.main import app

client = TestClient(app)


def _db_reachable() -> bool:
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        return False
    return True


def test_health_returns_ok_when_database_is_reachable() -> None:
    if not _db_reachable():
        pytest.skip("local PostgreSQL is not reachable")
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "reachable"


def test_health_reports_environment() -> None:
    response = client.get("/api/health")

    assert response.json()["environment"] == "development"


def test_health_reports_database_down_as_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenConnection:
        def connect(self) -> None:
            raise OperationalError("SELECT 1", None, ConnectionRefusedError("down"))

    monkeypatch.setattr("app.core.database.engine", _BrokenConnection())

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unreachable"
