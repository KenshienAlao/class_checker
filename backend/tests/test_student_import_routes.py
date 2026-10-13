"""Route-level integration tests for the student import endpoint."""

from collections.abc import Callable
from io import BytesIO
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.core.security import SESSION_COOKIE_NAME, create_session_token
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.student_repository import StudentRepository


def _workbook_bytes(headers: list[str], rows: list[list[object]] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(headers)
    for r in rows or []:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(
    client: TestClient,
    path: str,
    headers: dict[str, str],
    content: bytes,
    filename: str = "roster.xlsx",
) -> Any:
    files = {
        "file": (
            filename,
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    return client.post(path, headers=headers, files=files)


def test_import_no_session(client: TestClient) -> None:
    content = _workbook_bytes(["Student ID", "Full Name"])
    path = "/api/classrooms/1/students/import"
    response = client.post(path, files={"file": ("r.xlsx", content, "application/octet-stream")})
    assert response.status_code == 401


def test_import_requires_csrf(
    client: TestClient,
    make_user: Callable[[], User],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:

    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    content = _workbook_bytes(["Student ID", "Full Name"])
    headers = {"Cookie": f"{SESSION_COOKIE_NAME}={create_session_token(owner.id)}"}
    response = client.post(
        f"/api/classrooms/{classroom.id}/students/import",
        headers=headers,
        files={"file": ("r.xlsx", content, "application/octet-stream")},
    )
    assert response.status_code == 403


def test_import_missing_classroom_404(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()
    content = _workbook_bytes(["Student ID", "Full Name"])
    response = _upload(
        client, "/api/classrooms/999999/students/import", auth_headers(owner.id), content
    )
    assert response.status_code == 404


def test_import_header_only(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    content = _workbook_bytes(["Student ID", "Full Name"])
    response = _upload(
        client, f"/api/classrooms/{classroom.id}/students/import", auth_headers(owner.id), content
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"created": 0, "skipped": 0, "rejected": []}


def test_import_valid_rows(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    content = _workbook_bytes(
        ["Student ID", "Full Name", "Program"],
        [["  S1  ", "  Alice  ", "  BSIT  "], ["S2", "Bob", None]],
    )
    response = _upload(
        client, f"/api/classrooms/{classroom.id}/students/import", auth_headers(owner.id), content
    )
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    assert body["rejected"] == []


def test_import_missing_header_400(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    content = _workbook_bytes(["Full Name"])
    response = _upload(
        client, f"/api/classrooms/{classroom.id}/students/import", auth_headers(owner.id), content
    )
    assert response.status_code == 400


def test_import_malformed(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    r = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        b"junk",
        filename="x.xlsx",
    )
    assert r.status_code == 400


def test_import_1000_rows(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    rows: list[list[object]] = [[f"S{i}", f"N{i}"] for i in range(1000)]
    r = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        _workbook_bytes(["Student ID", "Full Name"], rows),
    )
    assert r.status_code == 200
    assert r.json()["created"] == 1000


def test_import_reordered_headers(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    content = _workbook_bytes(["FULL NAME", "program", "STUDENT ID"], [["Alice", "BSIT", "S1"]])
    r = _upload(
        client, f"/api/classrooms/{classroom.id}/students/import", auth_headers(owner.id), content
    )
    assert r.status_code == 200
    assert r.json()["skipped"] == 0


def test_import_overlong_program(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    content = _workbook_bytes(["Student ID", "Full Name", "Program"], [["S1", "Alice", "P" * 256]])
    r = _upload(
        client, f"/api/classrooms/{classroom.id}/students/import", auth_headers(owner.id), content
    )
    assert r.status_code == 422


def test_import_inactive_duplicate(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[[int, UUID, str, str, str | None], Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    st = make_student(classroom.id, owner.id, "S1", "Existing", None)
    # deactivate
    client.post(f"/api/students/{st.id}/deactivate", headers=auth_headers(owner.id))
    content = _workbook_bytes(["Student ID", "Full Name"], [["S1", "Alice"]])
    content = _workbook_bytes(["FULL NAME", "program", "STUDENT ID"], [["Alice", "BSIT", "S1"]])
    r = _upload(
        client, f"/api/classrooms/{classroom.id}/students/import", auth_headers(owner.id), content
    )
    assert r.status_code == 409


def test_import_over_5mb(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    big = b"x" * (5 * 1024 * 1024 + 100)
    r = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        big,
        filename="big.xlsx",
    )
    assert r.status_code == 400


def test_import_preserves_attendance_on_success(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[[int, UUID, str, str, str | None], Student],
) -> None:
    from app.repositories.attendance_record_repository import AttendanceRecordRepository
    from app.repositories.attendance_session_repository import AttendanceSessionRepository

    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    make_student(classroom.id, owner.id, "S0", "Existing", None)
    headers = auth_headers(owner.id)
    session_response = client.post(
        f"/api/classrooms/{classroom.id}/attendance-sessions", headers=headers
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["session_id"]

    sess_repo = AttendanceSessionRepository(db_session)
    rec_repo = AttendanceRecordRepository(db_session)
    before_sessions = sess_repo.get_owned(session_id, owner.id)
    before_records = rec_repo.list_by_session(session_id)
    before_ids = [(r.id, r.student_id, r.status) for r in before_records]

    content = _workbook_bytes(["Student ID", "Full Name"], [["SNEW", "New"]])
    r = _upload(client, f"/api/classrooms/{classroom.id}/students/import", headers, content)
    assert r.status_code == 200

    after_sessions = sess_repo.get_owned(session_id, owner.id)
    after_records = rec_repo.list_by_session(session_id)
    after_ids = [(r.id, r.student_id, r.status) for r in after_records]
    assert before_ids == after_ids
    assert before_sessions is not None and after_sessions is not None
    assert before_sessions.id == after_sessions.id


def test_import_preserves_attendance_on_rejection(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[[int, UUID, str, str, str | None], Student],
) -> None:
    from app.repositories.attendance_record_repository import AttendanceRecordRepository
    from app.repositories.attendance_session_repository import AttendanceSessionRepository

    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    make_student(classroom.id, owner.id, "S0", "Existing", None)
    headers = auth_headers(owner.id)
    session_response = client.post(
        f"/api/classrooms/{classroom.id}/attendance-sessions", headers=headers
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["session_id"]

    AttendanceSessionRepository(db_session)
    rec_repo = AttendanceRecordRepository(db_session)
    before_records = [(r.id, r.student_id, r.status) for r in rec_repo.list_by_session(session_id)]

    # duplicate (S0 exists)
    content = _workbook_bytes(["Student ID", "Full Name"], [["S0", "Dup"]])
    r = _upload(client, f"/api/classrooms/{classroom.id}/students/import", headers, content)
    assert r.status_code == 409

    after_records = [(r.id, r.student_id, r.status) for r in rec_repo.list_by_session(session_id)]
    assert before_records == after_records


def test_import_1001_rows_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    r = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        _workbook_bytes(["Student ID", "Full Name"], [[f"S{i}", f"N{i}"] for i in range(1001)]),
    )

    assert r.status_code == 400


def test_import_too_long_student_id_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    r = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        _workbook_bytes(["Student ID", "Full Name"], [["S" * 65, "Alice"]]),
    )

    assert r.status_code == 422


def test_import_too_long_full_name_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    r = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        _workbook_bytes(["Student ID", "Full Name"], [["S1", "N" * 256]]),
    )

    assert r.status_code == 422


def test_import_missing_classroom_is_unauthorized_to_other_owner(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[[int, UUID, str, str, str | None], Student],
) -> None:
    owner = make_user()
    stranger = make_user()
    classroom = make_classroom(owner.id, "C")
    make_student(classroom.id, owner.id, "S0", "Existing", None)
    before = [
        student.student_id for student in StudentRepository(db_session).list_active(classroom.id)
    ]

    response = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(stranger.id),
        _workbook_bytes(["Student ID", "Full Name"], [["S9", "Alice"]]),
    )

    assert response.status_code == 404
    after = [
        student.student_id for student in StudentRepository(db_session).list_active(classroom.id)
    ]
    assert after == before


def test_import_existing_duplicate_leaves_roster_unchanged(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[[int, UUID, str, str, str | None], Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    make_student(classroom.id, owner.id, "S0", "Existing", None)
    before = [
        student.student_id for student in StudentRepository(db_session).list_active(classroom.id)
    ]

    response = _upload(
        client,
        f"/api/classrooms/{classroom.id}/students/import",
        auth_headers(owner.id),
        _workbook_bytes(["Student ID", "Full Name"], [["S0", "Duplicate"], ["S1", "Alice"]]),
    )

    assert response.status_code == 409
    after = [
        student.student_id for student in StudentRepository(db_session).list_active(classroom.id)
    ]
    assert after == before


def test_import_unauthenticated_request_creates_no_students(
    client: TestClient,
    db_session: Session,
    make_user: Callable[[], User],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[[int, UUID, str, str, str | None], Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "C")
    make_student(classroom.id, owner.id, "S0", "Existing", None)
    before = [
        student.student_id for student in StudentRepository(db_session).list_active(classroom.id)
    ]

    response = client.post(
        f"/api/classrooms/{classroom.id}/students/import",
        files={
            "file": (
                "r.xlsx",
                _workbook_bytes(["Student ID", "Full Name"], [["S1", "Alice"]]),
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 401
    after = [
        student.student_id for student in StudentRepository(db_session).list_active(classroom.id)
    ]
    assert after == before
