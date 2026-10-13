"""
Ресурс «Автентифікація» (Auth): вхід через Google, оновлення і відкликання токена.

ЗАГЛУШКА: код Google не перевіряється, повертається тестовий студент. Реальна перевірка
ID-токена (iss, aud, exp, email_verified, hd == ukma.edu.ua) і збереження refresh-токенів
у БД додаються пізніше, форма відповідей уже відповідає контракту (§3.1).
"""

import secrets
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Cookie, Response, status
from pydantic import BaseModel, Field

from ..common import MOCK_STUDENT_ID, ApiError, error_responses

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
ACCESS_TOKEN_TTL_SECONDS = 900
REFRESH_COOKIE_TTL_SECONDS = 7 * 24 * 3600


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"


class GoogleLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048, description="Код авторизації Google")
    code_verifier: str = Field(..., min_length=43, max_length=128, description="PKCE code_verifier")
    redirect_uri: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="redirect_uri, використаний на фронтенді",
    )


class AuthUser(BaseModel):
    id: int = Field(..., description="ID користувача", examples=[42])
    email: str = Field(..., description="Пошта користувача", examples=["student@ukma.edu.ua"])
    full_name: str = Field(..., description="Повне ім'я", examples=["Тестовий Студент"])
    role: UserRole = Field(..., description="Роль користувача")


class AuthResponse(BaseModel):
    access_token: str = Field(..., description="Access-токен (живе 15 хв, зберігати лише в пам'яті)")
    token_type: str = Field("Bearer", description="Тип токена")
    expires_in: int = Field(ACCESS_TOKEN_TTL_SECONDS, description="Строк життя токена, секунди")
    user: AuthUser


def _issue_session(response: Response) -> AuthResponse:
    """Видає новий access-токен і виставляє refresh-cookie (HttpOnly, Secure, SameSite=Strict)."""
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=secrets.token_urlsafe(32),
        max_age=REFRESH_COOKIE_TTL_SECONDS,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return AuthResponse(
        access_token=secrets.token_urlsafe(32),
        user=AuthUser(
            id=MOCK_STUDENT_ID,
            email="student@ukma.edu.ua",
            full_name="Тестовий Студент",
            role=UserRole.STUDENT,
        ),
    )


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Вхід: обмін коду Google на токени",
    description="Заглушка: приймає будь-який код і повертає тестового студента.",
    responses={200: {"description": "Вхід виконано"}, **error_responses(401, 422)},
)
async def login_with_google(payload: GoogleLoginRequest, response: Response):
    return _issue_session(response)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Новий access-токен за refresh-cookie",
    description="Без тіла. Потрібна cookie refresh_token (credentials: include).",
    responses={200: {"description": "Токен оновлено"}, **error_responses(401)},
)
async def refresh_session(response: Response, refresh_token: Optional[str] = Cookie(None)):
    if not refresh_token:
        raise ApiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації")
    return _issue_session(response)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Вихід",
    description="Очищає refresh-cookie. Заглушка: токени в БД ще не відкликаються.",
    responses={204: {"description": "Вихід виконано"}},
)
async def logout():
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response
