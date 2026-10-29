"""
Ресурс «Автентифікація» (Auth): вхід через Microsoft, оновлення і відкликання токена.

ЗАГЛУШКА: код Microsoft не перевіряється, повертається тестовий студент. Реальна перевірка
ID-токена (iss, aud, exp, email_verified, tid == tenant НаУКМА, домен пошти ukma.edu.ua) і збереження refresh-токенів
у БД додаються пізніше, форма відповідей уже відповідає контракту (§3.1).

Використання ШІ: валідацію GoogleLoginRequest (формат PKCE code_verifier за RFC 7636, перевірка redirect_uri
зі списком дозволених адрес ALLOWED_REDIRECT_URIS) додано за допомогою Claude (Anthropic).
Перевірка: tests/test_plan_rules.py (тести схеми входу), Black, flake8, bandit.
"""

import os
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Cookie, Depends, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ...db.models.users import User
from ...db.session import get_db
from ..auth_service import create_refresh_token, revoke_refresh_token, rotate_refresh_token, sign_in_user
from ..common import ApiError, error_responses
from ..microsoft import authenticate
from ..tokens import (
    ACCESS_TOKEN_TTL_SECONDS,
    REFRESH_TOKEN_TTL_SECONDS,
    get_auth_settings,
    issue_access_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

_PKCE_PATTERN = r"^[A-Za-z0-9\-._~]{43,128}$"


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"


class MicrosoftLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048, description="Код авторизації Microsoft")
    code_verifier: str = Field(..., pattern=_PKCE_PATTERN, description="PKCE code_verifier (43-128 символів RFC 7636)")
    nonce: str = Field(
        ..., min_length=16, max_length=256, description="nonce, переданий фронтендом у запиті авторизації"
    )
    redirect_uri: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="redirect_uri, використаний на фронтенді",
    )

    @field_validator("redirect_uri")
    @classmethod
    def validate_redirect_uri(cls, value: str) -> str:
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


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_auth_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=REFRESH_TOKEN_TTL_SECONDS,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(
        access_token=issue_access_token(user.id, user.role.value),
        user=AuthUser(id=user.id, email=user.email, full_name=user.full_name, role=UserRole(user.role.value)),
    )


@router.post(
    "/microsoft",
    response_model=AuthResponse,
    summary="Вхід: обмін коду Microsoft на токени",
    description=(
        "Обмінює код авторизації Microsoft (PKCE) на id_token, перевіряє його підпис, tenant, nonce і домен пошти. "
        "При першому вході створює студента автоматично. Refresh-токен видається в HttpOnly cookie."
    ),
    responses={
        200: {"description": "Вхід виконано"},
        **error_responses(
            401,
            403,
            422,
            overrides={
                401: ("INVALID_AUTH_CODE", "Не вдалося підтвердити вхід через Microsoft"),
                403: ("EMAIL_DOMAIN_NOT_ALLOWED", "Вхід дозволено лише з корпоративною поштою НаУКМА"),
            },
        ),
    },
)
def login_with_microsoft(payload: MicrosoftLoginRequest, response: Response, db: Session = Depends(get_db)):
    identity = authenticate(payload.code, payload.code_verifier, payload.redirect_uri, payload.nonce)
    user = sign_in_user(db, identity)
    raw_refresh = create_refresh_token(db, user.id)
    db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return _auth_response(user)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Новий access-токен за refresh-cookie",
    description="Без тіла. Потрібна cookie refresh_token (credentials: include). Refresh-токен ротується.",
    responses={200: {"description": "Токен оновлено"}, **error_responses(401)},
)
def refresh_session(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise ApiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації")
    user, new_refresh = rotate_refresh_token(db, refresh_token)
    _set_refresh_cookie(response, new_refresh)
    return _auth_response(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Вихід",
    description="Відкликає refresh-токен і очищає cookie.",
    responses={204: {"description": "Вихід виконано"}},
)
def logout(refresh_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    settings = get_auth_settings()
    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    result.delete_cookie(
        key=REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return result
