"""FastAPI dependency wiring."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    SESSION_COOKIE_NAME,
    SessionTokenError,
    decode_session_token,
)
from app.models.user import User
from app.repositories.attendance_record_repository import AttendanceRecordRepository
from app.repositories.attendance_session_repository import AttendanceSessionRepository
from app.repositories.authentication_repository import AuthenticationRepository
from app.repositories.classroom_repository import ClassroomRepository
from app.repositories.student_repository import StudentRepository
from app.services.attendance_history_service import AttendanceHistoryService
from app.services.attendance_service import AttendanceService
from app.services.authentication_service import AuthenticationService
from app.services.classroom_service import ClassroomService
from app.services.excel_service import ExcelService
from app.services.import_service import ImportService
from app.services.student_service import StudentService


def get_authentication_service(
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticationService:
    return AuthenticationService(AuthenticationRepository(db))


def get_classroom_service(
    db: Annotated[Session, Depends(get_db)],
) -> ClassroomService:
    return ClassroomService(ClassroomRepository(db))


def get_student_service(
    db: Annotated[Session, Depends(get_db)],
) -> StudentService:
    return StudentService(StudentRepository(db), ClassroomRepository(db))


def get_import_service(
    db: Annotated[Session, Depends(get_db)],
) -> ImportService:
    return ImportService(db, StudentRepository(db), ClassroomRepository(db))


def get_attendance_service(
    db: Annotated[Session, Depends(get_db)],
) -> AttendanceService:
    return AttendanceService(
        AttendanceSessionRepository(db),
        AttendanceRecordRepository(db),
        ClassroomRepository(db),
        StudentRepository(db),
    )


def get_attendance_history_service(
    db: Annotated[Session, Depends(get_db)],
) -> AttendanceHistoryService:
    return AttendanceHistoryService(
        ClassroomRepository(db),
        AttendanceSessionRepository(db),
        AttendanceRecordRepository(db),
        StudentRepository(db),
    )


def get_excel_service() -> ExcelService:
    return ExcelService()


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the user behind the session cookie, or raise 401."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user_id = decode_session_token(token)
    except SessionTokenError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        ) from None
    user = AuthenticationRepository(db).get_user(user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user
