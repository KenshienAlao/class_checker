"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Self
from urllib.parse import quote_plus, urlsplit, urlunsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SQLAlchemy dialect for psycopg (v3). Both local and Supabase connections use it.
SQLALCHEMY_DRIVER = "postgresql+psycopg"

# Dev-only fallback for session signing. Reused verbatim nowhere in production:
# the validator below refuses to start production with it.
_DEV_SESSION_SECRET = "developent-session-key-12345-@"
_DEV_POSTGRES_PASSWORD = "development-password-key-12345-@"

_POSTGRES_SCHEMES = {"postgres", "postgresql"}


def normalize_database_url(url: str) -> str:
    """Rewrite a PostgreSQL URL so SQLAlchemy uses the psycopg (v3) driver.

    Supabase and Docker Compose both hand out ``postgresql://`` (or
    ``postgres://``) URLs. SQLAlchemy needs an explicit driver, so the scheme is
    rewritten to ``postgresql+psycopg``. The rest of the URL, including any
    query string such as ``sslmode=require``, is preserved untouched.
    """
    parts = urlsplit(url)
    if parts.scheme in _POSTGRES_SCHEMES:
        scheme = SQLALCHEMY_DRIVER
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
    return url


_MIN_SESSION_SECRET_BYTES = 32


def normalize_origin(value: str) -> str:
    """Return the canonical form of a browser origin.

    The canonical form has no userinfo, path, query, or fragment. Default
    ports are omitted so ``https://example.com`` and
    ``https://example.com:443`` compare consistently. Invalid or wildcard
    origins raise ``ValueError``.
    """
    raw = value.strip()
    if not raw or "*" in raw:
        raise ValueError("origin must be non-empty and must not contain a wildcard")

    parsed = urlsplit(raw)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("origin must use an http or https scheme")
    if parsed.username or parsed.password:
        raise ValueError("origin must not include authentication information")
    if parsed.path not in ("", "/"):
        raise ValueError("origin must not include a path")
    if parsed.query or parsed.fragment:
        raise ValueError("origin must not include a query or fragment")
    if parsed.hostname is None:
        raise ValueError("origin must include a hostname")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("origin must use a valid port") from exc
    if ":" in parsed.netloc and port is None:
        raise ValueError("origin must use a valid port")
    if port is not None and not (1 <= port <= 65535):
        raise ValueError("origin port must be between 1 and 65535")

    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    if port is None:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


_DEV_ORIGIN_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}


def _is_development_origin(origin: str) -> bool:
    host = urlsplit(origin).hostname
    if host is None:
        return False
    return host.lower() in _DEV_ORIGIN_HOSTS or host.lower().endswith(".localhost")


def _normalized_allowed_origins(allowed_origins: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for origin in allowed_origins.split(","):
        if not origin.strip():
            raise ValueError("origin must not be empty")
        item = normalize_origin(origin)
        if item in seen:
            raise ValueError("duplicate origin is not allowed")
        seen.add(item)
        normalized.append(item)
    return normalized


def _production_origin_is_valid(origin: str) -> bool:
    if "*" in origin:
        return False
    if not origin.startswith("https://"):
        return False
    return not _is_development_origin(origin)


class Settings(BaseSettings):
    """Typed application settings.

    Values are read from environment variables (and an optional ``.env`` file).
    Secrets are never given defaults that resemble real credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Class Checker API"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Comma-separated trusted frontend origins. Credentialed CORS forbids "*".
    allowed_origins: str = "http://localhost:3000"

    # HMAC key for the JWT session cookie (HS256). Must be a long random value.
    session_secret: SecretStr = SecretStr(_DEV_SESSION_SECRET)
    session_ttl_minutes: int = 60 * 24

    # Local PostgreSQL (Docker Compose). Used when SUPABASE_DB_URL is not set.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "class_checker"
    postgres_password: SecretStr = SecretStr(_DEV_POSTGRES_PASSWORD)
    postgres_db: str = "class_checker"

    # Supabase. Configuration only; the authentication flow is not implemented yet.
    supabase_url: str | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_db_url: SecretStr | None = None

    rate_limit_enabled: bool | None = None
    trusted_proxy_ips: str = ""
    rate_limit_window_seconds: int = 60
    rate_limit_generic_requests: int = 120
    rate_limit_auth_client_requests: int = 20
    rate_limit_auth_account_requests: int = 10
    rate_limit_import_requests: int = 5
    rate_limit_export_requests: int = 5
    rate_limit_attendance_session_requests: int = 30
    rate_limit_max_buckets: int = 10_000

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy connection URL.

        ``SUPABASE_DB_URL`` takes precedence over the local PostgreSQL settings so
        that a single deployment can switch between environments via env vars.
        """
        if self.supabase_db_url is not None:
            return normalize_database_url(self.supabase_db_url.get_secret_value())

        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password.get_secret_value())
        return (
            f"{SQLALCHEMY_DRIVER}://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def rate_limiting_enabled(self) -> bool:
        if self.rate_limit_enabled is not None:
            return self.rate_limit_enabled
        return self.environment.lower() not in {"development", "test", "testing"}

    @property
    def trusted_proxy_ip_set(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.trusted_proxy_ips.split(",") if item.strip())

    @property
    def uses_supabase_database(self) -> bool:
        """Whether the Supabase database connection string is configured."""
        return self.supabase_db_url is not None

    @property
    def allowed_origin_list(self) -> list[str]:
        """Canonical trusted frontend origins parsed from ``allowed_origins``."""
        return _normalized_allowed_origins(self.allowed_origins)

    @property
    def trusted_origin_set(self) -> frozenset[str]:
        """Canonical trusted origins used consistently by CORS and Origin checks."""
        return frozenset(self.allowed_origin_list)

    @model_validator(mode="after")
    def guard_allowed_origins(self) -> Self:
        """Validate origins once, when settings are constructed."""
        normalized = self.allowed_origin_list
        if self.environment.lower() == "development" and not normalized:
            return self
        if self.environment.lower() == "production":
            if not normalized:
                raise ValueError("CORS_ALLOWED_ORIGINS must not be empty in production")
            for origin in normalized:
                if not _production_origin_is_valid(origin):
                    raise ValueError(f"untrusted or invalid production origin: {origin}")
        return self

    @model_validator(mode="after")
    def guard_session_settings(self) -> Self:
        """Refuse production startup with an unsafe token secret or TTL."""
        secret = self.session_secret.get_secret_value()
        if self.environment.lower() == "production" and (
            not secret
            or secret == _DEV_SESSION_SECRET
            or len(secret.encode("utf-8")) < _MIN_SESSION_SECRET_BYTES
        ):
            raise ValueError(
                f"SESSION_SECRET must contain at least {_MIN_SESSION_SECRET_BYTES} "
                "random bytes in production"
            )
        if self.session_ttl_minutes <= 0:
            raise ValueError("session_ttl_minutes must be positive")
        for field_name in (
            "rate_limit_window_seconds",
            "rate_limit_generic_requests",
            "rate_limit_auth_client_requests",
            "rate_limit_auth_account_requests",
            "rate_limit_import_requests",
            "rate_limit_export_requests",
            "rate_limit_attendance_session_requests",
            "rate_limit_max_buckets",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.environment.lower() == "production" and self.rate_limit_enabled is False:
            raise ValueError("rate limiting must remain enabled in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""
    return Settings()
