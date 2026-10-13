"""Request and response schemas for the student endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _must_not_be_blank(value: str) -> str:
    """Reject empty and whitespace-only strings without mutating the value."""
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


FullName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255),
    AfterValidator(_must_not_be_blank),
]
StudentIdValue = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
    AfterValidator(_must_not_be_blank),
]
Program = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255),
    AfterValidator(_must_not_be_blank),
]


class StudentCreate(BaseModel):
    """Create payload for a student in the route's classroom."""

    model_config = ConfigDict(extra="forbid")

    student_id: StudentIdValue
    full_name: FullName
    program: Program | None = None


class StudentUpdate(BaseModel):
    """Patch payload with partial-update semantics.

    An omitted field stays unchanged; explicit ``program`` null clears it. Null
    for ``student_id`` or ``full_name`` is rejected by the service so the
    schema exposes the same optionality as ``UNSET`` in the service layer.
    """

    model_config = ConfigDict(extra="forbid")

    student_id: StudentIdValue | None = None
    full_name: FullName | None = None
    program: Program | None = None


class StudentResponse(BaseModel):
    """Public student representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    classroom_id: int
    student_id: str
    full_name: str
    program: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
