"""Route-level integration tests for the classroom endpoints."""

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.security import SESSION_COOKIE_NAME, create_session_token
from app.models.classroom import Classroom
from app.models.user import User

_NO_SESSION_ROUTES = [
    ("get", "/api/classrooms"),
    ("post", "/api/classrooms"),
    ("get", "/api/classrooms/1"),
    ("patch", "/api/classrooms/1"),
]


@pytest.mark.parametrize(("method", "path"), _NO_SESSION_ROUTES)
def test_classroom_routes_require_a_session(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


def test_create_classroom_returns_201(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    user = make_user()

    response = client.post(
        "/api/classrooms", headers=auth_headers(user.id), json={"name": "BSIT2B"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "BSIT2B"
    assert isinstance(body["id"], int)
    assert "created_at" in body
    assert "updated_at" in body
    assert "owner_id" not in body


def test_create_classroom_without_csrf_is_rejected(
    client: TestClient,
    make_user: Callable[[], User],
) -> None:
    user = make_user()
    headers = {"Cookie": f"{SESSION_COOKIE_NAME}={create_session_token(user.id)}"}

    response = client.post("/api/classrooms", headers=headers, json={"name": "BSIT2B"})

    assert response.status_code == 403


@pytest.mark.parametrize("name", ["", "   ", "\t"])
def test_create_classroom_rejects_blank_name(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    name: str,
) -> None:
    user = make_user()

    response = client.post("/api/classrooms", headers=auth_headers(user.id), json={"name": name})

    assert response.status_code == 422


def test_create_classroom_rejects_extra_fields(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    user = make_user()

    response = client.post(
        "/api/classrooms",
        headers=auth_headers(user.id),
        json={"name": "BSIT2B", "owner_id": 1},
    )

    assert response.status_code == 422


def test_list_returns_only_owned_classrooms(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    other = make_user()
    make_classroom(owner.id, "Mine")
    make_classroom(owner.id, "Also mine")
    make_classroom(other.id, "Theirs")

    response = client.get("/api/classrooms", headers=auth_headers(owner.id))

    assert response.status_code == 200
    assert [classroom["name"] for classroom in response.json()] == ["Also mine", "Mine"]


def test_get_returns_owned_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.get(f"/api/classrooms/{classroom.id}", headers=auth_headers(owner.id))

    assert response.status_code == 200
    assert response.json()["name"] == "BSIT2B"


def test_get_returns_404_for_another_users_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.get(f"/api/classrooms/{classroom.id}", headers=auth_headers(other.id))

    assert response.status_code == 404


def test_get_returns_404_for_missing_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
) -> None:
    user = make_user()

    response = client.get("/api/classrooms/999999999", headers=auth_headers(user.id))

    assert response.status_code == 404


def test_rename_updates_the_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.patch(
        f"/api/classrooms/{classroom.id}",
        headers=auth_headers(owner.id),
        json={"name": "BSIT3A"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "BSIT3A"


def test_rename_rejects_blank_name(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.patch(
        f"/api/classrooms/{classroom.id}",
        headers=auth_headers(owner.id),
        json={"name": "   "},
    )

    assert response.status_code == 422


def test_rename_requires_a_name(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.patch(
        f"/api/classrooms/{classroom.id}", headers=auth_headers(owner.id), json={}
    )

    assert response.status_code == 422


def test_patch_returns_404_for_another_users_classroom(
    client: TestClient,
    make_user: Callable[[], User],
    auth_headers: Callable[[UUID], dict[str, str]],
    make_classroom: Callable[[UUID, str], Classroom],
) -> None:
    owner = make_user()
    other = make_user()
    classroom = make_classroom(owner.id, "BSIT2B")

    response = client.patch(
        f"/api/classrooms/{classroom.id}",
        headers=auth_headers(other.id),
        json={"name": "Nope"},
    )

    assert response.status_code == 404


def test_openapi_lists_classroom_and_student_paths(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert {"get", "post"} <= set(paths["/api/classrooms"])
    assert {"get", "patch"} <= set(paths["/api/classrooms/{id}"])
    assert set(paths["/api/classrooms/{id}/students"]) == {"get", "post"}
    assert set(paths["/api/students/{id}"]) == {"get", "patch"}
    assert set(paths["/api/students/{id}/deactivate"]) == {"post"}
