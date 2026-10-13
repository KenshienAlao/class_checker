"""Real-database concurrency tests for attendance state transitions."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.attendance_service import AttendanceService
from app.services.classroom_service import ClassroomService
from app.services.student_service import StudentService


def _make_service(session: Session) -> AttendanceService:
    return AttendanceService(
        AttendanceSessionRepository(session),
        AttendanceRecordRepository(session),
        ClassroomRepository(session),
        StudentRepository(session),
    )


def _seed_session(
    test_engine: Any,
    student_count: int = 1,
) -> dict[str, Any]:
    with Session(test_engine) as session:
        owner = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
        session.add(owner)
        session.flush()

        classroom = ClassroomService(ClassroomRepository(session)).create(owner.id, "BSIT2B")
        student_repository = StudentRepository(session)
        students = [
            StudentService(student_repository, ClassroomRepository(session)).create(
                classroom.id,
                owner.id,
                student_id=f"S{i}",
                full_name=f"Student {i}",
            )
            for i in range(student_count)
        ]
        active_session = _make_service(session).create_session(classroom.id, owner.id)
        session.commit()

        seeded = {
            "owner_id": owner.id,
            "classroom_id": classroom.id,
            "session_id": active_session.id,
            "student_ids": [student.id for student in students],
            "business_student_id": "S0",
        }
        session.expunge_all()
        return seeded


def _cleanup(test_engine: Any, seeded: dict[str, Any]) -> None:
    with Session(test_engine) as session:
        ids = seeded["student_ids"]
        session.query(AttendanceRecord).filter(
            AttendanceRecord.session_id == seeded["session_id"]
        ).delete(synchronize_session=False)
        session.query(AttendanceSession).filter(
            AttendanceSession.id == seeded["session_id"]
        ).delete(synchronize_session=False)
        if ids:
            session.query(Student).filter(Student.id.in_(ids)).delete(synchronize_session=False)
        session.query(Classroom).filter(Classroom.id == seeded["classroom_id"]).delete(
            synchronize_session=False
        )
        session.query(User).filter(User.id == seeded["owner_id"]).delete(synchronize_session=False)
        session.commit()


def test_concurrent_mark_same_record_is_idempotent(test_engine: Any) -> None:
    seeded = _seed_session(test_engine)
    statuses: list[str] = []
    errors: list[int] = []

    def worker() -> None:
        with Session(test_engine) as session:
            service = _make_service(session)
            try:
                result = service.mark_present(
                    seeded["session_id"],
                    seeded["owner_id"],
                    student_id=seeded["business_student_id"],
                    method="QR",
                )
                statuses.append("already" if result.already_marked else "marked")
            except HTTPException as exc:
                errors.append(exc.status_code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: worker(), [None, None]))

        assert not errors
        assert sorted(statuses) == ["already", "marked"]

        with Session(test_engine) as session:
            record = AttendanceRecordRepository(session).get_by_student_business_id(
                seeded["session_id"], seeded["business_student_id"]
            )
            assert record is not None
            assert record.status == "PRESENT"
    finally:
        _cleanup(test_engine, seeded)


def test_concurrent_finalize_same_session_is_safe(test_engine: Any) -> None:
    seeded = _seed_session(test_engine)
    outcomes: list[str] = []
    errors: list[int] = []

    def worker() -> None:
        with Session(test_engine) as session:
            service = _make_service(session)
            try:
                result = service.finalize_session(seeded["session_id"], seeded["owner_id"])
                outcomes.append(result.session.status)
            except HTTPException as exc:
                errors.append(exc.status_code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: worker(), [None, None]))

        assert sorted(outcomes) == ["FINALIZED"]
        assert errors == [409]

        with Session(test_engine) as session:
            current = AttendanceSessionRepository(session).get_owned(
                seeded["session_id"], seeded["owner_id"]
            )
            assert current is not None
            assert current.status == "FINALIZED"
            counts = AttendanceRecordRepository(session).count_by_status(seeded["session_id"])
            assert counts == {"PENDING": 0, "PRESENT": 0, "ABSENT": 1}
    finally:
        _cleanup(test_engine, seeded)


def test_concurrent_create_session_for_same_classroom_is_safe(
    test_engine: Any,
) -> None:
    # Minimal setup with one active student for the creation race.
    with Session(test_engine) as session:
        owner = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
        session.add(owner)
        session.flush()
        classroom = ClassroomService(ClassroomRepository(session)).create(owner.id, "Race")
        StudentService(StudentRepository(session), ClassroomRepository(session)).create(
            classroom.id, owner.id, student_id="S1", full_name="Student"
        )
        session.commit()
        owner_id = owner.id
        classroom_id = classroom.id
        session.expunge_all()

    results: list[str] = []
    errors: list[int] = []

    def worker() -> None:
        with Session(test_engine) as session:
            try:
                _make_service(session).create_session(classroom_id, owner_id)
                results.append("created")
            except HTTPException as exc:
                errors.append(exc.status_code)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: worker(), [None, None]))

        assert results == ["created"]
        assert errors == [409]

        with Session(test_engine) as session:
            sessions = list(
                AttendanceSessionRepository(session).list_finalized_for_classroom(classroom_id)
            )
            # list_finalized excludes active sessions, so query the active row separately.
            active = AttendanceSessionRepository(session).get_active_for_classroom(classroom_id)
            assert active is not None
            assert all(s.status == "FINALIZED" for s in sessions)
    finally:
        with Session(test_engine) as session:
            active = AttendanceSessionRepository(session).get_active_for_classroom(classroom_id)
            session_ids = [active.id] if active is not None else []
            finals = AttendanceSessionRepository(session).list_finalized_for_classroom(classroom_id)
            session_ids.extend(s.id for s in finals)
            if session_ids:
                session.query(AttendanceRecord).filter(
                    AttendanceRecord.session_id.in_(session_ids)
                ).delete(synchronize_session=False)
                session.query(AttendanceSession).filter(
                    AttendanceSession.classroom_id == classroom_id
                ).delete(synchronize_session=False)
            session.query(Student).filter(Student.classroom_id == classroom_id).delete(
                synchronize_session=False
            )
            session.query(Classroom).filter(Classroom.id == classroom_id).delete(
                synchronize_session=False
            )
            session.query(User).filter(User.id == owner_id).delete(synchronize_session=False)
            session.commit()
