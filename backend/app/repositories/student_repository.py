"""Persistence for classroom-scoped student rows."""

from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models.classroom import Classroom
from app.models.student import Student

_LIKE_ESCAPE = "\\"


def _like_pattern(term: str) -> str:
    """Build a literal ``%term%`` LIKE pattern.

    ``%`` and ``_`` are wildcards in SQL; escaping them keeps search a literal
    substring match instead of letting user input widen the match.
    """
    escaped = (
        term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", f"{_LIKE_ESCAPE}%")
        .replace("_", f"{_LIKE_ESCAPE}_")
    )
    return f"%{escaped}%"


class StudentRepository:
    """Reads and writes ``students`` rows.

    Students are scoped to a classroom, which is itself owned by a user. The
    ownership check is expressed as a join so callers can never load a student
    outside the requesting owner.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self, classroom_id: int, search: str | None = None) -> list[Student]:
        """Return active students in a classroom, optionally filtered by search.

        ``search`` matches ``student_id`` or ``full_name`` case-insensitively as
        a literal substring. Filtering happens in the database.
        """
        conditions = [
            Student.classroom_id == classroom_id,
            Student.is_active.is_(True),
        ]

        term = (search or "").strip()
        if term:
            pattern = _like_pattern(term)
            conditions.append(
                or_(
                    Student.student_id.ilike(pattern, escape=_LIKE_ESCAPE),
                    Student.full_name.ilike(pattern, escape=_LIKE_ESCAPE),
                )
            )

        return list(
            self.db.scalars(
                select(Student)
                .where(*conditions)
                .order_by(Student.full_name.asc(), Student.student_id.asc())
            )
        )

    def get_owned(self, student_id: UUID, owner_id: UUID) -> Student | None:
        """Return the student only when its classroom belongs to ``owner_id``.

        ``None`` covers a missing row and a row owned by another user. Inactive
        students are still returned so they remain fetchable and deactivatable.
        """
        return self.db.scalar(
            select(Student)
            .join(Student.classroom)
            .where(
                Student.id == student_id,
                Classroom.owner_id == owner_id,
            )
        )

    def exists_student_id(
        self, classroom_id: int, student_id: str, exclude_id: UUID | None = None
    ) -> bool:
        """Return whether ``student_id`` is taken within ``classroom_id``.

        ``exclude_id`` skips the row being updated so a student can keep its own
        identifier.
        """
        conditions = [
            Student.classroom_id == classroom_id,
            Student.student_id == student_id,
        ]
        if exclude_id is not None:
            conditions.append(Student.id != exclude_id)

        return bool(self.db.scalar(select(exists().where(*conditions))))

    def list_existing_student_ids(self, classroom_id: int) -> list[str]:
        """Return every existing student_id in a classroom, active or inactive."""
        return list(
            self.db.scalars(select(Student.student_id).where(Student.classroom_id == classroom_id))
        )

    # Backward-compatible alias retained only for existing callers.
    list_student_ids = list_existing_student_ids

    def create(self, student: Student) -> Student:
        """Persist a new student and return the committed row."""
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def update(self, student: Student) -> Student:
        """Persist mutated fields on a tracked ``student``."""
        self.db.commit()
        self.db.refresh(student)
        return student
