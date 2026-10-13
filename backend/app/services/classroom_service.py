"""Classroom use cases with owner-scoped access."""

from uuid import UUID

from fastapi import HTTPException, status

from app.models.classroom import Classroom
from app.repositories.classroom_repository import ClassroomRepository


class ClassroomService:
    """Classroom use cases.

    Every operation is scoped to the requesting owner: a classroom that is
    missing and one owned by another user produce the same 404, so existence is
    never disclosed.
    """

    def __init__(self, repository: ClassroomRepository) -> None:
        self.repository = repository

    def create(self, owner_id: UUID, name: str) -> Classroom:
        """Create a classroom owned by ``owner_id``."""
        return self.repository.create(Classroom(name=name, owner_id=owner_id))

    def list(self, owner_id: UUID) -> list[Classroom]:
        """Return the owner's classrooms, newest first."""
        return self.repository.list_by_owner(owner_id)

    def get(self, classroom_id: int, owner_id: UUID) -> Classroom:
        """Return the owner's classroom, or raise 404."""
        classroom = self.repository.get_owned(classroom_id, owner_id)
        if classroom is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Classroom not found")
        return classroom

    def rename(self, classroom_id: int, owner_id: UUID, name: str) -> Classroom:
        """Rename the owner's classroom."""
        classroom = self.get(classroom_id, owner_id)
        classroom.name = name
        return self.repository.update(classroom)
