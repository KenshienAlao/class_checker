"""Metadata assertions for the classroom-scoped ORM models.

These checks inspect the declarative metadata only; they do not touch the
database. They guard the constraints that later migrations and services rely on.
"""

from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint, inspect
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.core.database import Base
from app.models import (
    AttendanceRecord,
    AttendanceSession,
    Classroom,
    Student,
)

_EXPECTED_TABLES = {
    "attendance_records",
    "attendance_sessions",
    "classrooms",
    "students",
    "users",
}


def _table(model: type[Base]) -> Table:
    return cast(Table, inspect(model).local_table)


def _unique_column_sets(model: type[Base]) -> set[frozenset[str]]:
    return {
        frozenset(column.name for column in constraint.columns)
        for constraint in _table(model).constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_keys(model: type[Base]) -> set[tuple[str, str]]:
    return {
        (fk.parent.name, f"{fk.column.table.name}.{fk.column.name}")
        for fk in _table(model).foreign_keys
    }


def test_all_tables_registered() -> None:
    assert _EXPECTED_TABLES <= set(Base.metadata.tables)


def test_student_foreign_key_and_unique_constraint() -> None:
    assert _foreign_keys(Student) == {("classroom_id", "classrooms.id")}
    assert frozenset({"classroom_id", "student_id"}) in _unique_column_sets(Student)


def test_student_id_is_uuid_primary_key() -> None:
    id_column = _table(Student).c.id
    assert id_column.primary_key is True
    assert isinstance(id_column.type, PG_UUID)
    assert id_column.type.as_uuid is True


def test_session_foreign_key_and_status_check() -> None:
    assert _foreign_keys(AttendanceSession) == {("classroom_id", "classrooms.id")}
    checks = [
        str(constraint.sqltext)
        for constraint in _table(AttendanceSession).constraints
        if isinstance(constraint, CheckConstraint)
    ]
    assert any("ACTIVE" in sql and "FINALIZED" in sql for sql in checks)


def test_one_active_session_partial_unique_index() -> None:
    index = next(
        ix
        for ix in _table(AttendanceSession).indexes
        if ix.name == "uq_attendance_sessions_active_classroom"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == ["classroom_id"]
    assert index.dialect_options["postgresql"]["where"] is not None


def test_attendance_record_foreign_keys_and_unique_constraint() -> None:
    assert _foreign_keys(AttendanceRecord) == {
        ("session_id", "attendance_sessions.id"),
        ("student_id", "students.id"),
    }
    assert frozenset({"session_id", "student_id"}) in _unique_column_sets(AttendanceRecord)


def test_no_cascade_delete_on_history_foreign_keys() -> None:
    for model in (Student, AttendanceSession, AttendanceRecord):
        for fk in _table(model).foreign_keys:
            assert fk.ondelete is None, f"{model.__name__}.{fk.parent.name} cascades"


def test_classroom_owned_by_user() -> None:
    assert _foreign_keys(Classroom) == {("owner_id", "users.id")}
