"""Classroom-scoped student model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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
from app.models.classroom import Classroom


class Student(Base):
    """A student owned by exactly one classroom.

    ``student_id`` is the business identifier and is unique only within its
    classroom. Students are deactivated with ``is_active = false`` rather than
    deleted so historical attendance is preserved.
    """

    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_students_classroom_id_student_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    classroom_id: Mapped[int] = mapped_column(ForeignKey("classrooms.id"), index=True)
    student_id: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(255))
    program: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    classroom: Mapped[Classroom] = relationship()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=func.now()
    )
