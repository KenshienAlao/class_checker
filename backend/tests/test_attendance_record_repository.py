"""Integration tests for ``AttendanceRecordRepository`` against PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository


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


def _student(db: Session, classroom: Classroom, student_id: str, full_name: str) -> Student:
    student = Student(classroom_id=classroom.id, student_id=student_id, full_name=full_name)
    db.add(student)
    db.flush()
    return student


def _session(db: Session, classroom: Classroom, status: str = "ACTIVE") -> AttendanceSession:
    session = AttendanceSession(classroom_id=classroom.id, status=status)
    db.add(session)
    db.flush()
    return session


def _record(
    db: Session,
    session: AttendanceSession,
    student: Student,
    *,
    status: str = "PENDING",
    method: str | None = None,
) -> AttendanceRecord:
    record = AttendanceRecord(
        session_id=session.id, student_id=student.id, status=status, method=method
    )
    db.add(record)
    db.flush()
    return record


def test_add_all_flushes_and_assigns_ids_without_committing(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    other = _student(db_session, classroom, "25-09760", "Grace")
    commits: list[int] = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    records = [
        AttendanceRecord(session_id=session.id, student_id=student.id),
        AttendanceRecord(session_id=session.id, student_id=other.id),
    ]
    AttendanceRecordRepository(db_session).add_all(records)

    assert all(record.id is not None for record in records)
    assert commits == []


def test_add_all_records_are_queryable_within_the_transaction(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    repository = AttendanceRecordRepository(db_session)

    repository.add_all([AttendanceRecord(session_id=session.id, student_id=student.id)])

    assert len(repository.list_by_session(session.id)) == 1


def test_get_by_student_business_id_returns_the_matching_record(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    record = _record(db_session, session, student)

    found = AttendanceRecordRepository(db_session).get_by_student_business_id(
        session.id, "25-09759"
    )

    assert found is not None
    assert found.id == record.id


def test_get_by_student_business_id_returns_none_for_missing_student(
    db_session: Session,
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)

    found = AttendanceRecordRepository(db_session).get_by_student_business_id(
        session.id, "99-00000"
    )

    assert found is None


def test_get_by_student_business_id_is_scoped_to_the_session(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    _record(db_session, session, student)
    other_session = _session(db_session, classroom, status="FINALIZED")

    found = AttendanceRecordRepository(db_session).get_by_student_business_id(
        other_session.id, "25-09759"
    )

    assert found is None


def test_list_by_session_returns_only_that_sessions_records(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    record = _record(db_session, session, student)
    other_session = _session(db_session, classroom, status="FINALIZED")
    other_student = _student(db_session, classroom, "25-09760", "Grace")
    other_record = _record(db_session, other_session, other_student)

    records = AttendanceRecordRepository(db_session).list_by_session(session.id)

    ids = [item.id for item in records]
    assert ids == [record.id]
    assert other_record.id not in ids


def test_list_by_session_orders_by_student_name_then_id(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    grace = _student(db_session, classroom, "25-09760", "Grace")
    ada = _student(db_session, classroom, "25-09759", "Ada")
    _record(db_session, session, grace)
    _record(db_session, session, ada)

    records = AttendanceRecordRepository(db_session).list_by_session(session.id)

    assert [item.student_id for item in records] == [ada.id, grace.id]


def test_count_by_status_returns_zero_counts_for_an_empty_session(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)

    counts = AttendanceRecordRepository(db_session).count_by_status(session.id)

    assert counts == {"PENDING": 0, "PRESENT": 0, "ABSENT": 0}


def test_count_by_status_counts_each_status(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    present = _student(db_session, classroom, "25-09759", "Ada")
    absent = _student(db_session, classroom, "25-09760", "Grace")
    pending = _student(db_session, classroom, "25-09761", "Linus")
    _record(db_session, session, present, status="PRESENT", method="QR")
    _record(db_session, session, absent, status="ABSENT")
    _record(db_session, session, pending)

    counts = AttendanceRecordRepository(db_session).count_by_status(session.id)

    assert counts == {"PENDING": 1, "PRESENT": 1, "ABSENT": 1}


def test_finalize_pending_marks_only_pending_records_absent(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    present = _student(db_session, classroom, "25-09759", "Ada")
    absent = _student(db_session, classroom, "25-09760", "Grace")
    pending = _student(db_session, classroom, "25-09761", "Linus")
    present_record = _record(db_session, session, present, status="PRESENT", method="QR")
    absent_record = _record(db_session, session, absent, status="ABSENT")
    pending_record = _record(db_session, session, pending)

    AttendanceRecordRepository(db_session).finalize_pending(session.id)

    db_session.refresh(present_record)
    db_session.refresh(absent_record)
    db_session.refresh(pending_record)
    assert present_record.status == "PRESENT"
    assert absent_record.status == "ABSENT"
    assert pending_record.status == "ABSENT"


def test_finalize_pending_returns_the_affected_row_count(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    first = _student(db_session, classroom, "25-09759", "Ada")
    second = _student(db_session, classroom, "25-09760", "Grace")
    _record(db_session, session, first)
    _record(db_session, session, second)

    affected = AttendanceRecordRepository(db_session).finalize_pending(session.id)

    assert affected == 2


def test_finalize_pending_is_idempotent(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    record = _record(db_session, session, student)
    repository = AttendanceRecordRepository(db_session)
    repository.finalize_pending(session.id)

    affected = repository.finalize_pending(session.id)

    assert affected == 0
    db_session.refresh(record)
    assert record.status == "ABSENT"


def test_finalize_pending_does_not_touch_other_sessions(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    session = _session(db_session, classroom)
    student = _student(db_session, classroom, "25-09759", "Ada")
    record = _record(db_session, session, student)
    other_session = _session(db_session, classroom, status="FINALIZED")
    other_record = _record(db_session, other_session, student)

    affected = AttendanceRecordRepository(db_session).finalize_pending(other_session.id)

    assert affected == 1
    db_session.refresh(record)
    db_session.refresh(other_record)
    assert record.status == "PENDING"
    assert other_record.status == "ABSENT"


def test_list_finalized_for_classroom_returns_only_finalized_records(
    db_session: Session,
) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    finalized = _session(db_session, classroom, status="FINALIZED")
    active = _session(db_session, classroom, status="ACTIVE")
    student = _student(db_session, classroom, "25-09759", "Ada")
    finalized_record = _record(db_session, finalized, student, status="PRESENT", method="QR")
    _record(db_session, active, student)

    records = AttendanceRecordRepository(db_session).list_finalized_for_classroom(classroom.id)

    assert [item.id for item in records] == [finalized_record.id]
    assert records[0].student.full_name == "Ada"
    assert records[0].session.status == "FINALIZED"


def test_list_finalized_for_classroom_is_scoped_to_the_classroom(db_session: Session) -> None:
    owner = _user(db_session)
    classroom = _classroom(db_session, owner)
    other = _classroom(db_session, owner, name="BSIT3A")
    other_session = _session(db_session, other, status="FINALIZED")
    other_student = _student(db_session, other, "25-09760", "Grace")
    _record(db_session, other_session, other_student)

    assert AttendanceRecordRepository(db_session).list_finalized_for_classroom(classroom.id) == []
