"""Route-level integration tests for the attendance history endpoint."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import cast
from uuid import UUID

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.attendance_service import AttendanceService


def _attendance_service(db: Session) -> AttendanceService:
    """Service wired to the guarded session, for test setup only."""
    return AttendanceService(
        AttendanceSessionRepository(db),
        AttendanceRecordRepository(db),
        ClassroomRepository(db),
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


def _history(client: TestClient, classroom: Classroom, headers: dict[str, str]) -> Response:
    return cast(
        Response,
        client.get(f"/api/classrooms/{classroom.id}/attendance-history", headers=headers),
    )


def _statuses(body: dict[str, object]) -> dict[str, list[str | None]]:
    rows = body["rows"]
    assert isinstance(rows, list)
    return {row["student_id"]: row["statuses"] for row in rows}


def test_history_requires_a_session(client: TestClient) -> None:
    assert client.get("/api/classrooms/1/attendance-history").status_code == 401


def test_history_returns_the_grid_for_its_owner(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    make_student(classroom.id, owner.id, "2025-002", "Bob Jones")
    _finalize_day(db_session, classroom, owner, date(2026, 3, 1), present=("2025-001",))
    _finalize_day(db_session, classroom, owner, date(2026, 3, 3), present=("2025-002",))
    make_student(classroom.id, owner.id, "2025-003", "Carol Danvers")

    response = _history(client, classroom, headers)

    assert response.status_code == 200
    body = response.json()
    assert body["classroom_id"] == classroom.id
    assert body["classroom_name"] == "BSIT2B"
    assert body["dates"] == ["2026-03-01", "2026-03-03"]
    assert [row["student_name"] for row in body["rows"]] == [
        "Alice Smith",
        "Bob Jones",
        "Carol Danvers",
    ]
    assert _statuses(body) == {
        "2025-001": ["PRESENT", "ABSENT"],
        "2025-002": ["ABSENT", "PRESENT"],
        "2025-003": [None, None],
    }


def test_history_returns_empty_columns_without_finalized_sessions(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = _history(client, classroom, headers)

    assert response.status_code == 200
    body = response.json()
    assert body["classroom_name"] == "BSIT2B"
    assert body["dates"] == []
    assert len(body["rows"]) == 1
    assert body["rows"][0]["statuses"] == []


def test_history_exposes_dates_without_timezone_conversion(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    _finalize_day(
        db_session,
        classroom,
        owner,
        date(2026, 3, 5),
        start_at=datetime(2026, 3, 5, 23, 30, tzinfo=UTC),
    )

    body = _history(client, classroom, headers).json()

    assert body["dates"] == ["2026-03-05"]
    assert all("T" not in value and "+" not in value for value in body["dates"])


def test_history_retains_deactivated_students_with_history(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    _finalize_day(db_session, classroom, owner, date(2026, 3, 1), present=("2025-001",))
    client.post(f"/api/students/{student.id}/deactivate", headers=headers)

    body = _history(client, classroom, headers).json()

    assert len(body["rows"]) == 1
    assert body["rows"][0]["is_active"] is False
    assert body["rows"][0]["statuses"] == ["PRESENT"]


def test_history_excludes_deactivated_students_without_history(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    departed = make_student(classroom.id, owner.id, "2025-002", "Bob Jones")
    client.post(f"/api/students/{departed.id}/deactivate", headers=headers)
    _finalize_day(db_session, classroom, owner, date(2026, 3, 1), present=("2025-001",))

    body = _history(client, classroom, headers).json()

    assert [row["student_id"] for row in body["rows"]] == ["2025-001"]


def test_history_returns_404_for_another_owner(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = _history(client, classroom, auth_headers(other.id))

    assert response.status_code == 404
    assert response.json()["detail"] == "Classroom not found"


def test_history_returns_404_for_missing_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.get(
        "/api/classrooms/999999999/attendance-history", headers=auth_headers(owner.id)
    )

    assert response.status_code == 404


def test_history_rejects_a_non_integer_id(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.get("/api/classrooms/abc/attendance-history", headers=auth_headers(owner.id))

    assert response.status_code == 422
