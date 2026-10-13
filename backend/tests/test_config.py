"""Tests for the session-secret production guard."""

import pytest
from pydantic import ValidationError

from app.core.config import _DEV_SESSION_SECRET, Settings


def test_production_rejects_dev_only_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            allowed_origins="https://app.example.com",
            session_secret=_DEV_SESSION_SECRET,
            _env_file=None,
        )


def test_production_rejects_blank_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            session_secret="",
            allowed_origins="https://app.example.com",
            _env_file=None,
        )


def test_production_accepts_explicit_secret() -> None:
    settings = Settings(
        environment="production",
        allowed_origins="https://app.example.com",
        session_secret="unsaccipeNrvNnQ0danQfEG0DDsEAhXayHhL0M6Xg9sI80VIh1EaBVsWvHDFwCcHUM2",
        _env_file=None,
    )
    assert settings.environment == "production"


def test_development_uses_dev_only_secret() -> None:
    settings = Settings(environment="development", _env_file=None)
    assert settings.session_secret.get_secret_value() == _DEV_SESSION_SECRET


def test_production_rejects_short_session_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            session_secret="x" * 31,
            allowed_origins="https://app.example.com",
            _env_file=None,
        )


def test_session_ttl_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="development", session_ttl_minutes=0, _env_file=None)


def test_allowed_origin_list_normalizes_default_ports() -> None:
    settings = Settings(
        environment="development",
        allowed_origins="https://example.com,https://www.example.com",
        _env_file=None,
    )

    assert settings.allowed_origin_list == ["https://example.com", "https://www.example.com"]


def test_production_rejects_wildcard_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production", allowed_origins="*", session_secret="A" * 32, _env_file=None
        )


def test_production_rejects_duplicate_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            allowed_origins="https://app.example.com,https://APP.example.com",
            session_secret="A" * 32,
            _env_file=None,
        )


def test_production_rejects_development_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            allowed_origins="http://localhost:3000",
            session_secret="A" * 32,
            _env_file=None,
        )


def test_production_rejects_empty_allowlist() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            allowed_origins="",
            session_secret="A" * 32,
            _env_file=None,
        )
