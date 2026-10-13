"""Attendance session and record use cases."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import Classroom
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository

_ACTIVE_SESSION_EXISTS = "Classroom already has an active session"
_NO_ACTIVE_STUDENTS = "Classroom has no active students"

_ALLOWED_METHODS = ("QR", "MANUAL")

_SESSION_NOT_FOUND = "Attendance session not found"
_SESSION_NOT_ACTIVE = "Attendance session is already finalized"
_STUDENT_NOT_FOUND = "Student was not found"
_RECORD_ABSENT = "Student is already marked absent"
_INVALID_METHOD = "method must be one of QR or MANUAL"
_FINALIZE_FAILED = "Attendance could not be finalized"


@dataclass(frozen=True, slots=True)
class MarkPresentResult:
    """Outcome of a mark-present call.

    ``already_marked`` is true when the record was already ``PRESENT`` and was
    left unchanged (idempotent duplicate scan).
    """

    record: AttendanceRecord
    already_marked: bool


@dataclass(frozen=True, slots=True)
class FinalizeResult:
    """Outcome of a finalize-session call.

    ``present_count`` and ``absent_count`` are the tallies after finalization;
    ``session.finalized_at`` carries the completion timestamp.
    """

    session: AttendanceSession
    present_count: int
    absent_count: int


@dataclass(frozen=True, slots=True)
class SessionReview:
    """Read model for the session review screen (`docs/05` §15).

    Holds the session (status and timestamps, including ``started_at`` as the
    session date), its classroom, counts derived from the persisted records
    (including zero counts), and the roster-snapshot records ordered by student
    name. Each record exposes its ``student`` identity and attendance fields.
    """

    session: AttendanceSession
    classroom: Classroom
    pending_count: int
    present_count: int
    absent_count: int
    records: list[AttendanceRecord]


class AttendanceService:
    """Attendance use cases scoped to an owned classroom.

    The service owns the transaction boundary: repositories stage writes with
    ``flush`` and the service performs the single ``commit`` or ``rollback``, so
    a session and its pending records are created atomically. A classroom that is
    missing and one owned by another user produce the same 404.
    """

    def __init__(
        self,
        session_repository: AttendanceSessionRepository,
        record_repository: AttendanceRecordRepository,
        classroom_repository: ClassroomRepository,
        student_repository: StudentRepository,
    ) -> None:
        self.session_repository = session_repository
        self.record_repository = record_repository
        self.classroom_repository = classroom_repository
        self.student_repository = student_repository

    def create_session(self, classroom_id: int, owner_id: UUID) -> AttendanceSession:
        """Create an ACTIVE session with a PENDING record per active student.

        Raises 404 for a missing or unowned classroom and 409 when the classroom
        already has an active session or has no active students. The session and
        its records are committed together; a failed write leaves no partial
        state.
        """
        self._ensure_owned_classroom(classroom_id, owner_id)
        self._ensure_no_active_session(classroom_id)
        roster = self.student_repository.list_active(classroom_id)
        if not roster:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_NO_ACTIVE_STUDENTS)

        session = AttendanceSession(classroom_id=classroom_id, status="ACTIVE")
        try:
            self.session_repository.add(session)
            self.record_repository.add_all(
                [
                    AttendanceRecord(
                        session_id=session.id,
                        student_id=student.id,
                        status="PENDING",
                    )
                    for student in roster
                ]
            )
            self.session_repository.db.commit()
        except IntegrityError:
            self.session_repository.db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_ACTIVE_SESSION_EXISTS) from None
        self.session_repository.db.refresh(session)
        return session

    def mark_present(
        self,
        session_id: int,
        owner_id: UUID,
        *,
        student_id: str,
        method: str,
    ) -> MarkPresentResult:
        """Mark a roster record PRESENT from a QR or manual attendance input.

        Locks the session and requires it to be ``ACTIVE``, then resolves the
        precreated roster record by the student's business ID. ``PENDING``
        records become ``PRESENT``; an already-present record is an idempotent
        success that is left unchanged. A missing or unowned session is a 404, as
        is an unknown student; a finalized session or an absent record is a 409.
        The roster snapshot is authoritative, so a student who was deactivated
        after the session started can still be marked.
        """
        if method not in _ALLOWED_METHODS:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=_INVALID_METHOD)

        session = self.session_repository.get_owned_for_update(session_id, owner_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_SESSION_NOT_FOUND)
        if session.status != "ACTIVE":
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_SESSION_NOT_ACTIVE)

        record = self.record_repository.get_by_student_business_id(session_id, student_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_STUDENT_NOT_FOUND)
        if record.status == "PRESENT":
            return MarkPresentResult(record=record, already_marked=True)
        if record.status == "ABSENT":
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_RECORD_ABSENT)

        record.status = "PRESENT"
        record.marked_at = datetime.now(UTC)
        record.method = method
        try:
            self.session_repository.db.commit()
        except IntegrityError:
            self.session_repository.db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Attendance could not be recorded"
            ) from None
        self.session_repository.db.refresh(record)
        return MarkPresentResult(record=record, already_marked=False)

    def finalize_session(self, session_id: int, owner_id: UUID) -> FinalizeResult:
        """Finalize an ACTIVE session: PENDING records become ABSENT.

        Locks the session and requires it to be ``ACTIVE``; a repeated
        finalization is a 409, as is a missing or unowned session (uniform 404
        for the latter). The pending-to-absent sweep and the session's
        ``FINALIZED`` status and ``finalized_at`` are committed as one
        transaction, so a failure leaves neither partially finalized records nor
        a partially finalized session. ``PRESENT`` records are untouched.
        """
        session = self.session_repository.get_owned_for_update(session_id, owner_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_SESSION_NOT_FOUND)
        if session.status != "ACTIVE":
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_SESSION_NOT_ACTIVE)

        try:
            self.record_repository.finalize_pending(session_id)
            session.status = "FINALIZED"
            session.finalized_at = datetime.now(UTC)
            self.session_repository.db.commit()
        except IntegrityError:
            self.session_repository.db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_FINALIZE_FAILED) from None
        self.session_repository.db.refresh(session)
        counts = self.record_repository.count_by_status(session_id)
        return FinalizeResult(
            session=session,
            present_count=counts["PRESENT"],
            absent_count=counts["ABSENT"],
        )

    def get_session(self, session_id: int, owner_id: UUID) -> SessionReview:
        """Return the review data for an owned session.

        Read-only: the service fetches the ownership-scoped session, derives the
        ``PENDING``/``PRESENT``/``ABSENT`` counts from the persisted records, and
        returns the session's roster records ordered by student name. Records
        from other sessions or classrooms are never included, and roster members
        deactivated after the session started remain in the snapshot. A missing
        or unowned session is a uniform 404.
        """
        session = self.session_repository.get_owned(session_id, owner_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=_SESSION_NOT_FOUND)
        counts = self.record_repository.count_by_status(session_id)
        return SessionReview(
            session=session,
            classroom=session.classroom,
            pending_count=counts["PENDING"],
            present_count=counts["PRESENT"],
            absent_count=counts["ABSENT"],
            records=self.record_repository.list_by_session(session_id),
        )

    def _ensure_owned_classroom(self, classroom_id: int, owner_id: UUID) -> None:
        if self.classroom_repository.get_owned(classroom_id, owner_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Classroom not found")

    def _ensure_no_active_session(self, classroom_id: int) -> None:
        if self.session_repository.get_active_for_classroom(classroom_id) is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_ACTIVE_SESSION_EXISTS)
