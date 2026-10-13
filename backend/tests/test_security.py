"""Tests for session tokens and CSRF protection (no database required)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER,
    SESSION_COOKIE_NAME,
    CSRFProtectionMiddleware,
    SessionTokenError,
    create_session_token,
    csrf_request_allowed,
    decode_session_token,
    generate_csrf_token,
    issue_session_cookies,
    trusted_browser_origin,
)
from app.main import app


def test_session_token_round_trip() -> None:
    user_id = uuid4()
    token = create_session_token(user_id)

    assert decode_session_token(token) == user_id


def test_tampered_session_token_is_rejected() -> None:
    token = create_session_token(uuid4())

    with pytest.raises(SessionTokenError):
        decode_session_token(token[:-3] + "xxx")


def test_expired_session_token_is_rejected() -> None:
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode(
        {"sub": str(uuid4()), "iat": past - timedelta(minutes=1), "exp": past},
        settings.session_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(SessionTokenError):
        decode_session_token(expired)


@pytest.mark.parametrize(
    "method",
    ["GET", "HEAD", "OPTIONS"],
)
def test_safe_methods_always_pass_csrf(method: str) -> None:
    assert csrf_request_allowed({"session": "t"}, {}, method)


def test_unsafe_method_without_session_cookie_passes() -> None:
    assert csrf_request_allowed({}, {}, "POST")


def test_unsafe_method_with_session_requires_matching_token() -> None:
    token = generate_csrf_token()
    cookies = {SESSION_COOKIE_NAME: "t", CSRF_COOKIE_NAME: token}

    assert csrf_request_allowed(cookies, {CSRF_HEADER: token}, "POST")
    assert not csrf_request_allowed(cookies, {}, "POST")
    assert not csrf_request_allowed(cookies, {CSRF_HEADER: generate_csrf_token()}, "POST")


def _csrf_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFProtectionMiddleware)

    @app.post("/state")
    def state() -> dict[str, str]:
        return {"ok": "yes"}

    return app


def test_csrf_middleware_skips_tokeless_requests() -> None:
    assert TestClient(_csrf_app()).post("/state", json={}).status_code == 200


def test_csrf_middleware_blocks_session_without_header() -> None:
    client = TestClient(_csrf_app())
    client.cookies.set(SESSION_COOKIE_NAME, "junk")

    assert client.post("/state").status_code == 403


def test_csrf_middleware_allows_matching_token() -> None:
    client = TestClient(_csrf_app())
    client.cookies.set(SESSION_COOKIE_NAME, "junk")
    token = generate_csrf_token()
    client.cookies.set(CSRF_COOKIE_NAME, token)

    assert client.post("/state", headers={CSRF_HEADER: token}).status_code == 200


def test_csrf_middleware_rejects_mismatched_token() -> None:
    client = TestClient(_csrf_app())
    client.cookies.set(SESSION_COOKIE_NAME, "junk")
    client.cookies.set(CSRF_COOKIE_NAME, generate_csrf_token())

    response = client.post("/state", headers={CSRF_HEADER: generate_csrf_token()})

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF verification failed"}


def test_custom_secret_token_round_trips() -> None:
    secret = "A" * 32
    settings = Settings(
        environment="production",
        allowed_origins="https://app.example.com",
        session_secret=secret,
        _env_file=None,
    )
    user_id = uuid4()
    token = create_session_token(user_id, settings)

    assert decode_session_token(token, settings) == user_id


def test_token_exp_matches_session_ttl() -> None:
    settings = get_settings()
    user_id = uuid4()
    token = create_session_token(user_id, settings)
    payload = jwt.decode(
        token,
        settings.session_secret.get_secret_value(),
        algorithms=["HS256"],
        options={"verify_exp": False},
    )

    assert payload["exp"] - payload["iat"] == settings.session_ttl_minutes * 60


def test_session_cookie_has_required_attributes() -> None:
    settings = Settings(
        environment="production",
        session_secret="b" * 32,
        allowed_origins="https://app.example.com",
        _env_file=None,
    )
    response = Response()
    issue_session_cookies(response, uuid4(), settings)

    set_cookie = "\n".join(response.headers.getlist("set-cookie"))
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "Max-Age=86400" in set_cookie
    assert "Path=/" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_session_cookies_are_invalidated_by_secret_rotation() -> None:
    user_id = uuid4()
    old_secret = "c" * 32
    new_secret = "d" * 32
    old_settings = Settings(
        environment="production",
        allowed_origins="https://app.example.com",
        session_secret=old_secret,
        _env_file=None,
    )
    new_settings = Settings(
        environment="production",
        allowed_origins="https://app.example.com",
        session_secret=new_secret,
        _env_file=None,
    )

    old_token = create_session_token(user_id, old_settings)
    assert decode_session_token(old_token, old_settings) == user_id

    with pytest.raises(SessionTokenError):
        decode_session_token(old_token, new_settings)

    new_token = create_session_token(user_id, new_settings)
    assert decode_session_token(new_token, new_settings) == user_id


def test_trusted_browser_origin_rejects_missing_and_untrusted_origins() -> None:
    settings = Settings(
        environment="production",
        allowed_origins="https://app.example.com",
        session_secret="A" * 32,
        _env_file=None,
    )

    assert trusted_browser_origin({"Origin": "https://app.example.com"}, settings)
    assert not trusted_browser_origin({"Origin": "https://evil.example.com"}, settings)
    assert not trusted_browser_origin({"Origin": "null"}, settings)
    assert not trusted_browser_origin({"Origin": "https://app.example.com/path"}, settings)
    assert not trusted_browser_origin({}, settings)


def test_csrf_middleware_rejects_untrusted_origin() -> None:
    client = TestClient(app)
    token = generate_csrf_token()
    credentials = {SESSION_COOKIE_NAME: "junk", CSRF_COOKIE_NAME: token}

    for key, value in credentials.items():
        client.cookies.set(key, value)

    response = client.post(
        "/api/classrooms/1/students",
        headers={"X-CSRF-Token": token, "Origin": "https://evil.example.com"},
        json={},
    )

    assert response.status_code == 403


def test_cors_preflight_allows_trusted_origin() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/auth/register",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "origin" in response.headers.get("vary", "").lower()


def test_cors_headers_on_trusted_origin_response() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/auth/me",
        headers={"Origin": "http://localhost:3000", "Cookie": "session=junk"},
    )

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"
