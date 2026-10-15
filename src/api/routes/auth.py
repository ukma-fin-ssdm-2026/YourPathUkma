"""
Ресурс «Автентифікація» (Auth): вхід через Google, оновлення і відкликання токена.

ЗАГЛУШКА: код Google не перевіряється, повертається тестовий студент. Реальна перевірка
ID-токена (iss, aud, exp, email_verified, hd == ukma.edu.ua) і збереження refresh-токенів
у БД додаються пізніше, форма відповідей уже відповідає контракту (§3.1).

Використання ШІ: валідацію GoogleLoginRequest (формат PKCE code_verifier за RFC 7636, перевірка redirect_uri
зі списком дозволених адрес ALLOWED_REDIRECT_URIS) додано за допомогою Claude (Anthropic).
Перевірка: tests/test_plan_rules.py (тести схеми входу), Black, flake8, bandit.
"""

import os
import secrets
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Cookie, Response, status
from pydantic import BaseModel, Field, field_validator

from ..common import MOCK_STUDENT_ID, ApiError, error_responses

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
ACCESS_TOKEN_TTL_SECONDS = 900
REFRESH_COOKIE_TTL_SECONDS = 7 * 24 * 3600

# RFC 7636: code_verifier складається з [A-Z] [a-z] [0-9] - . _ ~ і має довжину 43-128 символів
_PKCE_PATTERN = r"^[A-Za-z0-9\-._~]{43,128}$"


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"


class GoogleLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048, description="Код авторизації Google")
    code_verifier: str = Field(..., pattern=_PKCE_PATTERN, description="PKCE code_verifier (43-128 символів RFC 7636)")
    redirect_uri: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="redirect_uri, використаний на фронтенді",
    )

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, value: str) -> str:
        """Якщо задано ALLOWED_REDIRECT_URIS (через кому), приймаються лише ці адреси; інакше базова перевірка."""
        allowed = [uri.strip() for uri in os.getenv("ALLOWED_REDIRECT_URIS", "").split(",") if uri.strip()]
        if allowed:
            if value not in allowed:
                raise ValueError("redirect_uri не входить до дозволеного списку")
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.fragment:
            raise ValueError("redirect_uri має бути абсолютною http(s)-адресою без фрагмента")
        return value


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
async def logout(response: Response):
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="strict",
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)