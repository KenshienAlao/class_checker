"""HTTP middleware for the application's in-process rate limiter."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.rate_limit import RateLimitPolicy, get_rate_limiter

LOGGER = logging.getLogger(__name__)


def _client_ip(request: Request, trusted_proxies: frozenset[str]) -> str:
    direct_peer = request.client.host if request.client is not None else "unknown"
    if direct_peer not in trusted_proxies:
        return direct_peer

    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if not forwarded_for:
        return direct_peer
    first = forwarded_for.split(",", 1)[0].strip()
    return first or direct_peer


async def _extract_account_identifier(request: Request) -> str | None:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(body, dict):
        return None
    value = body.get("email")
    if not isinstance(value, str):
        return None
    return value.strip().lower()


def _policy_for(settings: Any, path: str, method: str) -> RateLimitPolicy:
    window = settings.rate_limit_window_seconds
    if method in {"POST"} and path.startswith("/api/auth/register"):
        return RateLimitPolicy(
            name="authentication-register",
            client_limit=settings.rate_limit_auth_client_requests,
            window_seconds=window,
            account_limit=settings.rate_limit_auth_account_requests,
            account_field="email",
        )
    if method in {"POST", "GET", "PATCH"} and path.startswith("/api/auth/login"):
        return RateLimitPolicy(
            name="authentication-login",
            client_limit=settings.rate_limit_auth_client_requests,
            window_seconds=window,
            account_limit=settings.rate_limit_auth_account_requests,
            account_field="email",
        )
    if method in {"POST", "PATCH"} and path.startswith("/api/students/import"):
        return RateLimitPolicy(
            name="student-import",
            client_limit=settings.rate_limit_import_requests,
            window_seconds=window,
        )
    if method in {"POST"} and path.startswith("/api/attendance-sessions"):
        return RateLimitPolicy(
            name="attendance-writing",
            client_limit=settings.rate_limit_attendance_session_requests,
            window_seconds=window,
        )
    if method in {"POST", "PATCH"} and path.startswith("/api/classroom"):
        # conservative for classroom creation;
        pass
    if "export" in path:
        return RateLimitPolicy(
            name="data-export",
            client_limit=settings.rate_limit_export_requests,
            window_seconds=window,
        )
    return RateLimitPolicy(
        name="generic-client",
        client_limit=settings.rate_limit_generic_requests,
        window_seconds=window,
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        if not settings.rate_limiting_enabled:
            return await call_next(request)

        policy = _policy_for(settings, request.url.path, request.method.upper())
        account_identifier = None
        if policy.name.startswith("authentication-"):
            account_identifier = await _extract_account_identifier(request)

        client_ip = _client_ip(request, settings.trusted_proxy_ip_set)
        try:
            result = get_rate_limiter().check_with_account(
                policy,
                client_ip,
                account_identifier,
            )
        except Exception:  # noqa: BLE001
            LOGGER.exception("rate limiter failed")
            return JSONResponse(
                status_code=503,
                content={"detail": "Rate limiter unavailable"},
            )

        if not result.allowed:
            headers = {"Retry-After": str(result.retry_after)}
            return JSONResponse(
                status_code=result.status_code,
                content={"detail": result.detail},
                headers=headers,
            )

        return await call_next(request)
