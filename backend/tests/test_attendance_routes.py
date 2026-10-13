"""Route-level integration tests for the attendance session endpoints."""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import SESSION_COOKIE_NAME, create_session_token
from app.models.attendance_record import AttendanceRecord
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.attendance_service import AttendanceService

_NO_SESSION_ROUTES = [
    ("post", "/api/classrooms/1/attendance-sessions"),
    ("get", "/api/attendance-sessions/1"),
    ("post", "/api/attendance-sessions/1/scan"),
    ("post", "/api/attendance-sessions/1/manual"),
    ("post", "/api/attendance-sessions/1/finalize"),
]

# The scan and manual routes converge on mark_present, so shared behavior is
# verified against both rather than duplicated per route.
_ENDPOINTS = ("scan", "manual")

_NON_INTEGER_ROUTES = [
    ("post", "/api/classrooms/abc/attendance-sessions", None),
    ("get", "/api/attendance-sessions/abc", None),
    ("post", "/api/attendance-sessions/abc/scan", {"student_id": "2025-001"}),
    ("post", "/api/attendance-sessions/abc/manual", {"student_id": "2025-001"}),
    ("post", "/api/attendance-sessions/abc/finalize", None),
]


@pytest.mark.parametrize(("method", "path"), _NO_SESSION_ROUTES)
def test_attendance_routes_require_a_session(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


def _create_session(client: TestClient, classroom: Classroom, headers: dict[str, str]) -> Response:
    return cast(
        Response,
        client.post(f"/api/classrooms/{classroom.id}/attendance-sessions", headers=headers),
    )


def _service(db_session: Session) -> AttendanceService:
    """Service wired to the guarded session, for test setup only."""
    return AttendanceService(
        AttendanceSessionRepository(db_session),
        AttendanceRecordRepository(db_session),
        ClassroomRepository(db_session),
        StudentRepository(db_session),
    )


def test_create_session_returns_201_with_the_review_schema(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    make_student(classroom.id, owner.id, "2025-002", "Bob Jones")

    response = _create_session(client, classroom, auth_headers(owner.id))

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] > 0
    assert body["classroom_id"] == classroom.id
    assert body["classroom_name"] == "BSIT2B"
    assert body["status"] == "ACTIVE"
    assert body["started_at"] is not None
    assert body["finalized_at"] is None
    assert (body["present_count"], body["pending_count"], body["absent_count"]) == (0, 2, 0)
    assert [record["student_id"] for record in body["records"]] == ["2025-001", "2025-002"]
    assert all(record["status"] == "PENDING" for record in body["records"])
    assert all(record["method"] is None for record in body["records"])
    assert all(record["marked_at"] is None for record in body["records"])


def test_get_session_returns_the_review_for_its_owner(
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
    created = _create_session(client, classroom, headers).json()

    response = client.get(f"/api/attendance-sessions/{created['session_id']}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == created["session_id"]
    assert body["classroom_name"] == "BSIT2B"
    assert (body["present_count"], body["pending_count"], body["absent_count"]) == (0, 1, 0)
    assert [record["student_name"] for record in body["records"]] == ["Alice Smith"]


def test_get_session_returns_404_for_another_owner(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    created = _create_session(client, classroom, auth_headers(owner.id)).json()

    response = client.get(
        f"/api/attendance-sessions/{created['session_id']}", headers=auth_headers(other.id)
    )

    assert response.status_code == 404


def test_get_session_returns_404_for_missing(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.get("/api/attendance-sessions/999999999", headers=auth_headers(owner.id))

    assert response.status_code == 404


def test_create_session_returns_404_for_another_owners_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = _create_session(client, classroom, auth_headers(other.id))

    assert response.status_code == 404


def test_create_session_returns_404_for_missing_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.post(
        "/api/classrooms/999999999/attendance-sessions", headers=auth_headers(owner.id)
    )

    assert response.status_code == 404


def test_create_session_conflicts_with_an_active_session(
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
    assert _create_session(client, classroom, headers).status_code == 201

    response = _create_session(client, classroom, headers)

    assert response.status_code == 409


def test_create_session_without_active_students_returns_409(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    inactive = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    client.post(f"/api/students/{inactive.id}/deactivate", headers=headers)

    response = _create_session(client, classroom, headers)

    assert response.status_code == 409


def test_create_session_without_csrf_is_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    headers = {"Cookie": f"{SESSION_COOKIE_NAME}={create_session_token(owner.id)}"}

    response = _create_session(client, classroom, headers)

    assert response.status_code == 403


def test_scan_marks_a_student_present(
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]

    response = client.post(
        f"/api/attendance-sessions/{session_id}/scan",
        headers=headers,
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == "2025-001"
    assert body["student_name"] == "Alice Smith"
    assert body["status"] == "PRESENT"
    assert body["method"] == "QR"
    assert body["marked_at"] is not None
    assert body["already_marked"] is False


def test_manual_marks_a_student_present_as_manual(
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]

    response = client.post(
        f"/api/attendance-sessions/{session_id}/manual",
        headers=headers,
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PRESENT"
    assert body["method"] == "MANUAL"
    assert body["already_marked"] is False


def test_duplicate_scan_is_idempotent_and_preserves_the_original(
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    url = f"/api/attendance-sessions/{session_id}/scan"
    original = client.post(url, headers=headers, json={"student_id": "2025-001"}).json()

    duplicate = client.post(url, headers=headers, json={"student_id": "2025-001"}).json()
    after_manual = client.post(
        f"/api/attendance-sessions/{session_id}/manual",
        headers=headers,
        json={"student_id": "2025-001"},
    ).json()

    assert duplicate["already_marked"] is True
    assert duplicate["status"] == "PRESENT"
    assert duplicate["method"] == "QR"
    assert duplicate["marked_at"] == original["marked_at"]
    # The route determines the method; a later manual input cannot overwrite QR.
    assert after_manual["already_marked"] is True
    assert after_manual["method"] == "QR"
    assert after_manual["marked_at"] == original["marked_at"]


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_marking_returns_404_for_an_unknown_student(
    client: TestClient,
    endpoint: str,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    session_id = _create_session(client, classroom, headers).json()["session_id"]

    response = client.post(
        f"/api/attendance-sessions/{session_id}/{endpoint}",
        headers=headers,
        json={"student_id": "does-not-exist"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_marking_returns_404_for_another_owners_session(
    client: TestClient,
    endpoint: str,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    session_id = _create_session(client, classroom, auth_headers(owner.id)).json()["session_id"]

    response = client.post(
        f"/api/attendance-sessions/{session_id}/{endpoint}",
        headers=auth_headers(other.id),
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_marking_returns_404_for_a_missing_session(
    client: TestClient,
    endpoint: str,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.post(
        f"/api/attendance-sessions/999999999/{endpoint}",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_marking_returns_409_for_a_finalized_session(
    client: TestClient,
    endpoint: str,
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    _service(db_session).finalize_session(session_id, owner.id)

    response = client.post(
        f"/api/attendance-sessions/{session_id}/{endpoint}",
        headers=headers,
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_marking_returns_409_for_an_absent_record(
    client: TestClient,
    endpoint: str,
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    record = db_session.scalar(
        select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    )
    assert record is not None
    record.status = "ABSENT"
    db_session.flush()

    response = client.post(
        f"/api/attendance-sessions/{session_id}/{endpoint}",
        headers=headers,
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
def test_marking_without_csrf_is_rejected(
    client: TestClient,
    endpoint: str,
    make_user: Callable[[], User],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    session_id = _create_session(client, classroom, auth_headers(owner.id)).json()["session_id"]
    headers = {"Cookie": f"{SESSION_COOKIE_NAME}={create_session_token(owner.id)}"}

    response = client.post(
        f"/api/attendance-sessions/{session_id}/{endpoint}",
        headers=headers,
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("endpoint", _ENDPOINTS)
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"student_id": "   "},
        {"student_id": "2025-001", "method": "MANUAL"},
    ],
)
def test_marking_rejects_an_invalid_body(
    client: TestClient,
    endpoint: str,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
    payload: dict[str, str],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    session_id = _create_session(client, classroom, headers).json()["session_id"]

    response = client.post(
        f"/api/attendance-sessions/{session_id}/{endpoint}", headers=headers, json=payload
    )

    assert response.status_code == 422


def test_finalize_returns_200_with_counts(
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
    make_student(classroom.id, owner.id, "2025-002", "Bob Jones")
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    client.post(
        f"/api/attendance-sessions/{session_id}/scan",
        headers=headers,
        json={"student_id": "2025-001"},
    )

    response = client.post(f"/api/attendance-sessions/{session_id}/finalize", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["status"] == "FINALIZED"
    assert body["present_count"] == 1
    assert body["absent_count"] == 1
    assert body["finalized_at"] is not None


def test_finalize_sweeps_pending_records_to_absent(
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
    make_student(classroom.id, owner.id, "2025-002", "Bob Jones")
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    client.post(
        f"/api/attendance-sessions/{session_id}/scan",
        headers=headers,
        json={"student_id": "2025-001"},
    )
    client.post(f"/api/attendance-sessions/{session_id}/finalize", headers=headers)

    review = client.get(f"/api/attendance-sessions/{session_id}", headers=headers).json()

    assert review["status"] == "FINALIZED"
    assert (review["present_count"], review["pending_count"], review["absent_count"]) == (1, 0, 1)
    statuses = {record["student_id"]: record["status"] for record in review["records"]}
    assert statuses == {"2025-001": "PRESENT", "2025-002": "ABSENT"}


def test_finalize_an_already_finalized_session_returns_409(
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    assert (
        client.post(f"/api/attendance-sessions/{session_id}/finalize", headers=headers).status_code
        == 200
    )

    response = client.post(f"/api/attendance-sessions/{session_id}/finalize", headers=headers)

    assert response.status_code == 409


def test_finalize_returns_404_for_another_owners_session(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    session_id = _create_session(client, classroom, auth_headers(owner.id)).json()["session_id"]

    response = client.post(
        f"/api/attendance-sessions/{session_id}/finalize", headers=auth_headers(other.id)
    )

    assert response.status_code == 404


def test_finalize_returns_404_for_a_missing_session(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.post(
        "/api/attendance-sessions/999999999/finalize", headers=auth_headers(owner.id)
    )

    assert response.status_code == 404


def test_finalize_without_csrf_is_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    session_id = _create_session(client, classroom, auth_headers(owner.id)).json()["session_id"]
    headers = {"Cookie": f"{SESSION_COOKIE_NAME}={create_session_token(owner.id)}"}

    response = client.post(f"/api/attendance-sessions/{session_id}/finalize", headers=headers)

    assert response.status_code == 403


def test_duplicate_manual_is_idempotent(
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
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    url = f"/api/attendance-sessions/{session_id}/manual"
    original = client.post(url, headers=headers, json={"student_id": "2025-001"}).json()

    duplicate = client.post(url, headers=headers, json={"student_id": "2025-001"}).json()

    assert duplicate["already_marked"] is True
    assert duplicate["status"] == "PRESENT"
    assert duplicate["method"] == "MANUAL"
    assert duplicate["marked_at"] == original["marked_at"]


def test_deactivated_student_remains_in_the_roster_snapshot(
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
    departed = make_student(classroom.id, owner.id, "2025-002", "Bob Jones")
    session_id = _create_session(client, classroom, headers).json()["session_id"]
    client.post(f"/api/students/{departed.id}/deactivate", headers=headers)

    marked = client.post(
        f"/api/attendance-sessions/{session_id}/scan",
        headers=headers,
        json={"student_id": "2025-002"},
    )

    assert marked.status_code == 200
    assert marked.json()["status"] == "PRESENT"
    review = client.get(f"/api/attendance-sessions/{session_id}", headers=headers).json()
    statuses = {record["student_id"]: record["status"] for record in review["records"]}
    assert statuses == {"2025-001": "PENDING", "2025-002": "PRESENT"}


def test_a_new_session_can_be_created_after_finalization(
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
    first_id = _create_session(client, classroom, headers).json()["session_id"]
    assert (
        client.post(f"/api/attendance-sessions/{first_id}/finalize", headers=headers).status_code
        == 200
    )

    response = _create_session(client, classroom, headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["session_id"] != first_id


def test_review_records_are_ordered_by_student_name(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Zoe Adams")
    make_student(classroom.id, owner.id, "2025-002", "Alice Brown")

    body = _create_session(client, classroom, headers).json()

    assert [record["student_name"] for record in body["records"]] == ["Alice Brown", "Zoe Adams"]


@pytest.mark.parametrize(("method", "path", "payload"), _NON_INTEGER_ROUTES)
def test_session_routes_reject_a_non_integer_id(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    method: str,
    path: str,
    payload: dict[str, str] | None,
) -> None:
    owner = make_user()

    response = client.request(method, path, headers=auth_headers(owner.id), json=payload)

    assert response.status_code == 422
