"""Integration tests for ``ClassroomRepository`` against PostgreSQL."""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.classroom import Classroom
from app.models.user import User
from app.repositories.classroom_repository import ClassroomRepository


def _user(db: Session, name: str = "Owner") -> User:
    user = User(id=uuid4(), name=name, email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _classroom(db: Session, owner: User, name: str) -> Classroom:
    classroom = Classroom(name=name, owner_id=owner.id)
    db.add(classroom)
    db.flush()
    return classroom


def test_list_by_owner_returns_only_owned_classrooms(db_session: Session) -> None:
    owner = _user(db_session)
    other = _user(db_session, name="Other")
    _classroom(db_session, owner, "Mine")
    _classroom(db_session, other, "Theirs")

    classrooms = ClassroomRepository(db_session).list_by_owner(owner.id)

    assert [classroom.name for classroom in classrooms] == ["Mine"]


def test_list_by_owner_orders_newest_first(db_session: Session) -> None:
    owner = _user(db_session)
    first = _classroom(db_session, owner, "First")
    second = _classroom(db_session, owner, "Second")

    classrooms = ClassroomRepository(db_session).list_by_owner(owner.id)

    assert [classroom.id for classroom in classrooms] == [second.id, first.id]


def test_get_owned_returns_classroom_for_owner(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner, "BSIT2B")

    found = ClassroomRepository(db_session).get_owned(classroom.id, owner.id)

    assert found is not None
    assert found.id == classroom.id


def test_get_owned_returns_none_for_other_owner(db_session: Session) -> None:
    owner = _user(db_session)
    other = _user(db_session, name="Other")
    classroom = _classroom(db_session, owner, "BSIT2B")

    assert ClassroomRepository(db_session).get_owned(classroom.id, other.id) is None


def test_get_owned_returns_none_for_missing_classroom(db_session: Session) -> None:
    owner = _user(db_session)

    assert ClassroomRepository(db_session).get_owned(10**9, owner.id) is None


def test_create_and_update_persist(db_session: Session) -> None:
    owner = _user(db_session)
    repository = ClassroomRepository(db_session)

    classroom = repository.create(Classroom(name="BSIT2B", owner_id=owner.id))
    assert classroom.id is not None

    classroom.name = "BSIT3A"
    updated = repository.update(classroom)

    assert updated.name == "BSIT3A"
