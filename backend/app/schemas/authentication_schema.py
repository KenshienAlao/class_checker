"""Request schemas for the authentication endpoints.

Credentials are hashed with argon2 (pwdlib) in the service layer; this module
only validates shape and rejects a mismatched password confirmation.
"""

from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

# Whitespace is stripped first so backend validation matches the frontend's trim().
Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
# Sanity check only; full RFC-compliant validation is out of scope.
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class Register(BaseModel):
    """Registration payload."""

    name: Name
    email: Email
    password: Password
    confirm: Password

    @model_validator(mode="after")
    def _passwords_match(self) -> Self:
        """Reject a mismatched confirmation; the client is not authoritative."""
        if self.password != self.confirm:
            raise ValueError("passwords do not match")
        return self


class Login(BaseModel):
    """Login payload."""

    email: Email
    password: Password


class UserResponse(BaseModel):
    """Public user profile. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
