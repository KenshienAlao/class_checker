"""Request and response schemas for the classroom endpoints."""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _must_not_be_blank(value: str) -> str:
    """Reject empty and whitespace-only strings without mutating the value."""
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


Name = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255),
    AfterValidator(_must_not_be_blank),
]


class ClassroomCreate(BaseModel):
    """Create payload for a classroom owned by the current user."""

    model_config = ConfigDict(extra="forbid")

    name: Name


class ClassroomUpdate(BaseModel):
    """Patch payload for renaming a classroom.

    ``name`` is required because it is the classroom's only mutable field and
    ``ClassroomService.rename`` updates it unconditionally.
    """

    model_config = ConfigDict(extra="forbid")

    name: Name


class ClassroomResponse(BaseModel):
    """Public classroom representation. ``owner_id`` stays implicit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
