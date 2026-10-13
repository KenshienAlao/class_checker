"""Attendance history grid assembly (`docs/03` §20a, `docs/02` §10)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status

from app.models.student import Student
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository

_CLASSROOM_NOT_FOUND = "Classroom not found"


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One student's row in the history grid.

    ``statuses`` is aligned one-to-one with ``AttendanceHistoryGrid.dates``; each
    entry is ``PRESENT``, ``ABSENT``, or ``None`` when no record exists for that
    date (for example a student enrolled after the session).
    """

    student_id: str
    student_name: str
    is_active: bool
    statuses: list[str | None]


@dataclass(frozen=True, slots=True)
class AttendanceHistoryGrid:
    """Read model for the classroom attendance history grid.

    Rows are students, columns are the distinct attendance dates of the
    classroom's finalized sessions, and the grid is derived from finalized
    records rather than stored separately.
    """

    classroom_id: int
    classroom_name: str
    dates: list[date]
    rows: list[HistoryRow]


def _session_date(started_at: datetime) -> date:
    """Return a session's attendance date in the application's UTC convention.

    Session timestamps are written in UTC (``datetime.now(UTC)`` or the
    ``now()`` server default), so the calendar date is taken in UTC. Normalizing
    explicitly keeps the grid independent of the PostgreSQL session time zone
    instead of relying on an implicit conversion.
    """
    return started_at.astimezone(UTC).date()


class AttendanceHistoryService:
    """Assembles the read-only attendance history grid for an owned classroom.

    Rows are the classroom's active students plus deactivated students that have
    records in finalized sessions, so a student's history survives deactivation
    while a deactivated student with no history is omitted. Columns are the
    distinct dates of the classroom's finalized sessions in chronological order.
    A cell is ``PRESENT`` when any finalized record for that student and date is
    present, ``ABSENT`` when records exist but none is present, and ``None`` when
    the student has no record for that date.

    The service is read-only: it never writes, flushes, or commits. A missing
    classroom and one owned by another user both yield a uniform 404.
    """

    def __init__(
        self,
        classroom_repository: ClassroomRepository,
        session_repository: AttendanceSessionRepository,
        record_repository: AttendanceRecordRepository,
        student_repository: StudentRepository,
    ) -> None:
        self.classroom_repository = classroom_repository
        self.session_repository = session_repository
        self.record_repository = record_repository
        self.student_repository = student_repository

    def build_grid(self, classroom_id: int, owner_id: UUID) -> AttendanceHistoryGrid:
        """Return the attendance history grid for the owner's classroom."""
        classroom = self.classroom_repository.get_owned(classroom_id, owner_id)
        if classroom is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_CLASSROOM_NOT_FOUND)

        dates: list[date] = []
        for session in self.session_repository.list_finalized_for_classroom(classroom_id):
            session_date = _session_date(session.started_at)
            if not dates or dates[-1] != session_date:
                dates.append(session_date)

        statuses: dict[tuple[UUID, date], str] = {}
        students: dict[UUID, Student] = {}
        for record in self.record_repository.list_finalized_for_classroom(classroom_id):
            student = record.student
            students[student.id] = student
            key = (student.id, _session_date(record.session.started_at))
            if record.status == "PRESENT":
                statuses[key] = "PRESENT"
            elif record.status == "ABSENT":
                statuses.setdefault(key, "ABSENT")

        for student in self.student_repository.list_active(classroom_id):
            students.setdefault(student.id, student)

        rows = [
            HistoryRow(
                student_id=student.student_id,
                student_name=student.full_name,
                is_active=student.is_active,
                statuses=[statuses.get((student.id, day)) for day in dates],
            )
            for student in sorted(
                students.values(), key=lambda item: (item.full_name, item.student_id)
            )
        ]
        return AttendanceHistoryGrid(
            classroom_id=classroom.id,
            classroom_name=classroom.name,
            dates=dates,
            rows=rows,
        )
