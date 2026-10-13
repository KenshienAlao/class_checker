"""Attendance record model linking a student to a session."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.attendance_session import AttendanceSession
from app.models.student import Student


class AttendanceRecord(Base):
    """A single student's attendance within one session.

    At most one record exists per student per session, enforced by
    ``uq_attendance_records_session_id_student_id``. ``method`` is null for
    records finalized as absent, where no attendance input occurred.
    """

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "student_id", name="uq_attendance_records_session_id_student_id"
        ),
        CheckConstraint("status IN ('PENDING', 'PRESENT', 'ABSENT')", name="record_status"),
        CheckConstraint("method IS NULL OR method IN ('QR', 'MANUAL')", name="record_method"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("attendance_sessions.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("students.id"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default="PENDING", server_default=text("'PENDING'")
    )
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    method: Mapped[str | None] = mapped_column(String(16))

    session: Mapped[AttendanceSession] = relationship()
    student: Mapped[Student] = relationship()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )
