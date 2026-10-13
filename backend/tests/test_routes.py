"""Safety audit for the exposed API surface.

Every ``/api`` route must be either explicitly public (listed in
``PUBLIC_PATHS``) or reject requests without a session cookie with 401. Adding a
new protected endpoint without wiring the session dependency fails this audit.
"""

from typing import Annotated, Any, cast

import pytest
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.core.security import CSRFProtectionMiddleware
from app.main import app, create_app

# The only endpoints reachable without a session cookie. Logout is public on
# purpose: clearing cookies is harmless and must never be blocked by a dying
# session.
PUBLIC_PATHS = {
    ("/api/health", "GET"),
    ("/api/auth/register", "POST"),
    ("/api/auth/login", "POST"),
    ("/api/auth/logout", "POST"),
}

client = TestClient(app)


def _api_routes() -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api")
    ]


def test_every_api_route_is_public_whitelisted_or_session_protected() -> None:
    routes = _api_routes()
    assert routes, "no API routes found; audit would be vacuous"

    violations: list[tuple[str, str, int]] = []
    for route in routes:
        for method in route.methods or set():
            if (route.path, method) in PUBLIC_PATHS:
                continue
            response = client.request(method, route.path)
            if response.status_code != 401:
                violations.append((route.path, method, response.status_code))

    assert violations == []


def test_public_routes_do_not_require_a_session() -> None:
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/auth/register", json={}).status_code == 422
    assert client.post("/api/auth/login", json={}).status_code == 422
    assert client.post("/api/auth/logout").status_code == 204


def test_csrf_and_cors_middleware_are_registered() -> None:
    # Middleware.cls is typed as a generic factory; cast to inspect the class.
    classes = [cast(Any, middleware.cls) for middleware in app.user_middleware]

    assert CSRFProtectionMiddleware in classes
    assert CORSMiddleware in classes


def test_registration_validation_error_uses_detail_array() -> None:
    client = TestClient(app)

    response = client.post("/api/auth/register", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert all(set(item) >= {"loc", "msg", "type"} for item in detail)


def test_development_api_documentation_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    application = create_app()
    client = TestClient(application)
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_production_api_documentation_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production_settings = Settings(
        environment="production",
        allowed_origins="https://app.example.com",
        session_secret="A" * 32,
        _env_file=None,
    )
    monkeypatch.setattr("app.main.get_settings", lambda: production_settings)
    application = create_app()
    client = TestClient(application)
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_cors_never_uses_wildcard_with_credentials() -> None:
    assert "*" not in get_settings().allowed_origin_list


def test_protected_route_without_session_returns_401() -> None:
    protected = FastAPI()

    @protected.get("/private")
    def private(user: Annotated[object, Depends(get_current_user)]) -> dict[str, str]:
        return {"user": str(user)}

    response = TestClient(protected).get("/private")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_protected_route_rejects_tampered_session() -> None:
    protected = FastAPI()

    @protected.get("/private")
    def private(user: Annotated[object, Depends(get_current_user)]) -> dict[str, str]:
        return {"user": str(user)}

    test_client = TestClient(protected)
    test_client.cookies.set("session", "not-a-real-jwt")

    response = test_client.get("/private")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired session"
