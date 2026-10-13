"""Unit tests for the authentication request schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.authentication_schema import Register


def test_valid_registration_is_accepted() -> None:
    data = Register(
        name="Jane Doe",
        email="jane@example.com",
        password="Sup3r!Secret",
        confirm="Sup3r!Secret",
    )
    assert data.email == "jane@example.com"


def test_mismatched_confirmation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Register(
            name="Jane Doe",
            email="jane@example.com",
            password="Sup3r!Secret",
            confirm="different-secret",
        )
