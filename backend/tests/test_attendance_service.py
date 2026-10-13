"""Integration tests for ``AttendanceService`` against PostgreSQL."""

from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import Classroom
from app.models.student import Student
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.attendance_service import (
    AttendanceService,
    FinalizeResult,
    MarkPresentResult,
    SessionReview,
)


def _owner(db: Session) -> User:
    user = User(id=uuid4(), name="Owner", email=f"{uuid4()}@example.com", password="n/a")
    db.add(user)
    db.flush()
    return user


def _classroom(db: Session, owner: User) -> Classroom:
    return ClassroomRepository(db).create(Classroom(name="BSIT2B", owner_id=owner.id))


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


def _service(db: Session) -> AttendanceService:
    return AttendanceService(
        AttendanceSessionRepository(db),
        AttendanceRecordRepository(db),
        ClassroomRepository(db),
        StudentRepository(db),
    )


def _record_student_ids(db: Session, session_id: int) -> set[UUID]:
    return {
        record.student_id for record in AttendanceRecordRepository(db).list_by_session(session_id)
    }


def _record_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(AttendanceRecord)) or 0


def _record_for(db: Session, session_id: int, business_id: str) -> AttendanceRecord | None:
    return AttendanceRecordRepository(db).get_by_student_business_id(session_id, business_id)


