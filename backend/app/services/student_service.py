"""Student use cases scoped to an owned classroom."""

from collections.abc import Callable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.student import Student
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository

_MAX_SEARCH_LENGTH = 255

_DUPLICATE_STUDENT_ID = "Student ID already exists in this classroom"


class _Unset:
    """Sentinel type marking a partial-update argument as not provided."""

    __slots__ = ()


UNSET = _Unset()


class StudentService:
    """Student use cases.

    Students are always reached through their classroom: every call verifies the
    classroom's owner, and a missing student is indistinguishable from one owned
    by another user.
    """

    def __init__(
        self,
        repository: StudentRepository,
        classroom_repository: ClassroomRepository,
    ) -> None:
        self.repository = repository
        self.classroom_repository = classroom_repository

    def create(
        self,
        classroom_id: int,
        owner_id: UUID,
        *,
        student_id: str,
        full_name: str,
        program: str | None = None,
    ) -> Student:
        """Add a student to the owner's classroom, rejecting duplicate IDs."""
        self._ensure_owned_classroom(classroom_id, owner_id)
        self._ensure_student_id_available(classroom_id, student_id)
        student = Student(
            classroom_id=classroom_id,
            student_id=student_id,
            full_name=full_name,
            program=program,
        )
        return self._save(lambda: self.repository.create(student))

    def list(
        self, classroom_id: int, owner_id: UUID, *, search: str | None = None
    ) -> list[Student]:
        """Return the owner's active roster for a classroom."""
        self._ensure_owned_classroom(classroom_id, owner_id)
        if search is not None and len(search) > _MAX_SEARCH_LENGTH:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Search must be at most {_MAX_SEARCH_LENGTH} characters",
            )
        return self.repository.list_active(classroom_id, search)

    def get(self, student_uuid: UUID, owner_id: UUID) -> Student:
        """Return one of the owner's students, including inactive ones."""
        return self._owned_student(student_uuid, owner_id)

    def update(
        self,
        student_uuid: UUID,
        owner_id: UUID,
        *,
        student_id: str | None | _Unset = UNSET,
        full_name: str | None | _Unset = UNSET,
        program: str | None | _Unset = UNSET,
    ) -> Student:
        """Partially update an owned student.

        ``UNSET`` leaves a field unchanged, ``program=None`` clears it, and
        ``None`` for ``student_id`` or ``full_name`` is rejected. ``is_active``
        is intentionally not updatable here; use :meth:`deactivate`.
        """
        student = self._owned_student(student_uuid, owner_id)

        if (
            isinstance(student_id, _Unset)
            and isinstance(full_name, _Unset)
            and isinstance(program, _Unset)
        ):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No fields to update")

        if not isinstance(student_id, _Unset):
            if student_id is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="student_id cannot be null",
                )
            if student_id != student.student_id:
                self._ensure_student_id_available(
                    student.classroom_id, student_id, exclude_id=student.id
                )
                student.student_id = student_id

        if not isinstance(full_name, _Unset):
            if full_name is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="full_name cannot be null",
                )
            student.full_name = full_name

        if not isinstance(program, _Unset):
            student.program = program

        return self._save(lambda: self.repository.update(student))

    def deactivate(self, student_uuid: UUID, owner_id: UUID) -> Student:
        """Mark an owned student inactive. Idempotent; history is preserved."""
        student = self._owned_student(student_uuid, owner_id)
        if not student.is_active:
            return student
        student.is_active = False
        return self.repository.update(student)

    def _ensure_owned_classroom(self, classroom_id: int, owner_id: UUID) -> None:
        if self.classroom_repository.get_owned(classroom_id, owner_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Classroom not found")

    def _owned_student(self, student_uuid: UUID, owner_id: UUID) -> Student:
        student = self.repository.get_owned(student_uuid, owner_id)
        if student is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Student not found")
        return student

    def _ensure_student_id_available(
        self, classroom_id: int, student_id: str, exclude_id: UUID | None = None
    ) -> None:
        if self.repository.exists_student_id(classroom_id, student_id, exclude_id):
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_DUPLICATE_STUDENT_ID)

    def _save(self, write: Callable[[], Student]) -> Student:
        """Run a write, translating a unique-constraint race into a 409.

        The pre-check can be passed concurrently, so the database constraint is
        the real guard. The shared session is rolled back so it stays usable for
        the rest of the request.
        """
        try:
            return write()
        except IntegrityError:
            self.repository.db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail=_DUPLICATE_STUDENT_ID) from None
