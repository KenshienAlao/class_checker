"""Persistence for attendance sessions belonging to a classroom."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance_session import AttendanceSession
from app.models.classroom import Classroom


class AttendanceSessionRepository:
    """Reads and writes ``attendance_sessions`` rows.

    A session is reached through its classroom, which is owned by a user, so
    every lookup joins the classroom and carries an ``owner_id`` filter. A
    missing session and one belonging to another user both yield ``None``, so
    the caller cannot distinguish the two.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_owned(self, session_id: int, owner_id: UUID) -> AttendanceSession | None:
        """Return the session only when its classroom belongs to ``owner_id``."""
        return self.db.scalar(
            select(AttendanceSession)
            .join(AttendanceSession.classroom)
            .where(
                AttendanceSession.id == session_id,
                Classroom.owner_id == owner_id,
            )
        )

    def get_owned_for_update(self, session_id: int, owner_id: UUID) -> AttendanceSession | None:
        """Return the owner's session with a row lock for a state change.

        ``FOR UPDATE`` on the session row serializes concurrent attendance
        operations for the same session. The lock targets the session row only,
        not the joined classroom row.
        """
        return self.db.scalar(
            select(AttendanceSession)
            .join(AttendanceSession.classroom)
            .where(
                AttendanceSession.id == session_id,
                Classroom.owner_id == owner_id,
            )
            .with_for_update(of=AttendanceSession)
        )

    def get_active_for_classroom(self, classroom_id: int) -> AttendanceSession | None:
        """Return the classroom's ``ACTIVE`` session, if one exists.

        The partial unique index ``uq_attendance_sessions_active_classroom``
        guarantees at most one such row.
        """
        return self.db.scalar(
            select(AttendanceSession).where(
                AttendanceSession.classroom_id == classroom_id,
                AttendanceSession.status == "ACTIVE",
            )
        )

    def list_finalized_for_classroom(self, classroom_id: int) -> list[AttendanceSession]:
        """Return the classroom's ``FINALIZED`` sessions, oldest first.

        The history grid derives its date columns from these sessions, so an
        ``ACTIVE`` session (not yet part of history) is excluded. Ordering by
        ``started_at`` then ``id`` groups a classroom's same-date sessions
        together in a stable order.
        """
        return list(
            self.db.scalars(
                select(AttendanceSession)
                .where(
                    AttendanceSession.classroom_id == classroom_id,
                    AttendanceSession.status == "FINALIZED",
                )
                .order_by(AttendanceSession.started_at.asc(), AttendanceSession.id.asc())
            )
        )

    def add(self, session: AttendanceSession) -> AttendanceSession:
        """Stage a new session and flush it, leaving the commit to the caller.

        Flushing assigns the primary key so pending records can reference the
        session while the whole creation remains in a single transaction.
        """
        self.db.add(session)
        self.db.flush()
        return session
