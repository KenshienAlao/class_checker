"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.controllers.attendance_controller import router as attendance_router
from app.controllers.authentication_controller import router as authentication_router
from app.controllers.classroom_controller import router as classroom_router
from app.controllers.student_controller import router as student_router
from app.core import database
from app.core.config import get_settings
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.security import CSRFProtectionMiddleware


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    docs_url = None if settings.environment.lower() == "production" else "/docs"
    redoc_url = None if settings.environment.lower() == "production" else "/redoc"
    openapi_url = None if settings.environment.lower() == "production" else "/openapi.json"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Credential-carrying cookies require an explicit origin list, never "*".
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(CSRFProtectionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "HEAD", "POST", "PATCH"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
    )
    app.include_router(authentication_router)
    app.include_router(classroom_router)
    app.include_router(student_router)
    app.include_router(attendance_router)

    @app.get("/api/health", tags=["health"])
    def health() -> JSONResponse:
        """Liveness and readiness: also probes the database connection."""
        try:
            with database.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except OperationalError:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "environment": settings.environment,
                    "database": "unreachable",
                },
            )
        return JSONResponse(
            content={
                "status": "ok",
                "environment": settings.environment,
                "database": "reachable",
            }
        )

    return app


app = create_app()
