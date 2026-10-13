"""Request and response schemas for the attendance session endpoints."""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _must_not_be_blank(value: str) -> str:
    """Reject empty and whitespace-only strings without mutating the value."""
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


StudentIdValue = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
    AfterValidator(_must_not_be_blank),
]


class AttendanceMarkRequest(BaseModel):
    """Body for the scan and manual attendance routes (`docs/05` §6, §7).

    The attendance ``method`` is determined by the route (``/scan`` → ``QR``,
    ``/manual`` → ``MANUAL``), so callers submit only the student's business ID.
    """

    model_config = ConfigDict(extra="forbid")

    student_id: StudentIdValue


class AttendanceMarkResponse(BaseModel):
    """Outcome of a scan or manual input (`docs/05` §10, §11).

    ``already_marked`` is true for an idempotent duplicate: the record was
    already ``PRESENT`` and its original ``method``/``marked_at`` are unchanged.
    """

    student_id: str
    student_name: str
    status: str
    method: str | None
    marked_at: datetime | None
    already_marked: bool


class AttendanceRecordResponse(BaseModel):
    """A student's attendance within a session (`docs/05` §10, §15)."""

    student_id: str
    student_name: str
    status: str
    method: str | None
    marked_at: datetime | None


class AttendanceFinalizeResponse(BaseModel):
    """Outcome of finalizing a session (`docs/05` §19).

    ``present_count``/``absent_count`` are the tallies after the pending-to-absent
    sweep; ``finalized_at`` is the completion timestamp.
    """

    session_id: int
    status: str
    present_count: int
    absent_count: int
    finalized_at: datetime | None


class AttendanceSessionResponse(BaseModel):
    """Session review payload: status, classroom, date, counts, and records.

    Serves both the initial attendance screen shown after creation (`docs/05`
    §5) and the review endpoint (`docs/05` §15).
    """

    session_id: int
    classroom_id: int
    classroom_name: str
    status: str
    started_at: datetime
    finalized_at: datetime | None
    present_count: int
    pending_count: int
    absent_count: int
    records: list[AttendanceRecordResponse]


class AttendanceHistoryRowResponse(BaseModel):
    """One student's row in the attendance history grid (`docs/03` §20a).

    ``statuses`` is aligned one-to-one with ``AttendanceHistoryResponse.dates``;
    an entry is ``PRESENT``, ``ABSENT``, or JSON ``null`` when the student has no
    record for that date.
    """

    student_id: str
    student_name: str
    is_active: bool
    statuses: list[str | None]


class AttendanceHistoryResponse(BaseModel):
    """Classroom attendance history grid (`docs/05` §24).

    ``dates`` are the finalized sessions' attendance dates in chronological
    order; ``rows`` are the classroom's students ordered by name. The grid is
    read-only and derived from finalized records.
    """

    classroom_id: int
    classroom_name: str
    dates: list[date]
    rows: list[AttendanceHistoryRowResponse]
