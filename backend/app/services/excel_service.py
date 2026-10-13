"""Deterministic XLSX generation for attendance export (`docs/05` §23)."""

from datetime import UTC, date, datetime

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.services.attendance_history_service import AttendanceHistoryGrid
from app.services.attendance_service import SessionReview

# Column labels of the per-session report, in the documented order.
_SESSION_COLUMNS = (
    "Student ID",
    "Student Name",
    "Program",
    "Classroom",
    "Date",
    "Status",
    "Marked Time",
    "Method",
)

# Leading label columns of the transposed history grid.
_HISTORY_LABEL_COLUMNS = ("Student ID", "Student Name")

# Placeholder for the marked time and method an absent record never has.
_ABSENT_PLACEHOLDER = "-"


class ExcelService:
    """Renders attendance read models as XLSX workbooks.

    Both builders are pure functions of their inputs: row order comes
    from the read model and workbook timestamps are derived from the
    data, so the same input always produces the same bytes. Rendering
    never writes to the database.
    """

    def build_session_workbook(self, review: SessionReview) -> Workbook:
        """Render one session as the documented per-session report.

        Columns follow ``docs/05`` §23. Records are rendered in the
        review's name order. An absent record renders ``-`` for the
        marked time and method it does not have.
        """
        workbook = self._workbook(review.session.started_at)
        worksheet = _active_sheet(workbook)
        worksheet.append(list(_SESSION_COLUMNS))
        classroom_name = review.classroom.name
        session_date = _session_date(review.session.started_at).isoformat()
        for record in review.records:
            worksheet.append(
                [
                    record.student.student_id,
                    record.student.full_name,
                    record.student.program or "",
                    classroom_name,
                    session_date,
                    record.status,
                    _mark_time(record.marked_at),
                    record.method or _ABSENT_PLACEHOLDER,
                ]
            )
        return workbook

    def session_export_filename(self, review: SessionReview) -> str:
        """Return the predictable session export filename (FR-EXPORT-009)."""
        session_date = _session_date(review.session.started_at)
        return f"{review.classroom.name}_Attendance_{session_date.isoformat()}.xlsx"

    def build_history_workbook(
        self, grid: AttendanceHistoryGrid, exported_at: datetime
    ) -> Workbook:
        """Render the history grid transposed (FR-EXPORT-010).

        Students are rows and the finalized session dates are columns,
        in the grid's chronological order. A student with no record
        for a date renders a blank cell.
        """
        workbook = self._workbook(exported_at)
        worksheet = _active_sheet(workbook)
        worksheet.append(
            [
                *_HISTORY_LABEL_COLUMNS,
                *(day.isoformat() for day in grid.dates),
            ]
        )
        for row in grid.rows:
            worksheet.append(
                [row.student_id, row.student_name, *(status or "" for status in row.statuses)]
            )
        return workbook

    def history_export_filename(self, grid: AttendanceHistoryGrid, exported_at: datetime) -> str:
        """Return the predictable history export filename (FR-EXPORT-009).

        The history grid spans many session dates, so the export date
        distinguishes the workbook; ``exported_at`` is supplied by the
        caller to keep generation deterministic.
        """
        export_date = _session_date(exported_at)
        return f"{grid.classroom_name}_Attendance_History_{export_date.isoformat()}.xlsx"

    @staticmethod
    def _workbook(stamped_at: datetime) -> Workbook:
        workbook = Workbook()
        # openpyxl stamps creation time by default; deriving the
        # metadata from the data keeps repeated builds byte-identical.
        workbook.properties.created = stamped_at
        workbook.properties.modified = stamped_at
        return workbook


def _active_sheet(workbook: Workbook) -> Worksheet:
    """Return the workbook's default sheet.

    ``Workbook()`` always creates one sheet, so the active sheet is
    never ``None``; the assert records that invariant for the type
    checker.
    """
    worksheet = workbook.active
    assert worksheet is not None
    return worksheet


def _session_date(started_at: datetime) -> date:
    """Return a timestamp's calendar date in the application's UTC convention.

    Session and record timestamps are written in UTC, so the exported
    date is the UTC calendar date rather than a time-zone-dependent
    rendering.
    """
    return started_at.astimezone(UTC).date()


def _mark_time(marked_at: datetime | None) -> str:
    """Return a record's marked time as ``HH:MM AM``, or ``-`` when absent."""
    if marked_at is None:
        return _ABSENT_PLACEHOLDER
    return marked_at.astimezone(UTC).strftime("%I:%M %p")
