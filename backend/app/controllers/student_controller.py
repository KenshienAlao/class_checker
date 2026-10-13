"""Student endpoints, always scoped to an owned classroom."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, status

from app.core.dependencies import get_current_user, get_import_service, get_student_service
from app.models.user import User
from app.schemas.import_schema import ImportSummary
from app.schemas.student_schema import StudentCreate, StudentResponse, StudentUpdate
from app.services.import_service import ImportService
from app.services.student_service import UNSET, StudentService

router = APIRouter(tags=["students"])


@router.get("/api/classrooms/{id}/students", response_model=list[StudentResponse])
def list_students(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[StudentService, Depends(get_student_service)],
    search: str | None = Query(default=None, max_length=255),
) -> list[StudentResponse]:
    students = service.list(id, current_user.id, search=search)
    return [StudentResponse.model_validate(student) for student in students]


@router.post(
    "/api/classrooms/{id}/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_student(
    id: int,
    data: StudentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[StudentService, Depends(get_student_service)],
) -> StudentResponse:
    student = service.create(
        id,
        current_user.id,
        student_id=data.student_id,
        full_name=data.full_name,
        program=data.program,
    )
    return StudentResponse.model_validate(student)


@router.get("/api/students/{id}", response_model=StudentResponse)
def get_student(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[StudentService, Depends(get_student_service)],
) -> StudentResponse:
    student = service.get(id, current_user.id)
    return StudentResponse.model_validate(student)


@router.patch("/api/students/{id}", response_model=StudentResponse)
def update_student(
    id: UUID,
    data: StudentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[StudentService, Depends(get_student_service)],
) -> StudentResponse:
    fields = data.model_fields_set
    student = service.update(
        id,
        current_user.id,
        student_id=data.student_id if "student_id" in fields else UNSET,
        full_name=data.full_name if "full_name" in fields else UNSET,
        program=data.program if "program" in fields else UNSET,
    )
    return StudentResponse.model_validate(student)


@router.post("/api/students/{id}/deactivate", response_model=StudentResponse)
def deactivate_student(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[StudentService, Depends(get_student_service)],
) -> StudentResponse:
    student = service.deactivate(id, current_user.id)
    return StudentResponse.model_validate(student)


@router.post("/api/classrooms/{id}/students/import", response_model=ImportSummary)
def import_students(
    id: int,
    file: UploadFile,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ImportService, Depends(get_import_service)],
) -> ImportSummary:
    return service.import_file(id, current_user.id, file)
