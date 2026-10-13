"""Classroom endpoints, owner-scoped through the service."""

from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import (
    get_attendance_history_service,
    get_classroom_service,
    get_current_user,
    get_excel_service,
)
from app.models.user import User
from app.schemas.attendance_schema import (
    AttendanceHistoryResponse,
    AttendanceHistoryRowResponse,
)
from app.schemas.classroom_schema import ClassroomCreate, ClassroomResponse, ClassroomUpdate
from app.services.attendance_history_service import AttendanceHistoryGrid, AttendanceHistoryService
from app.services.classroom_service import ClassroomService
from app.services.excel_service import ExcelService

router = APIRouter(tags=["classrooms"])

_XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/api/classrooms", response_model=list[ClassroomResponse])
def list_classrooms(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ClassroomService, Depends(get_classroom_service)],
) -> list[ClassroomResponse]:
    classrooms = service.list(current_user.id)
    return [ClassroomResponse.model_validate(classroom) for classroom in classrooms]


@router.post(
    "/api/classrooms",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_classroom(
    data: ClassroomCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ClassroomService, Depends(get_classroom_service)],
) -> ClassroomResponse:
    classroom = service.create(current_user.id, data.name)
    return ClassroomResponse.model_validate(classroom)


@router.get("/api/classrooms/{id}", response_model=ClassroomResponse)
def get_classroom(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ClassroomService, Depends(get_classroom_service)],
) -> ClassroomResponse:
    classroom = service.get(id, current_user.id)
    return ClassroomResponse.model_validate(classroom)


@router.patch("/api/classrooms/{id}", response_model=ClassroomResponse)
def update_classroom(
    id: int,
    data: ClassroomUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ClassroomService, Depends(get_classroom_service)],
) -> ClassroomResponse:
    classroom = service.rename(id, current_user.id, data.name)
    return ClassroomResponse.model_validate(classroom)


def _history_response(grid: AttendanceHistoryGrid) -> AttendanceHistoryResponse:
    """Map the history read model onto the public grid representation."""
    return AttendanceHistoryResponse(
        classroom_id=grid.classroom_id,
        classroom_name=grid.classroom_name,
        dates=grid.dates,
        rows=[
            AttendanceHistoryRowResponse(
                student_id=row.student_id,
                student_name=row.student_name,
                is_active=row.is_active,
                statuses=row.statuses,
            )
            for row in grid.rows
        ],
    )


@router.get(
    "/api/classrooms/{id}/attendance-history",
    response_model=AttendanceHistoryResponse,
)
def get_attendance_history(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceHistoryService, Depends(get_attendance_history_service)],
) -> AttendanceHistoryResponse:
    return _history_response(service.build_grid(id, current_user.id))


@router.get("/api/classrooms/{id}/attendance-history/export")
def export_attendance_history(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[AttendanceHistoryService, Depends(get_attendance_history_service)],
    excel: Annotated[ExcelService, Depends(get_excel_service)],
) -> Response:
    """Download the classroom's finalized attendance history as an XLSX workbook.

    Ownership is enforced by the service (uniform 404 for a missing or
    unowned classroom). The workbook is the transposed grid: students as
    rows, finalized session dates as columns, blank cells for missing
    records. The endpoint is read-only.
    """
    grid = service.build_grid(id, current_user.id)
    exported_at = datetime.now(UTC)
    workbook = excel.build_history_workbook(grid, exported_at)
    buffer = BytesIO()
    workbook.save(buffer)
    filename = excel.history_export_filename(grid, exported_at)
    return Response(
        content=buffer.getvalue(),
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
