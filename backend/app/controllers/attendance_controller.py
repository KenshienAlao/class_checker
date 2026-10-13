"""Attendance session endpoints, owner-scoped through the service."""

from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.dependencies import (
    get_attendance_service,
    get_current_user,
    get_excel_service,
)
from app.models.user import User
from app.schemas.attendance_schema import (
    AttendanceFinalizeResponse,
    AttendanceMarkRequest,
    AttendanceMarkResponse,
    AttendanceRecordResponse,
    AttendanceSessionResponse,
)
from app.services.attendance_service import (
    AttendanceService,
    FinalizeResult,
    MarkPresentResult,
    SessionReview,
)
from app.services.excel_service import ExcelService

router = APIRouter(tags=["attendance"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_SESSION_NOT_FINALIZED = "Attendance session is not finalized"


def _finalize_response(result: FinalizeResult) -> AttendanceFinalizeResponse:
    """Map a finalize outcome onto the public response representation."""
    return AttendanceFinalizeResponse(
        session_id=result.session.id,
        status=result.session.status,
        present_count=result.present_count,
        absent_count=result.absent_count,
        finalized_at=result.session.finalized_at,
    )


def _mark_response(result: MarkPresentResult) -> AttendanceMarkResponse:
    """Map a mark-present outcome onto the public response representation."""
    record = result.record
    return AttendanceMarkResponse(
        student_id=record.student.student_id,
        student_name=record.student.full_name,
        status=record.status,
        method=record.method,
        marked_at=record.marked_at,
        already_marked=result.already_marked,
    )


def _to_response(review: SessionReview) -> AttendanceSessionResponse:
    """Map the service read model onto the public session representation."""
    return AttendanceSessionResponse(
        session_id=review.session.id,
        classroom_id=review.classroom.id,
        classroom_name=review.classroom.name,
        status=review.session.status,
        started_at=review.session.started_at,
        finalized_at=review.session.finalized_at,
        present_count=review.present_count,
        pending_count=review.pending_count,
        absent_count=review.absent_count,
        records=[
            AttendanceRecordResponse(
                student_id=record.student.student_id,
                student_name=record.student.full_name,
                status=record.status,
                method=record.method,
                marked_at=record.marked_at,
            )
            for record in review.records
        ],
    )


@router.post(
    "/api/classrooms/{id}/attendance-sessions",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attendance_session(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceSessionResponse:
    session = service.create_session(id, current_user.id)
    return _to_response(service.get_session(session.id, current_user.id))


@router.get("/api/attendance-sessions/{id}", response_model=AttendanceSessionResponse)
def get_attendance_session(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceSessionResponse:
    return _to_response(service.get_session(id, current_user.id))


@router.post("/api/attendance-sessions/{id}/scan", response_model=AttendanceMarkResponse)
def scan_attendance(
    id: int,
    data: AttendanceMarkRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceMarkResponse:
    result = service.mark_present(id, current_user.id, student_id=data.student_id, method="QR")
    return _mark_response(result)


@router.post("/api/attendance-sessions/{id}/manual", response_model=AttendanceMarkResponse)
def manual_attendance(
    id: int,
    data: AttendanceMarkRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceMarkResponse:
    result = service.mark_present(id, current_user.id, student_id=data.student_id, method="MANUAL")
    return _mark_response(result)


@router.post(
    "/api/attendance-sessions/{id}/finalize",
    response_model=AttendanceFinalizeResponse,
)
def finalize_attendance(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
) -> AttendanceFinalizeResponse:
    return _finalize_response(service.finalize_session(id, current_user.id))


@router.get("/api/attendance-sessions/{id}/export")
def export_attendance_session(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceService, Depends(get_attendance_service)],
    excel: Annotated[ExcelService, Depends(get_excel_service)],
) -> Response:
    """Download a finalized session's attendance report as an XLSX workbook.

    Ownership is enforced by the service (uniform 404 for a missing or
    unowned session). Only finalized sessions can be exported: an active
    session has no final report yet. The endpoint is read-only.
    """
    review = service.get_session(id, current_user.id)
    if review.session.status != "FINALIZED":
        raise HTTPException(status.HTTP_409_CONFLICT, detail=_SESSION_NOT_FINALIZED)
    workbook = excel.build_session_workbook(review)
    buffer = BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type=_XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{excel.session_export_filename(review)}"'
        },
    )
