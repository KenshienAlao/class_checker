"""Route-level integration tests for the student endpoints."""

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import SESSION_COOKIE_NAME, create_session_token
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User

_MISSING_UUID = "00000000-0000-0000-0000-000000000001"

_NO_SESSION_ROUTES = [
    ("get", "/api/classrooms/1/students"),
    ("post", "/api/classrooms/1/students"),
    ("get", f"/api/students/{_MISSING_UUID}"),
    ("patch", f"/api/students/{_MISSING_UUID}"),
    ("post", f"/api/students/{_MISSING_UUID}/deactivate"),
]


@pytest.mark.parametrize(("method", "path"), _NO_SESSION_ROUTES)
def test_student_routes_require_a_session(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


def test_create_student_returns_201(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith", "program": "BSIT"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["student_id"] == "2025-001"
    assert body["full_name"] == "Alice Smith"
    assert body["program"] == "BSIT"
    assert body["is_active"] is True
    assert body["classroom_id"] == classroom.id


def test_create_student_allows_null_program(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith", "program": None},
    )

    assert response.status_code == 201
    assert response.json()["program"] is None


def test_create_student_without_csrf_is_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    headers = {"Cookie": f"{SESSION_COOKIE_NAME}={create_session_token(owner.id)}"}

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=headers,
        json={"student_id": "2025-001", "full_name": "Alice Smith"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"student_id": "", "full_name": "Alice Smith"},
        {"student_id": "   ", "full_name": "Alice Smith"},
        {"student_id": "2025-001", "full_name": ""},
        {"student_id": "2025-001", "full_name": " \t "},
        {"student_id": "2025-001", "full_name": "Alice Smith", "program": "   "},
    ],
)
def test_create_student_rejects_blank_fields(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    payload: dict[str, object],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(owner.id),
        json=payload,
    )

    assert response.status_code == 422


def test_create_student_rejects_extra_fields(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith", "is_active": False},
    )

    assert response.status_code == 422


def test_create_duplicate_student_id_returns_409(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Eve"},
    )

    assert response.status_code == 409


