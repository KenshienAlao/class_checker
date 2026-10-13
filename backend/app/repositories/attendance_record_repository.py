"""Persistence for attendance records within a session."""

from typing import cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, selectinload

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.student import Student

# Attendance statuses as defined by ``docs/04`` §10 and enforced by the
# ``record_status`` check constraint.
_STATUSES = ("PENDING", "PRESENT", "ABSENT")


class AttendanceRecordRepository:
    """Reads and writes ``attendance_records`` rows.

    A record links one student to one session. Every lookup is scoped by
    ``session_id`` so a caller cannot read or modify a record outside the
    requested session.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def add_all(self, records: list[AttendanceRecord]) -> None:
        """Stage records and flush them, leaving the commit to the caller.

        Flushing assigns primary keys so the records are usable (and the
        caller's later writes fail atomically) within a single transaction.
        """
        self.db.add_all(records)
        self.db.flush()

    def get_by_student_business_id(
        self, session_id: int, business_id: str
    ) -> AttendanceRecord | None:
        """Return the session's record for a student's business ``student_id``.

        The join to ``Student`` resolves the classroom-scoped business
        identifier, while ``session_id`` keeps the lookup inside the requested
        session.
        """
        return self.db.scalar(
            select(AttendanceRecord)
            .join(AttendanceRecord.student)
            .where(
                AttendanceRecord.session_id == session_id,
                Student.student_id == business_id,
            )
        )

    def list_by_session(self, session_id: int) -> list[AttendanceRecord]:
        """Return the session's records ordered by student name, then ID."""
        return list(
            self.db.scalars(
                select(AttendanceRecord)
                .join(AttendanceRecord.student)
                .where(AttendanceRecord.session_id == session_id)
                .order_by(Student.full_name.asc(), Student.student_id.asc())
            )
        )

    def list_finalized_for_classroom(self, classroom_id: int) -> list[AttendanceRecord]:
        """Return records belonging to a classroom's ``FINALIZED`` sessions.

        This is the source for the attendance history grid. ``classroom_id`` and
        the ``FINALIZED`` filter keep the query scoped so a caller cannot read
        records from another classroom or from an unfinalized session. Student
        and session are eager-loaded because the grid needs each record's student
        identity and session date without per-row queries.
        """
        return list(
            self.db.scalars(
                select(AttendanceRecord)
                .join(AttendanceRecord.session)
                .where(
                    AttendanceSession.classroom_id == classroom_id,
                    AttendanceSession.status == "FINALIZED",
                )
                .options(
                    selectinload(AttendanceRecord.student),
                    selectinload(AttendanceRecord.session),
                )
            )
        )

    def count_by_status(self, session_id: int) -> dict[str, int]:
        """Return a count per attendance status for the session.

        Every known status is present in the result, so a session with no
        records yields all-zero counts.
        """
        counts = dict.fromkeys(_STATUSES, 0)
        rows = self.db.execute(
            select(AttendanceRecord.status, func.count())
            .where(AttendanceRecord.session_id == session_id)
            .group_by(AttendanceRecord.status)
        )
        for status, count in rows:
            counts[status] = count
        return counts

    def finalize_pending(self, session_id: int) -> int:
        """Mark the session's ``PENDING`` records ``ABSENT``; return the count.

        ``PRESENT`` and already-``ABSENT`` records are left untouched. The bulk
        update skips ORM synchronization so it remains a single statement.
        """
        result = self.db.execute(
            update(AttendanceRecord)
            .where(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.status == "PENDING",
            )
            .values(status="ABSENT")
            .execution_options(synchronize_session=False)
        )
        return cast("CursorResult[tuple[()]]", result).rowcount
