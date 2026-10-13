"""Real-database concurrency coverage for the Student Import transaction."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.models.classroom import Classroom
from app.models.user import User
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.classroom_service import ClassroomService
from app.services.import_service import ImportService


def _seed_concurrency_import(test_engine: Any) -> dict[str, Any]:
    with Session(test_engine) as session:
        owner = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
        session.add(owner)
        session.flush()
        classroom = ClassroomService(ClassroomRepository(session)).create(owner.id, "Import C")
        session.commit()

        result: dict[str, Any] = {
            "owner_id": owner.id,
            "classroom_id": classroom.id,
        }
        session.expunge_all()
        return result


def _cleanup_concurrency_import(test_engine: Any, seeded: dict[str, Any]) -> None:
    with Session(test_engine) as session:
        from app.models.student import Student

        session.query(Student).filter(Student.classroom_id == seeded["classroom_id"]).delete(
            synchronize_session=False
        )
        session.query(Classroom).filter(Classroom.id == seeded["classroom_id"]).delete(
            synchronize_session=False
        )
        session.query(User).filter(User.id == seeded["owner_id"]).delete(synchronize_session=False)
        session.commit()


def _workbook_bytes() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Student ID", "Full Name"])
    ws.append(["S1", "Alice"])
    ws.append(["S2", "Bob"])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_concurrent_student_imports_do_not_duplicate_rows(test_engine: Any) -> None:
    seeded = _seed_concurrency_import(test_engine)
    from app.models.student import Student

    content = _workbook_bytes()
    statuses: list[int] = []
    errors: list[str] = []

    def worker() -> None:
        with Session(test_engine) as session:
            repository: Any = StudentRepository(session)
            service = ImportService(
                session,
                repository,
                ClassroomRepository(session),
            )
            # Simulate both workers observing the pre-update roster at the same
            # point in time. The unique constraint remains the final guard.
            repository.list_existing_student_ids = lambda classroom_id: []

            try:
                result = service.import_file(
                    seeded["classroom_id"],
                    seeded["owner_id"],
                    UploadFile(BytesIO(content), filename="r.xlsx"),
                )
                statuses.append(200)
                assert result.created == 2
            except HTTPException as exc:
                statuses.append(exc.status_code)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: worker(), [None, None]))

        assert not errors
        assert sorted(statuses) == [200, 409]

        with Session(test_engine) as session:
            ids = session.scalars(
                select(Student.student_id).where(Student.classroom_id == seeded["classroom_id"])
            ).all()
            assert sorted(ids) == ["S1", "S2"]
    finally:
        _cleanup_concurrency_import(test_engine, seeded)