def test_create_session_creates_active_session_with_pending_records(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    first = _student(db_session, classroom, "25-09759", "Ada")
    second = _student(db_session, classroom, "25-09760", "Grace")

    session = _service(db_session).create_session(classroom.id, owner.id)

    assert session.id is not None
    assert session.classroom_id == classroom.id
    assert session.status == "ACTIVE"
    records = AttendanceRecordRepository(db_session).list_by_session(session.id)
    assert {record.student_id for record in records} == {first.id, second.id}
    assert {record.status for record in records} == {"PENDING"}


def test_create_session_returns_404_for_unowned_classroom(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    _student(db_session, classroom, "1", "Ada")
    stranger = _owner(db_session)
    service = _service(db_session)

    with pytest.raises(HTTPException) as exc:
        service.create_session(classroom.id, stranger.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Classroom not found"


def test_create_session_returns_404_for_missing_classroom(db_session: Session) -> None:
    owner = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).create_session(10**9, owner.id)

    assert exc.value.status_code == 404


def test_create_session_returns_409_when_an_active_session_exists(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    service = _service(db_session)
    existing = service.create_session(classroom.id, owner.id)

    with pytest.raises(HTTPException) as exc:
        service.create_session(classroom.id, owner.id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Classroom already has an active session"
    assert (
        AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) == existing
    )
    assert len(_record_student_ids(db_session, existing.id)) == 1


def test_create_session_returns_409_for_empty_active_roster(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada", active=False)
    service = _service(db_session)

    with pytest.raises(HTTPException) as exc:
        service.create_session(classroom.id, owner.id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Classroom has no active students"
    assert AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) is None
    assert _record_count(db_session) == 0


def test_create_session_snapshots_only_active_students(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    active = _student(db_session, classroom, "1", "Active")
    _student(db_session, classroom, "2", "Inactive", active=False)

    session = _service(db_session).create_session(classroom.id, owner.id)

    assert _record_student_ids(db_session, session.id) == {active.id}


def test_create_session_is_atomic_on_integrity_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    service = _service(db_session)

    def _boom(*args: object, **kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("simulated"))

    # Simulate the record insert failing after the session row was flushed.
    monkeypatch.setattr(service.record_repository, "add_all", _boom)

    with pytest.raises(HTTPException) as exc:
        service.create_session(classroom.id, owner.id)

    assert exc.value.status_code == 409
    assert AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) is None
    # The rolled-back session must still serve further queries.
    assert _record_count(db_session) == 0


def test_create_session_race_conflict_returns_409_without_extra_records(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    _student(db_session, classroom, "2", "Grace")
    service = _service(db_session)
    existing = service.create_session(classroom.id, owner.id)

    # Simulate two requests passing the active-session pre-check concurrently.
    monkeypatch.setattr(service, "_ensure_no_active_session", lambda *a, **k: None)

    with pytest.raises(HTTPException) as exc:
        service.create_session(classroom.id, owner.id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Classroom already has an active session"
    assert (
        AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id) == existing
    )
    assert len(_record_student_ids(db_session, existing.id)) == 2


def _session_with_student(
    db: Session, student_id: str = "25-09759", full_name: str = "Ada"
) -> tuple[User, Classroom, Student, AttendanceSession]:
    owner = _owner(db)
    classroom = _classroom(db, owner)
    student = _student(db, classroom, student_id, full_name)
    session = _service(db).create_session(classroom.id, owner.id)
    return owner, classroom, student, session


def test_mark_present_marks_a_pending_record_present(db_session: Session) -> None:
    owner, _, student, session = _session_with_student(db_session)

    result = _service(db_session).mark_present(
        session.id, owner.id, student_id="25-09759", method="QR"
    )

    assert isinstance(result, MarkPresentResult)
    assert result.already_marked is False
    assert result.record.student_id == student.id
    assert result.record.status == "PRESENT"
    assert result.record.method == "QR"
    assert result.record.marked_at is not None


def test_mark_present_records_the_manual_method(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)

    result = _service(db_session).mark_present(
        session.id, owner.id, student_id="25-09759", method="MANUAL"
    )

    assert result.record.method == "MANUAL"
    assert result.record.status == "PRESENT"


def test_mark_present_returns_404_for_unowned_session(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    _student(db_session, classroom, "1", "Ada")
    session = _service(db_session).create_session(classroom.id, other.id)
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(session.id, stranger.id, student_id="1", method="QR")

    assert exc.value.status_code == 404
    assert exc.value.detail == "Attendance session not found"


def test_mark_present_returns_404_for_missing_session(db_session: Session) -> None:
    owner = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(10**9, owner.id, student_id="1", method="QR")

    assert exc.value.status_code == 404


def test_mark_present_returns_409_for_a_finalized_session(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)
    session.status = "FINALIZED"
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(session.id, owner.id, student_id="25-09759", method="QR")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Attendance session is already finalized"
    record = _record_for(db_session, session.id, "25-09759")
    assert record is not None
    assert record.status == "PENDING"


def test_mark_present_returns_404_for_an_unknown_student(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(session.id, owner.id, student_id="99-00000", method="QR")

    assert exc.value.status_code == 404
    assert exc.value.detail == "Student was not found"


def test_mark_present_returns_409_for_an_absent_record(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)
    record = _record_for(db_session, session.id, "25-09759")
    assert record is not None
    record.status = "ABSENT"
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(session.id, owner.id, student_id="25-09759", method="QR")

    assert exc.value.status_code == 409
    refreshed = _record_for(db_session, session.id, "25-09759")
    assert refreshed is not None
    assert refreshed.status == "ABSENT"


def test_repeated_scan_returns_already_marked(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)
    service = _service(db_session)
    service.mark_present(session.id, owner.id, student_id="25-09759", method="QR")

    result = service.mark_present(session.id, owner.id, student_id="25-09759", method="QR")

    assert result.already_marked is True
    assert result.record.status == "PRESENT"


def test_duplicate_scan_preserves_the_original_values(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)
    service = _service(db_session)
    first = service.mark_present(session.id, owner.id, student_id="25-09759", method="QR")

    result = service.mark_present(session.id, owner.id, student_id="25-09759", method="MANUAL")

    assert result.already_marked is True
    assert result.record.method == "QR"
    assert result.record.marked_at == first.record.marked_at


def test_mark_present_succeeds_after_the_student_is_deactivated(db_session: Session) -> None:
    owner, _, student, session = _session_with_student(db_session)
    student.is_active = False
    db_session.commit()

    result = _service(db_session).mark_present(
        session.id, owner.id, student_id="25-09759", method="QR"
    )

    assert result.already_marked is False
    assert result.record.status == "PRESENT"


def test_mark_present_rejects_an_invalid_method(db_session: Session) -> None:
    owner, _, _, session = _session_with_student(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(session.id, owner.id, student_id="25-09759", method="BAD")

    assert exc.value.status_code == 422


def test_duplicate_marking_race_simulation_creates_no_second_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulation only: a real two-connection concurrency test is a separate task.
    # Both simulated requests observe the pre-mark PENDING state, yet marking
    # never inserts, so exactly one row remains.
    owner, _, _, session = _session_with_student(db_session)
    service = _service(db_session)
    first = service.mark_present(session.id, owner.id, student_id="25-09759", method="QR")
    assert first.already_marked is False

    def _stale_lookup(session_id: int, business_id: str) -> AttendanceRecord | None:
        record = _record_for(db_session, session_id, business_id)
        if record is not None:
            record.status = "PENDING"
        return record

    monkeypatch.setattr(service.record_repository, "get_by_student_business_id", _stale_lookup)

    second = service.mark_present(session.id, owner.id, student_id="25-09759", method="MANUAL")

    assert second.already_marked is False
    assert _record_count(db_session) == 1


def _service_with_roster(db: Session, count: int = 3) -> tuple[User, Classroom, AttendanceSession]:
    owner = _owner(db)
    classroom = _classroom(db, owner)
    for index in range(count):
        _student(db, classroom, f"25-0975{index}", f"Student {index}")
    session = _service(db).create_session(classroom.id, owner.id)
    return owner, classroom, session


def test_finalize_session_marks_pending_absent_and_finalizes(db_session: Session) -> None:
    owner, _, session = _service_with_roster(db_session, count=3)
    service = _service(db_session)
    service.mark_present(session.id, owner.id, student_id="25-09750", method="QR")

    result = service.finalize_session(session.id, owner.id)

    assert isinstance(result, FinalizeResult)
    assert result.session.status == "FINALIZED"
    assert result.session.finalized_at is not None
    assert result.session.finalized_at.tzinfo is not None
    assert result.present_count == 1
    assert result.absent_count == 2
    counts = AttendanceRecordRepository(db_session).count_by_status(session.id)
    assert counts == {"PENDING": 0, "PRESENT": 1, "ABSENT": 2}


def test_finalize_session_preserves_present_records(db_session: Session) -> None:
    owner, _, session = _service_with_roster(db_session, count=2)
    service = _service(db_session)
    service.mark_present(session.id, owner.id, student_id="25-09750", method="QR")

    service.finalize_session(session.id, owner.id)

    record = _record_for(db_session, session.id, "25-09750")
    assert record is not None
    assert record.status == "PRESENT"
    assert record.method == "QR"
    assert record.marked_at is not None


def test_finalize_session_leaves_already_absent_records_unchanged(db_session: Session) -> None:
    owner, _, session = _service_with_roster(db_session, count=2)
    absent_record = _record_for(db_session, session.id, "25-09751")
    assert absent_record is not None
    absent_record.status = "ABSENT"
    db_session.commit()

    result = _service(db_session).finalize_session(session.id, owner.id)

    refreshed = _record_for(db_session, session.id, "25-09751")
    assert refreshed is not None
    assert refreshed.status == "ABSENT"
    assert refreshed.method is None
    assert result.absent_count == 2


def test_finalize_session_returns_404_for_unowned_session(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    _student(db_session, classroom, "1", "Ada")
    session = _service(db_session).create_session(classroom.id, other.id)
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).finalize_session(session.id, stranger.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Attendance session not found"


def test_finalize_session_returns_404_for_missing_session(db_session: Session) -> None:
    owner = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).finalize_session(10**9, owner.id)

    assert exc.value.status_code == 404


def test_finalize_session_returns_409_when_already_finalized(db_session: Session) -> None:
    owner, _, session = _service_with_roster(db_session, count=1)
    service = _service(db_session)
    first = service.finalize_session(session.id, owner.id)

    with pytest.raises(HTTPException) as exc:
        service.finalize_session(session.id, owner.id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Attendance session is already finalized"
    assert first.session.finalized_at is not None


def test_finalize_session_handles_an_empty_session(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    session = AttendanceSessionRepository(db_session).add(
        AttendanceSession(classroom_id=classroom.id, status="ACTIVE")
    )
    db_session.commit()

    result = _service(db_session).finalize_session(session.id, owner.id)

    assert result.session.status == "FINALIZED"
    assert result.present_count == 0
    assert result.absent_count == 0


def test_finalize_session_rolls_back_on_commit_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, classroom, session = _service_with_roster(db_session, count=2)
    service = _service(db_session)

    def _boom() -> None:
        raise IntegrityError("COMMIT", {}, Exception("simulated"))

    monkeypatch.setattr(db_session, "commit", _boom)

    with pytest.raises(HTTPException) as exc:
        service.finalize_session(session.id, owner.id)

    assert exc.value.status_code == 409
    # Neither the pending sweep nor the session status change may persist.
    still_active = AttendanceSessionRepository(db_session).get_active_for_classroom(classroom.id)
    assert still_active is not None
    counts = AttendanceRecordRepository(db_session).count_by_status(session.id)
    assert counts == {"PENDING": 2, "PRESENT": 0, "ABSENT": 0}


def test_concurrent_finalize_race_simulation_is_consistent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulation only: a real two-connection concurrency test is a separate task.
    # A second request that read ACTIVE before the first committed re-runs the
    # sweep harmlessly; the outcome stays consistent.
    owner, _, session = _service_with_roster(db_session, count=2)
    service = _service(db_session)
    first = service.finalize_session(session.id, owner.id)

    original = service.session_repository.get_owned_for_update

    def _stale_status(session_id: int, owner_id: UUID) -> AttendanceSession | None:
        stale = original(session_id, owner_id)
        if stale is not None:
            stale.status = "ACTIVE"
        return stale

    monkeypatch.setattr(service.session_repository, "get_owned_for_update", _stale_status)

    second = service.finalize_session(session.id, owner.id)

    assert second.session.status == "FINALIZED"
    assert second.present_count == first.present_count
    assert second.absent_count == first.absent_count
    counts = AttendanceRecordRepository(db_session).count_by_status(session.id)
    assert counts == {"PENDING": 0, "PRESENT": 0, "ABSENT": 2}


def test_get_session_returns_the_review_aggregate(db_session: Session) -> None:
    owner, classroom, session = _service_with_roster(db_session, count=3)

    review = _service(db_session).get_session(session.id, owner.id)

    assert isinstance(review, SessionReview)
    assert review.session.id == session.id
    assert review.session.status == "ACTIVE"
    assert review.classroom.id == classroom.id
    assert review.classroom.name == "BSIT2B"
    assert review.pending_count == 3
    assert review.present_count == 0
    assert review.absent_count == 0
    assert len(review.records) == 3


def test_get_session_counts_mixed_statuses(db_session: Session) -> None:
    owner, _, session = _service_with_roster(db_session, count=3)
    service = _service(db_session)
    service.mark_present(session.id, owner.id, student_id="25-09750", method="QR")
    absent_record = _record_for(db_session, session.id, "25-09751")
    assert absent_record is not None
    absent_record.status = "ABSENT"
    db_session.commit()

    review = service.get_session(session.id, owner.id)

    assert review.present_count == 1
    assert review.absent_count == 1
    assert review.pending_count == 1


def test_get_session_counts_after_finalization(db_session: Session) -> None:
    owner, _, session = _service_with_roster(db_session, count=2)
    service = _service(db_session)
    service.mark_present(session.id, owner.id, student_id="25-09750", method="QR")
    service.finalize_session(session.id, owner.id)

    review = service.get_session(session.id, owner.id)

    assert review.session.status == "FINALIZED"
    assert review.session.finalized_at is not None
    assert review.pending_count == 0
    assert review.present_count == 1
    assert review.absent_count == 1


def test_get_session_orders_records_by_student_name(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "2", "Grace")
    _student(db_session, classroom, "1", "Ada")
    session = _service(db_session).create_session(classroom.id, owner.id)

    review = _service(db_session).get_session(session.id, owner.id)

    assert [record.student.full_name for record in review.records] == ["Ada", "Grace"]


def test_get_session_returns_404_for_unowned_session(db_session: Session) -> None:
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    _student(db_session, classroom, "1", "Ada")
    session = _service(db_session).create_session(classroom.id, other.id)
    stranger = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).get_session(session.id, stranger.id)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Attendance session not found"


def test_get_session_returns_404_for_missing_session(db_session: Session) -> None:
    owner = _owner(db_session)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).get_session(10**9, owner.id)

    assert exc.value.status_code == 404


def test_get_session_scopes_records_to_the_session(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    first = _student(db_session, classroom, "1", "Ada")
    service = _service(db_session)
    session_a = service.create_session(classroom.id, owner.id)
    second = _student(db_session, classroom, "2", "Grace")
    service.finalize_session(session_a.id, owner.id)
    session_b = service.create_session(classroom.id, owner.id)

    review_a = service.get_session(session_a.id, owner.id)
    review_b = service.get_session(session_b.id, owner.id)

    assert {record.student_id for record in review_a.records} == {first.id}
    assert {record.student_id for record in review_b.records} == {first.id, second.id}
    assert all(record.session_id == session_a.id for record in review_a.records)


def test_get_session_retains_inactive_students(db_session: Session) -> None:
    owner, _, student, session = _session_with_student(db_session)
    student.is_active = False
    db_session.commit()

    review = _service(db_session).get_session(session.id, owner.id)

    assert len(review.records) == 1
    record = review.records[0]
    assert record.student.student_id == "25-09759"
    assert record.student.is_active is False


def test_get_session_handles_an_empty_session(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    session = AttendanceSessionRepository(db_session).add(
        AttendanceSession(classroom_id=classroom.id, status="ACTIVE")
    )
    db_session.commit()

    review = _service(db_session).get_session(session.id, owner.id)

    assert review.pending_count == 0
    assert review.present_count == 0
    assert review.absent_count == 0
    assert review.records == []


def test_get_session_does_not_mutate_state(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _, _, session = _session_with_student(db_session)
    service = _service(db_session)
    commits: list[int] = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    review = service.get_session(session.id, owner.id)

    assert commits == []
    assert review.session.status == "ACTIVE"
    record = _record_for(db_session, session.id, "25-09759")
    assert record is not None
    assert record.status == "PENDING"
    assert record.method is None


def test_session_operations_return_a_uniform_404(db_session: Session) -> None:
    owner = _owner(db_session)
    other = _owner(db_session)
    classroom = _classroom(db_session, other)
    _student(db_session, classroom, "1", "Ada")
    session = _service(db_session).create_session(classroom.id, other.id)
    service = _service(db_session)
    expected = (404, "Attendance session not found")

    for session_id, owner_id in ((session.id, owner.id), (10**9, owner.id)):
        with pytest.raises(HTTPException) as mark_exc:
            service.mark_present(session_id, owner_id, student_id="1", method="QR")
        with pytest.raises(HTTPException) as finalize_exc:
            service.finalize_session(session_id, owner_id)
        with pytest.raises(HTTPException) as get_exc:
            service.get_session(session_id, owner_id)
        for exc in (mark_exc, finalize_exc, get_exc):
            assert (exc.value.status_code, exc.value.detail) == expected


def test_mark_present_rejects_a_student_from_another_classroom(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    other_classroom = ClassroomRepository(db_session).create(
        Classroom(name="BSIT3A", owner_id=owner.id)
    )
    _student(db_session, other_classroom, "25-09999", "Other Student")
    session = _service(db_session).create_session(classroom.id, owner.id)

    with pytest.raises(HTTPException) as exc:
        _service(db_session).mark_present(session.id, owner.id, student_id="25-09999", method="QR")

    assert exc.value.status_code == 404
    assert exc.value.detail == "Student was not found"
    record = _record_for(db_session, session.id, "25-09999")
    assert record is None


def test_attendance_lifecycle_end_to_end(db_session: Session) -> None:
    owner = _owner(db_session)
    classroom = _classroom(db_session, owner)
    _student(db_session, classroom, "1", "Ada")
    _student(db_session, classroom, "2", "Grace")
    _student(db_session, classroom, "3", "Linus")
    service = _service(db_session)

    session = service.create_session(classroom.id, owner.id)
    assert service.get_session(session.id, owner.id).pending_count == 3

    qr = service.mark_present(session.id, owner.id, student_id="1", method="QR")
    manual = service.mark_present(session.id, owner.id, student_id="2", method="MANUAL")
    duplicate = service.mark_present(session.id, owner.id, student_id="1", method="MANUAL")
    assert qr.already_marked is False
    assert manual.record.method == "MANUAL"
    assert duplicate.already_marked is True
    assert duplicate.record.method == "QR"

    review = service.get_session(session.id, owner.id)
    assert (review.present_count, review.pending_count, review.absent_count) == (2, 1, 0)

    result = service.finalize_session(session.id, owner.id)
    assert result.session.status == "FINALIZED"
    assert (result.present_count, result.absent_count) == (2, 1)

    # The bulk PENDING->ABSENT sweep does not synchronize in-memory ORM objects
    # (synchronize_session=False). Expire the shared test session to model the
    # separate request a real review GET would run in.
    db_session.expire_all()
    final_review = service.get_session(session.id, owner.id)
    assert (
        final_review.present_count,
        final_review.pending_count,
        final_review.absent_count,
    ) == (2, 0, 1)
    statuses = {record.student.student_id: record.status for record in final_review.records}
    assert statuses == {"1": "PRESENT", "2": "PRESENT", "3": "ABSENT"}

    with pytest.raises(HTTPException) as exc:
        service.mark_present(session.id, owner.id, student_id="3", method="QR")
    assert exc.value.status_code == 409
