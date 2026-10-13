from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.config import get_settings
from app.core.dependencies import get_authentication_service, get_current_user
from app.core.security import (
    CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    issue_session_cookies,
)
from app.models.user import User
from app.schemas.authentication_schema import Login, Register, UserResponse
from app.services.authentication_service import AuthenticationService

router = APIRouter(prefix="/api/auth")


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: Register,
    response: Response,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> UserResponse:
    user = service.register(data)
    issue_session_cookies(response, user.id)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=UserResponse)
def login(
    data: Login,
    response: Response,
    service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> UserResponse:
    user = service.login(data)
    issue_session_cookies(response, user.id)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/refresh", response_model=UserResponse)
def refresh(
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
) -> UserResponse:
    """Re-issue fresh cookies, sliding the session expiry on activity."""
    issue_session_cookies(response, current_user.id)
    return UserResponse.model_validate(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """Clear the session and CSRF cookies. Idempotent and session-less safe."""
    settings = get_settings()
    secure = settings.environment.lower() == "production"
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        CSRF_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )
