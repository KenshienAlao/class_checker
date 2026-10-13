"""Integration tests for ``StudentService`` against PostgreSQL."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.classroom import Classroom
from app.models.user import User
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.student_service import StudentService


def _owner(db: Session) -> User:
    user = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _classroom(db: Session, owner: User) -> Classroom:
    return ClassroomRepository(db).create(Classroom(name="BSIT2B", owner_id=owner.id))


def _service(db: Session) -> StudentService:
    return StudentService(StudentRepository(db), ClassroomRepository(db))


def test_create_adds_a_student_to_the_owned_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)

    student = _service(db_session).create(
        classroom.id, owner.id, student_id="25-09759", full_name="Alex Santos"
    )

    assert student.id is not None
    assert student.classroom_id == classroom.id
    assert student.student_id == "25-09759"
    assert student.is_active is True


def test_create_raises_404_for_unowned_classroom(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).create(classroom.id, stranger.id, student_id="1", full_name="A")

    assert exc.value.status_code == 404


def test_create_raises_409_for_duplicate_student_id(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    with pytest.raises(HTTPException) as exc:
        service.create(classroom.id, owner.id, student_id="001", full_name="Bob")

    assert exc.value.status_code == 409


def test_create_conflict_race_raises_409_and_keeps_session_usable(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    def _no_duplicate(*args: object, **kwargs: object) -> bool:
        return False

    # Simulate two requests passing the pre-check concurrently.
    monkeypatch.setattr(service.repository, "exists_student_id", _no_duplicate)

    with pytest.raises(HTTPException) as exc:
        service.create(classroom.id, owner.id, student_id="001", full_name="Bob")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Student ID already exists in this classroom"

    # The rolled-back session must still serve further queries.
    assert [s.student_id for s in service.list(classroom.id, owner.id)] == ["001"]


def test_list_returns_active_students_only(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    active = service.create(classroom.id, owner.id, student_id="1", full_name="Active")
    inactive = service.create(classroom.id, owner.id, student_id="2", full_name="Inactive")
    service.deactivate(inactive.id, owner.id)

    names = [s.full_name for s in service.list(classroom.id, owner.id)]

    assert names == ["Active"]
    assert active.id is not None


def test_list_raises_404_for_unowned_classroom(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).list(classroom.id, stranger.id)

    assert exc.value.status_code == 404


def test_list_rejects_search_longer_than_255_characters(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).list(classroom.id, owner.id, search="x" * 256)

    assert exc.value.status_code == 422


def test_list_accepts_a_255_character_search(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)

    students = _service(db_session).list(classroom.id, owner.id, search="x" * 255)

    assert students == []


def test_get_returns_a_student_of_the_owner(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    student = _service(db_session).create(classroom.id, owner.id, student_id="1", full_name="A")

    found = _service(db_session).get(student.id, owner.id)

    assert found.id == student.id


def test_get_returns_inactive_students(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="1", full_name="A")
    service.deactivate(student.id, owner.id)

    found = service.get(student.id, owner.id)

    assert found.is_active is False


def test_get_raises_404_for_another_users_student(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    student = _service(db_session).create(classroom.id, other.id, student_id="1", full_name="A")
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).get(student.id, stranger.id)

    assert exc.value.status_code == 404


def test_get_raises_404_for_missing_student(db_session: Session) -> None:
    owner = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).get(uuid4(), owner.id)

    assert exc.value.status_code == 404


def test_update_changes_full_name(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    updated = service.update(student.id, owner.id, full_name="Alice Santos")

    assert updated.full_name == "Alice Santos"


def test_update_leaves_omitted_program_unchanged(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(
        classroom.id, owner.id, student_id="001", full_name="Alice", program="BSIT"
    )

    updated = service.update(student.id, owner.id, full_name="Alice Santos")

    assert updated.program == "BSIT"
    assert updated.full_name == "Alice Santos"


def test_update_clears_program_with_explicit_null(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(
        classroom.id, owner.id, student_id="001", full_name="Alice", program="BSIT"
    )

    updated = service.update(student.id, owner.id, program=None)

    assert updated.program is None


def test_update_rejects_empty_body(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    with pytest.raises(HTTPException) as exc:
        service.update(student.id, owner.id)

    assert exc.value.status_code == 422


def test_update_rejects_null_full_name(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    with pytest.raises(HTTPException) as exc:
        service.update(student.id, owner.id, full_name=None)

    assert exc.value.status_code == 422


def test_update_rejects_null_student_id(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    with pytest.raises(HTTPException) as exc:
        service.update(student.id, owner.id, student_id=None)

    assert exc.value.status_code == 422


def test_update_changes_student_id(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    updated = service.update(student.id, owner.id, student_id="002")

    assert updated.student_id == "002"


def test_update_student_id_conflict_raises_409(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    service.create(classroom.id, owner.id, student_id="001", full_name="Alice")
    second = service.create(classroom.id, owner.id, student_id="002", full_name="Bob")

    with pytest.raises(HTTPException) as exc:
        service.update(second.id, owner.id, student_id="001")

    assert exc.value.status_code == 409


def test_update_keeps_an_unchanged_student_id(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    updated = service.update(student.id, owner.id, student_id="001")

    assert updated.student_id == "001"


def test_deactivate_is_idempotent(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    service = _service(db_session)
    student = service.create(classroom.id, owner.id, student_id="001", full_name="Alice")

    first = service.deactivate(student.id, owner.id)
    second = service.deactivate(student.id, owner.id)

    assert first.is_active is False
    assert second.is_active is False


def test_deactivate_raises_404_for_unowned_student(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    student = _service(db_session).create(classroom.id, other.id, student_id="001", full_name="A")
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).deactivate(student.id, stranger.id)

    assert exc.value.status_code == 404
