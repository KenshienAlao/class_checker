"""Integration tests for ``AttendanceSessionRepository`` against PostgreSQL."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance_session import AttendanceSession
from app.models.classroom import Classroom
from app.models.user import User
from app.repositories.attendance_session_repository import AttendanceSessionRepository


def _user(db: Session, name: str = "Owner") -> User:
    user = User(id=uuid4(), name=name, email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _classroom(db: Session, owner: User, name: str = "BSIT2B") -> Classroom:
    classroom = Classroom(name=name, owner_id=owner.id)
    db.add(classroom)
    db.flush()
    return classroom


def _session(db: Session, classroom: Classroom, status: str = "ACTIVE") -> AttendanceSession:
    session = AttendanceSession(classroom_id=classroom.id, status=status)
    db.add(session)
    db.flush()
    return session


def test_get_owned_returns_session_for_owning_user(db_session: Session) -> None:
    owner = _user(db_session)
    session = _session(db_session, _classroom(db_session, owner))

    found = AttendanceSessionRepository(db_session).get_owned(session.id, owner.id)

    assert found is not None
    assert found.id == session.id


def test_get_owned_returns_none_for_other_owner(db_session: Session) -> None:
    owner = _user(db_session)
    other = _user(db_session, name="Other")
    session = _session(db_session, _classroom(db_session, owner))

    assert AttendanceSessionRepository(db_session).get_owned(session.id, other.id) is None


def test_get_owned_returns_none_for_missing_session(db_session: Session) -> None:
    owner = _user(db_session)

    assert AttendanceSessionRepository(db_session).get_owned(10**9, owner.id) is None


def test_get_owned_for_update_returns_the_owner_session(db_session: Session) -> None:
    owner = _user(db_session)
    session = _session(db_session, _classroom(db_session, owner))

    found = AttendanceSessionRepository(db_session).get_owned_for_update(session.id, owner.id)

    assert found is not None
    assert found.id == session.id


def test_get_owned_for_update_returns_none_for_other_owner(db_session: Session) -> None:
    owner = _user(db_session)
    other = _user(db_session, name="Other")
    session = _session(db_session, _classroom(db_session, owner))

    found = AttendanceSessionRepository(db_session).get_owned_for_update(session.id, other.id)

    assert found is None


def test_get_active_for_classroom_returns_the_active_session(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)

    found = AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id)

    assert found is not None
    assert found.id == session.id


def test_get_active_for_classroom_returns_none_without_an_active_session(
    db_session: Session,
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)

    assert AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) is None


def test_get_active_for_classroom_ignores_finalized_sessions(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    _session(db_session, classroom, status="FINALIZED")

    assert AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) is None


def test_get_active_for_classroom_is_scoped_to_the_classroom(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    other = _classroom(db_session, owner, name="BSIT3A")
    _session(db_session, other)

    assert AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) is None


def test_add_flushes_without_committing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    commits: list[int] = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    session = AttendanceSessionRepository(db_session).add(
        AttendanceSession(classroom_id=classroom.id)
    )

    assert session.id is not None
    assert commits == []


def test_add_makes_the_session_queryable_within_the_transaction(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    repository = AttendanceSessionRepository(db_session)

    session = repository.add(AttendanceSession(classroom_id=classroom.id))

    found = repository.get_active_for_classroom(classroom.id)
    assert found is not None
    assert found.id == session.id


def test_second_active_session_in_same_classroom_violates_constraint(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    repository = AttendanceSessionRepository(db_session)
    repository.add(AttendanceSession(classroom_id=classroom.id))

    with pytest.raises(IntegrityError):
        repository.add(AttendanceSession(classroom_id=classroom.id))

    db_session.rollback()


def test_finalized_session_does_not_block_a_new_active_session(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    repository = AttendanceSessionRepository(db_session)
    repository.add(AttendanceSession(classroom_id=classroom.id, status="FINALIZED"))

    active = repository.add(AttendanceSession(classroom_id=classroom.id))

    assert active.id is not None
    assert repository.get_active_for_classroom(classroom.id) is not None


def test_list_finalized_for_classroom_returns_finalized_sessions_oldest_first(
    db_session: Session,
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    later = _session(db_session, classroom, status="FINALIZED")
    later.started_at = datetime(2026, 3, 5, 8, 0, tzinfo=UTC)
    earlier = _session(db_session, classroom, status="FINALIZED")
    earlier.started_at = datetime(2026, 3, 1, 8, 0, tzinfo=UTC)
    db_session.flush()
    _session(db_session, classroom, status="ACTIVE")

    sessions = AttendanceSessionRepository(db_session).list_finalized_for_classroom(classroom.id)

    assert [item.id for item in sessions] == [earlier.id, later.id]


def test_list_finalized_for_classroom_is_scoped_to_the_classroom(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    other = _classroom(db_session, owner, name="BSIT3A")
    _session(db_session, other, status="FINALIZED")

    assert AttendanceSessionRepository(db_session).list_finalized_for_classroom(classroom.id) == []
