"""Session tokens (signed JWT), CSRF tokens, and cookie plumbing.

The session is an HttpOnly ``session`` cookie holding a short-lived JWT (HS256,
signed with ``SESSION_SECRET``). CSRF uses the double-submit pattern: a readable
``csrf`` cookie whose value must be echoed in the ``X-CSRF-Token`` header for any
state-changing request that carries a session cookie.
"""

import secrets
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings, get_settings, normalize_origin

SESSION_COOKIE_NAME = "session"
CSRF_COOKIE_NAME = "csrf"
CSRF_HEADER = "x-csrf-token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_ALGORITHM = "HS256"


class SessionTokenError(Exception):
    """Raised when a session token is missing, invalid, or expired."""


def create_session_token(user_id: UUID, settings: Settings | None = None) -> str:
    """Return a signed JWT for ``user_id`` valid for the configured lifetime.

    The ``jti`` nonce makes every token unique even within the same second,
    so refresh always rotates to a visibly fresh session.
    """
    settings = settings or get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.session_ttl_minutes),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.session_secret.get_secret_value(), algorithm=_ALGORITHM)


def decode_session_token(token: str, settings: Settings | None = None) -> UUID:
    """Validate ``token`` and return the user ID it was issued to."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.session_secret.get_secret_value(),
            algorithms=[_ALGORITHM],
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as err:
        raise SessionTokenError from err


def generate_csrf_token() -> str:
    """Return an unguessable CSRF token."""
    return secrets.token_urlsafe(32)


def _header_value(headers: Mapping[str, str], name: str) -> str | None:
    """Return an HTTP header value without depending on key case."""
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def trusted_browser_origin(headers: Mapping[str, str], settings: Settings | None = None) -> bool:
    """Return whether an Origin header belongs to the configured trusted set.

    Missing, malformed, or ``null`` Origins are trusted only in the effective
    compatibility mode used for local non-browser tests. Untrusted explicit
    Origins are rejected everywhere.
    """
    settings = settings or get_settings()
    origin = _header_value(headers, "Origin")
    if origin is None:
        return settings.environment.lower() != "production"
    try:
        normalized = normalize_origin(origin)
    except ValueError:
        return False
    return normalized in settings.trusted_origin_set


def origin_request_allowed(headers: Mapping[str, str], settings: Settings | None = None) -> bool:
    """Return whether a request's Origin can be served for this deployment."""
    return trusted_browser_origin(headers, settings)


def csrf_and_origin_request_allowed(
    cookies: Mapping[str, str],
    headers: Mapping[str, str],
    method: str,
    settings: Settings | None = None,
) -> bool:
    """Double-submit CSRF check with explicit browser-origin enforcement."""
    if method in _SAFE_METHODS or cookies.get(SESSION_COOKIE_NAME) is None:
        return True

    effective_settings = settings or get_settings()
    if not trusted_browser_origin(headers, effective_settings):
        return False

    token = cookies.get(CSRF_COOKIE_NAME)
    if token is None:
        return False
    return secrets.compare_digest(token, headers.get(CSRF_HEADER, ""))


csrf_request_allowed = csrf_and_origin_request_allowed  # compatibility alias
origin_allowed = trusted_browser_origin  # compatibility alias


def issue_session_cookies(
    response: Response, user_id: UUID, settings: Settings | None = None
) -> None:
    """Set the JWT session cookie and a matching CSRF cookie on ``response``."""
    settings = settings or get_settings()
    max_age = settings.session_ttl_minutes * 60
    secure = settings.environment.lower() == "production"
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(user_id, settings),
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        generate_csrf_token(),
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Reject unsafe browser requests without CSRF and trusted-Origin evidence."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        method = request.method.upper()
        cookies = dict(request.cookies)
        headers = dict(request.headers)

        if method not in _SAFE_METHODS and SESSION_COOKIE_NAME in cookies:
            if not trusted_browser_origin(headers, settings):
                return JSONResponse({"detail": "Request origin is not allowed"}, status_code=403)
            token = cookies.get(CSRF_COOKIE_NAME)
            if token is None or not secrets.compare_digest(token, headers.get(CSRF_HEADER, "")):
                return JSONResponse({"detail": "CSRF verification failed"}, status_code=403)
        return await call_next(request)
