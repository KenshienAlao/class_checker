"""Persistence for classroom rows owned by application users."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.classroom import Classroom


class ClassroomRepository:
    """Reads and writes ``classrooms`` rows.

    Every lookup is owner-scoped: there is no method that returns a classroom
    without an ``owner_id`` filter, so a caller cannot accidentally read another
    user's row.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_owner(self, owner_id: UUID) -> list[Classroom]:
        """Return the owner's classrooms, newest first."""
        return list(
            self.db.scalars(
                select(Classroom)
                .where(Classroom.owner_id == owner_id)
                .order_by(Classroom.created_at.desc(), Classroom.id.desc())
            )
        )

    def get_owned(self, classroom_id: int, owner_id: UUID) -> Classroom | None:
        """Return the classroom only when it belongs to ``owner_id``.

        ``None`` covers both a missing row and one owned by another user, so the
        caller cannot distinguish the two.
        """
        return self.db.scalar(
            select(Classroom).where(
                Classroom.id == classroom_id,
                Classroom.owner_id == owner_id,
            )
        )

    def create(self, classroom: Classroom) -> Classroom:
        """Persist a new classroom and return the committed row."""
        self.db.add(classroom)
        self.db.commit()
        self.db.refresh(classroom)
        return classroom

    def update(self, classroom: Classroom) -> Classroom:
        """Persist mutated fields on a tracked ``classroom``."""
        self.db.commit()
        self.db.refresh(classroom)
        return classroom
