"""Supabase configuration.

This module exposes the Supabase Auth settings for later use. It deliberately
does not implement any authentication flow (registration, login, sessions), and
it does not import a Supabase client library. Supabase Auth is expected to be
called from the backend only; service credentials must never reach the frontend.
"""

from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class SupabaseConfig:
    """Server-side Supabase settings needed to talk to Supabase Auth."""

    url: str | None
    service_role_key: str | None

    @property
    def is_configured(self) -> bool:
        """Whether both the project URL and the service role key are present."""
        return bool(self.url and self.service_role_key)

    @property
    def auth_base_url(self) -> str | None:
        """Base URL of the Supabase Auth (GoTrue) REST API, if configured."""
        if not self.url:
            return None
        return f"{self.url.rstrip('/')}/auth/v1"


def get_supabase_config(settings: Settings | None = None) -> SupabaseConfig:
    """Build a ``SupabaseConfig`` from application settings."""
    settings = settings or get_settings()
    service_role_key = (
        settings.supabase_service_role_key.get_secret_value()
        if settings.supabase_service_role_key is not None
        else None
    )
    return SupabaseConfig(url=settings.supabase_url, service_role_key=service_role_key)
