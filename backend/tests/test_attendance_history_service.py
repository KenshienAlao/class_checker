"""Integration tests for ``AttendanceHistoryService`` against PostgreSQL."""

from datetime import UTC, date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.attendance_history_service import (
    AttendanceHistoryGrid,
    AttendanceHistoryService,
)
from app.services.attendance_service import AttendanceService


def _owner(db: Session, name: str = "Owner") -> User:
    user = User(id=uuid4(), name=name, email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _classroom(db: Session, owner: User, name: str = "BSIT2B") -> Classroom:
    return ClassroomRepository(db).create(Classroom(name=name, owner_id=owner.id))


def _student(
    db: Session, classroom: Classroom, student_id: str, full_name: str, *, active: bool = True
) -> Student:
    return StudentRepository(db).create(
        Student(
            classroom_id=classroom.id,
            student_id=student_id,
            full_name=full_name,
            is_active=active,
        )
    )


def _attendance_service(db: Session) -> AttendanceService:
    return AttendanceService(
        AttendanceSessionRepository(db),
        AttendanceRecordRepository(db),
        ClassroomRepository(db),
        StudentRepository(db),
    )


def _history_service(db: Session) -> AttendanceHistoryService:
    return AttendanceHistoryService(
        ClassroomRepository(db),
        AttendanceSessionRepository(db),
        AttendanceRecordRepository(db),
        StudentRepository(db),
    )


def _finalize_day(
    db: Session,
    classroom: Classroom,
    owner: User,
    day: date,
    present: tuple[str, ...] = (),
    *,
    start_at: datetime | None = None,
) -> None:
    """Create, optionally mark, and finalize a session dated ``day``."""
    service = _attendance_service(db)
    session = service.create_session(classroom.id, owner.id)
    session.started_at = start_at or datetime(day.year, day.month, day.day, 8, 0, tzinfo=UTC)
    db.commit()
    for business_id in present:
        service.mark_present(session.id, owner.id, student_id=business_id, method="QR")
    service.finalize_session(session.id, owner.id)


def _statuses(grid: AttendanceHistoryGrid) -> dict[str, list[str | None]]:
    return {row.student_id: row.statuses for row in grid.rows}


def test_grid_maps_present_and_absent_cells(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    _student(db_session, classroom, "2", "Grace")
    _student(db_session, classroom, "3", "Linus")
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1", "2"))

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert isinstance(grid, AttendanceHistoryGrid)
    assert grid.classroom_id == classroom.id
    assert grid.classroom_name == "BSIT2B"
    assert grid.dates == [day]
    assert _statuses(grid) == {
        "1": ["PRESENT"],
        "2": ["PRESENT"],
        "3": ["ABSENT"],
    }


def test_grid_orders_columns_chronologically_and_rows_by_name(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "2", "Zoe")
    _student(db_session, classroom, "1", "Ada")
    earlier = date(2026, 3, 1)
    later = date(2026, 3, 3)
    _finalize_day(db_session, classroom, owner, later)
    _finalize_day(db_session, classroom, owner, earlier)

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == [earlier, later]
    assert [row.student_name for row in grid.rows] == ["Ada", "Zoe"]


def test_grid_excludes_active_sessions(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1",))
    _attendance_service(db_session).create_session(classroom.id, owner.id)

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == [day]
    assert _statuses(grid) == {"1": ["PRESENT"]}


def test_grid_merges_same_date_sessions_with_present_precedence(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    _student(db_session, classroom, "2", "Grace")
    _student(db_session, classroom, "3", "Linus")
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1",))
    _finalize_day(db_session, classroom, owner, day, present=("2",))

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == [day]
    assert _statuses(grid) == {
        "1": ["PRESENT"],
        "2": ["PRESENT"],
        "3": ["ABSENT"],
    }


def test_grid_retains_deactivated_students_with_history(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    student = _student(db_session, classroom, "1", "Ada")
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1",))
    student.is_active = False
    db_session.commit()

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert len(grid.rows) == 1
    assert grid.rows[0].student_id == "1"
    assert grid.rows[0].is_active is False
    assert grid.rows[0].statuses == ["PRESENT"]


def test_grid_excludes_deactivated_students_without_history(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    _student(db_session, classroom, "2", "Grace", active=False)
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1",))

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert [row.student_id for row in grid.rows] == ["1"]


def test_grid_shows_a_blank_cell_for_a_student_added_after_a_session(
    db_session: Session,
) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1",))
    _student(db_session, classroom, "2", "Grace")

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == [day]
    assert _statuses(grid) == {"1": ["PRESENT"], "2": [None]}


def test_grid_handles_no_finalized_sessions(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == []
    assert len(grid.rows) == 1
    assert grid.rows[0].statuses == []


def test_grid_uses_the_utc_calendar_date(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    _finalize_day(
        db_session,
        classroom,
        owner,
        date(2026, 3, 5),
        start_at=datetime(2026, 3, 5, 23, 30, tzinfo=UTC),
    )

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == [date(2026, 3, 5)]


def test_grid_normalizes_a_non_utc_timestamp_to_the_utc_date(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    # 2026-03-06 01:30 +05:00 is 2026-03-05 20:30 UTC.
    _finalize_day(
        db_session,
        classroom,
        owner,
        date(2026, 3, 5),
        start_at=datetime(2026, 3, 6, 1, 30, tzinfo=timezone(timedelta(hours=5))),
    )

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == [date(2026, 3, 5)]


def test_grid_is_scoped_to_the_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    other = _classroom(db_session, owner, name="BSIT3A")
    _student(db_session, classroom, "1", "Ada")
    _student(db_session, other, "2", "Grace")
    _finalize_day(db_session, other, owner, date(2026, 3, 2), present=("2",))

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert grid.dates == []
    assert [row.student_id for row in grid.rows] == ["1"]


def test_grid_returns_404_for_unowned_and_missing_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    other = _owner(db_session, name="Other")
    classroom = _classroom(db_session, other)
    service = _history_service(db_session)

    for classroom_id in (classroom.id, 10**9):
        with pytest.raises(HTTPException) as exc:
            service.build_grid(classroom_id, owner.id)

        assert exc.value.status_code == 404
        assert exc.value.detail == "Classroom not found"


def test_grid_is_read_only(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    student = _student(db_session, classroom, "1", "Ada")
    day = date(2026, 3, 1)
    _finalize_day(db_session, classroom, owner, day, present=("1",))
    commits: list[int] = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    grid = _history_service(db_session).build_grid(classroom.id, owner.id)

    assert commits == []
    assert grid.rows[0].statuses == ["PRESENT"]
    persisted = AttendanceRecordRepository(db_session).list_finalized_for_classroom(classroom.id)
    assert len(persisted) == 1
    assert persisted[0].student_id == student.id
    assert persisted[0].status == "PRESENT"