def test_same_student_id_in_different_classrooms_is_allowed(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    first = make_classroom(owner.id, "First")
    second = make_classroom(owner.id, "Second")

    first_response = client.post(
        f"/api/classrooms/{first.id}/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith"},
    )
    second_response = client.post(
        f"/api/classrooms/{second.id}/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201


def test_create_student_in_another_users_classroom_returns_404(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.post(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(other.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith"},
    )

    assert response.status_code == 404


def test_create_student_in_missing_classroom_returns_404(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.post(
        "/api/classrooms/999999999/students",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001", "full_name": "Alice Smith"},
    )

    assert response.status_code == 404


def test_list_students_returns_active_only(
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
    inactive = make_student(classroom.id, owner.id, "2025-002", "Bob Jones")

    response = client.post(f"/api/students/{inactive.id}/deactivate", headers=headers)

    assert response.status_code == 200
    listed = client.get(f"/api/classrooms/{classroom.id}/students", headers=headers).json()
    assert [student["student_id"] for student in listed] == ["2025-001"]


def test_list_students_filters_by_search(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith", "BSIT")
    make_student(classroom.id, owner.id, "2025-002", "Bob Jones", "BSCS")
    url = f"/api/classrooms/{classroom.id}/students"

    all_response = client.get(url, headers=headers)
    by_name = client.get(url, headers=headers, params={"search": "ALICE"})
    by_id = client.get(url, headers=headers, params={"search": "2025-002"})
    none = client.get(url, headers=headers, params={"search": "zzz"})

    assert [student["student_id"] for student in all_response.json()] == [
        "2025-001",
        "2025-002",
    ]
    assert [student["full_name"] for student in by_name.json()] == ["Alice Smith"]
    assert [student["full_name"] for student in by_id.json()] == ["Bob Jones"]
    assert none.json() == []


def test_list_students_rejects_search_over_255_characters(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.get(
        f"/api/classrooms/{classroom.id}/students",
        headers=auth_headers(owner.id),
        params={"search": "a" * 256},
    )

    assert response.status_code == 422


def test_list_students_returns_404_for_another_users_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.get(
        f"/api/classrooms/{classroom.id}/students", headers=auth_headers(other.id)
    )

    assert response.status_code == 404


def test_get_student_returns_owned(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith", "BSIT")

    response = client.get(f"/api/students/{student.id}", headers=auth_headers(owner.id))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(student.id)
    assert body["student_id"] == "2025-001"
    assert body["is_active"] is True


def test_get_student_returns_404_for_another_owner(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.get(f"/api/students/{student.id}", headers=auth_headers(other.id))

    assert response.status_code == 404


def test_get_student_returns_404_for_missing(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    owner = make_user()

    response = client.get(f"/api/students/{_MISSING_UUID}", headers=auth_headers(owner.id))

    assert response.status_code == 404


def test_update_student_partial_update(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith", "BSIT")

    response = client.patch(
        f"/api/students/{student.id}",
        headers=auth_headers(owner.id),
        json={"full_name": "Alice J. Smith"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Alice J. Smith"
    assert body["student_id"] == "2025-001"
    assert body["program"] == "BSIT"


def test_update_student_program_null_clears_it(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith", "BSIT")

    response = client.patch(
        f"/api/students/{student.id}",
        headers=auth_headers(owner.id),
        json={"program": None},
    )

    assert response.status_code == 200
    assert response.json()["program"] is None


def test_update_student_rejects_taken_student_id(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    other = make_student(classroom.id, owner.id, "2025-002", "Bob Jones")

    response = client.patch(
        f"/api/students/{other.id}",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-001"},
    )

    assert response.status_code == 409


def test_update_student_to_new_student_id(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.patch(
        f"/api/students/{student.id}",
        headers=auth_headers(owner.id),
        json={"student_id": "2025-003"},
    )

    assert response.status_code == 200
    assert response.json()["student_id"] == "2025-003"


@pytest.mark.parametrize(
    "payload",
    [
        {"student_id": None},
        {"full_name": None},
        {"student_id": "   "},
        {"program": "   "},
    ],
)
def test_update_student_rejects_invalid_values(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
    payload: dict[str, object],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.patch(
        f"/api/students/{student.id}", headers=auth_headers(owner.id), json=payload
    )

    assert response.status_code == 422


def test_update_student_empty_body_is_rejected(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.patch(f"/api/students/{student.id}", headers=auth_headers(owner.id), json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "No fields to update"


def test_update_student_rejects_extra_fields(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.patch(
        f"/api/students/{student.id}",
        headers=auth_headers(owner.id),
        json={"program": "BSIT", "is_active": False},
    )

    assert response.status_code == 422


def test_update_student_returns_404_for_another_owner(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.patch(
        f"/api/students/{student.id}",
        headers=auth_headers(other.id),
        json={"full_name": "Nope"},
    )

    assert response.status_code == 404


def test_deactivate_student(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.post(f"/api/students/{student.id}/deactivate", headers=auth_headers(owner.id))

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_deactivate_student_is_idempotent(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    url = f"/api/students/{student.id}/deactivate"

    first = client.post(url, headers=headers)
    second = client.post(url, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["is_active"] is False


def test_deactivate_student_is_still_gettable(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    headers = auth_headers(owner.id)
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")
    client.post(f"/api/students/{student.id}/deactivate", headers=headers)

    response = client.get(f"/api/students/{student.id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_deactivate_student_returns_404_for_another_owner(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
    make_student: Callable[..., Student],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")
    student = make_student(classroom.id, owner.id, "2025-001", "Alice Smith")

    response = client.post(f"/api/students/{student.id}/deactivate", headers=auth_headers(other.id))

    assert response.status_code == 404
