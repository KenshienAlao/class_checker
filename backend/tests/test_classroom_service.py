"""Integration tests for ``ClassroomService`` against PostgreSQL."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.classroom_repository import ClassroomRepository
from app.services.classroom_service import ClassroomService


def _owner(db: Session) -> User:
    user = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _service(db: Session) -> ClassroomService:
    return ClassroomService(ClassroomRepository(db))


def test_create_assigns_the_owner(db_session: Session) -> None:
    owner = _owner(db_session)

    classroom = _service(db_session).create(owner.id, "BSIT2B")

    assert classroom.id is not None
    assert classroom.owner_id == owner.id


def test_list_returns_only_owned_classrooms(db_session: Session) -> None:
    owner = _owner(db_session)
    other = _owner(db_session)
    service = _service(db_session)
    service.create(owner.id, "Mine")
    service.create(other.id, "Theirs")

    classrooms = service.list(owner.id)

    assert [classroom.name for classroom in classrooms] == ["Mine"]


def test_get_returns_owned_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _service(db_session).create(owner.id, "BSIT2B")

    found = _service(db_session).get(classroom.id, owner.id)

    assert found.id == classroom.id


def test_get_raises_404_for_another_users_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    other = _owner(db_session)
    classroom = _service(db_session).create(owner.id, "BSIT2B")

    with pytest.raises(HTTPException) as exc:
        _service(db_session).get(classroom.id, other.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Classroom not found"


def test_get_raises_404_for_missing_classroom(db_session: Session) -> None:
    owner = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).get(10**9, owner.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Classroom not found"


def test_rename_updates_the_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    service = _service(db_session)
    classroom = service.create(owner.id, "BSIT2B")

    renamed = service.rename(classroom.id, owner.id, "BSIT3A")

    assert renamed.name == "BSIT3A"


def test_rename_raises_404_for_another_user(db_session: Session) -> None:
    owner = _owner(db_session)
    other = _owner(db_session)
    classroom = _service(db_session).create(owner.id, "BSIT2B")

    with pytest.raises(HTTPException) as exc:
        _service(db_session).rename(classroom.id, other.id, "Nope")

    assert exc.value.status_code == 404
