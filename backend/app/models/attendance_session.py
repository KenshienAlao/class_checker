"""Attendance session model for a classroom."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.classroom import Classroom


class AttendanceSession(Base):
    """A dated attendance event belonging to exactly one classroom.

    A classroom has at most one ``ACTIVE`` session at a time. The partial unique
    index ``uq_attendance_sessions_active_classroom`` enforces that rule at the
    database level for PostgreSQL.
    """

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'FINALIZED')", name="session_status"),
        Index(
            "uq_attendance_sessions_active_classroom",
            "classroom_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), index=True)
    status: Mapped[str] = mapped_column(
        String(16), default="ACTIVE", server_default=text("'ACTIVE'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    classroom: Mapped[Classroom] = relationship()
