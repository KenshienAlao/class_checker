"""Integration tests for ``StudentRepository`` against PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.student_repository import StudentRepository


def _user(db: Session) -> User:
    user = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _classroom(db: Session, owner: User, name: str = "BSIT2B") -> Classroom:
    classroom = Classroom(name=name, owner_id=owner.id)
    db.add(classroom)
    db.flush()
    return classroom


def _student(
    db: Session,
    classroom: Classroom,
    student_id: str,
    full_name: str,
    *,
    is_active: bool = True,
) -> Student:
    student = Student(
        classroom_id=classroom.id,
        student_id=student_id,
        full_name=full_name,
        is_active=is_active,
    )
    db.add(student)
    db.flush()
    return student


def test_list_active_excludes_inactive_students(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    active = _student(db_session, classroom, "1", "Active Student")
    _student(db_session, classroom, "2", "Inactive Student", is_active=False)

    students = StudentRepository(db_session).list_active(classroom.id)

    assert [student.id for student in students] == [active.id]


def test_list_active_is_scoped_to_the_classroom(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    other = _classroom(db_session, owner, name="BSIT3A")
    mine = _student(db_session, classroom, "1", "Mine")
    _student(db_session, other, "1", "Theirs")

    students = StudentRepository(db_session).list_active(classroom.id)

    assert [student.id for student in students] == [mine.id]


def test_list_active_orders_by_full_name_then_student_id(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "10", "Bob")
    _student(db_session, classroom, "20", "Alice")
    _student(db_session, classroom, "05", "Alice")

    students = StudentRepository(db_session).list_active(classroom.id)

    assert [(s.full_name, s.student_id) for s in students] == [
        ("Alice", "05"),
        ("Alice", "20"),
        ("Bob", "10"),
    ]


def test_search_matches_full_name_case_insensitively(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    target = _student(db_session, classroom, "1", "Alice Santos")
    _student(db_session, classroom, "2", "Bob Reyes")

    students = StudentRepository(db_session).list_active(classroom.id, search="santos")

    assert [student.id for student in students] == [target.id]


def test_search_matches_student_id_substring(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    target = _student(db_session, classroom, "25-09759", "Alice Santos")
    _student(db_session, classroom, "25-09999", "Bob Reyes")

    students = StudentRepository(db_session).list_active(classroom.id, search="097")

    assert [student.id for student in students] == [target.id]


@pytest.mark.parametrize(
    ("search", "matching", "decoy"),
    [
        ("100%", "100% sure", "1000 sure"),
        ("A_B", "A_B", "AXB"),
        ("A\\B", "A\\B", "AB"),
    ],
)
def test_search_treats_sql_wildcards_literally(
    db_session: Session, search: str, matching: str, decoy: str
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    target = _student(db_session, classroom, "1", matching)
    _student(db_session, classroom, "2", decoy)

    students = StudentRepository(db_session).list_active(classroom.id, search=search)

    assert [student.id for student in students] == [target.id]


@pytest.mark.parametrize("search", [None, "", "   "])
def test_empty_search_returns_full_active_roster(db_session: Session, search: str | None) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    first = _student(db_session, classroom, "1", "Alice")
    second = _student(db_session, classroom, "2", "Bob")

    students = StudentRepository(db_session).list_active(classroom.id, search=search)

    assert {student.id for student in students} == {first.id, second.id}


def test_get_owned_returns_student_for_owning_user(db_session: Session) -> None:
    owner = _user(db_session)
    student = _student(db_session, _classroom(db_session, owner), "1", "Alice")

    found = StudentRepository(db_session).get_owned(student.id, owner.id)

    assert found is not None
    assert found.id == student.id


def test_get_owned_returns_none_for_other_user(db_session: Session) -> None:
    owner = _user(db_session)
    other = _classroom(db_session, _user(db_session))
    student = _student(db_session, _classroom(db_session, owner), "1", "Alice")

    assert StudentRepository(db_session).get_owned(student.id, other.owner_id) is None


def test_get_owned_returns_none_for_missing_student(db_session: Session) -> None:
    owner = _user(db_session)

    assert StudentRepository(db_session).get_owned(uuid4(), owner.id) is None


def test_get_owned_still_returns_inactive_students(db_session: Session) -> None:
    owner = _user(db_session)
    student = _student(db_session, _classroom(db_session, owner), "1", "Alice", is_active=False)

    found = StudentRepository(db_session).get_owned(student.id, owner.id)

    assert found is not None
    assert found.is_active is False


def test_exists_student_id_is_scoped_to_the_classroom(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    other = _classroom(db_session, owner, name="BSIT3A")
    student = _student(db_session, classroom, "001", "Alice")
    repository = StudentRepository(db_session)

    assert repository.exists_student_id(classroom.id, "001") is True
    assert repository.exists_student_id(other.id, "001") is False
    assert repository.exists_student_id(classroom.id, "999") is False
    assert repository.exists_student_id(classroom.id, "001", exclude_id=student.id) is False


def test_duplicate_student_id_in_same_classroom_violates_constraint(
    db_session: Session,
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "001", "Alice")

    with pytest.raises(IntegrityError):
        StudentRepository(db_session).create(
            Student(classroom_id=classroom.id, student_id="001", full_name="Bob")
        )

    db_session.rollback()


def test_create_and_update_persist(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    repository = StudentRepository(db_session)

    student = repository.create(
        Student(classroom_id=classroom.id, student_id="001", full_name="Alice")
    )
    assert student.id is not None

    student.full_name = "Alice Santos"
    updated = repository.update(student)

    assert updated.full_name == "Alice Santos"
