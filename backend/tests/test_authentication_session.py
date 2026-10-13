"""Tests for the session-backed endpoints: /me, /refresh, /logout."""

from collections.abc import Iterator
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal, engine
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    create_session_token,
    decode_session_token,
    generate_csrf_token,
)
from app.main import app
from app.models.user import User


def _db_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        return False
    return True


def _cookie_value(headers: httpx.Headers, name: str) -> str:
    """Return the value of the named cookie from a Set-Cookie response."""
    for header in headers.get_list("set-cookie") or []:
        key, _, value = header.partition("=")
        if key.strip() == name:
            return value.split(";", 1)[0].strip('"')
    return ""


@pytest.fixture
def user_id() -> Iterator[UUID]:
    if not _db_reachable():
        pytest.skip("local PostgreSQL is not reachable")
    user = User(
        id=uuid4(),
        name="Session Checker",
        email=f"session-{uuid4().hex[:8]}@example.com",
        password=PasswordHash.recommended().hash("Sup3r!Secret"),
    )
    with SessionLocal() as db:
        db.add(user)
        db.commit()
        user_id_value = user.id
    yield user_id_value
    with SessionLocal() as db:
        existing = db.get(User, user_id_value)
        if existing is not None:
            db.delete(existing)
            db.commit()


def _auth_headers(session_token: str, csrf_token: str) -> dict[str, str]:
    return {
        "Cookie": f"{SESSION_COOKIE_NAME}={session_token}; {CSRF_COOKIE_NAME}={csrf_token}",
        "X-CSRF-Token": csrf_token,
    }


def test_me_without_session_returns_401() -> None:
    response = TestClient(app).get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_me_returns_profile_for_session_user(user_id: UUID) -> None:
    session_token = create_session_token(user_id)

    response = TestClient(app).get(
        "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={session_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["email"].startswith("session-")
    assert "password" not in body


def test_refresh_without_session_returns_401() -> None:
    assert TestClient(app).post("/api/auth/refresh").status_code == 401


def test_refresh_reissues_fresh_cookies(user_id: UUID) -> None:
    old_session_token = create_session_token(user_id)
    old_csrf_token = generate_csrf_token()

    response = TestClient(app).post(
        "/api/auth/refresh", headers=_auth_headers(old_session_token, old_csrf_token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    new_session_token = _cookie_value(response.headers, SESSION_COOKIE_NAME)
    new_csrf_token = _cookie_value(response.headers, CSRF_COOKIE_NAME)
    assert new_session_token and new_session_token != old_session_token
    assert new_csrf_token and new_csrf_token != old_csrf_token
    assert decode_session_token(new_session_token) == user_id


def test_logout_is_public_without_session() -> None:
    response = TestClient(app).post("/api/auth/logout")

    assert response.status_code == 204


def test_logout_instructs_browser_to_drop_cookies(user_id: UUID) -> None:
    session_token = create_session_token(user_id)
    csrf_token = generate_csrf_token()
    test_client = TestClient(app)
    assert (
        test_client.get(
            "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={session_token}"}
        ).status_code
        == 200
    )

    response = test_client.post(
        "/api/auth/logout", headers=_auth_headers(session_token, csrf_token)
    )

    assert response.status_code == 204
    assert _cookie_value(response.headers, SESSION_COOKIE_NAME) == ""
    assert _cookie_value(response.headers, CSRF_COOKIE_NAME) == ""
    assert any("Max-Age=0" in header for header in response.headers.get_list("set-cookie") or [])
