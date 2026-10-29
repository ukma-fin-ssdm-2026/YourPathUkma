"""
Спільні елементи API YourPathUkma: єдиний формат помилок, пагінація, заглушка автентифікації.

Використання ШІ: файл створено за допомогою Claude (Anthropic) за вимогами ЛР4 та api-design.md.
Перевірка: ручний запуск сервера, перегляд у Swagger UI (/api-docs), перевірка
відповідей 401/404/409/422 для кожної кінцевої точки, звірка форматів з docs/api/api-design.md.

Правки за зовнішнім рев'ю (review/received/review-report.md) внесено за допомогою Claude (Claude Code):
`request_id` у ErrorResponse і заголовок X-Request-ID, журналювання замість print, обмеження
MCP_DEV_MODE. Перевірено: pytest (tests/test_request_id.py) і ruff check src/api.
"""

import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .tokens import decode_access_token, validate_auth_settings

logger = logging.getLogger("yourpath.api")

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_EXAMPLE_REQUEST_ID = "req_3f9a1c7e2b4d4a6e"
_UNAUTHORIZED_MESSAGE = "Відсутній або некоректний токен авторизації"


class ErrorDetail(BaseModel):
    field: str = Field(..., description="Поле, до якого належить помилка", examples=["items.0.credits"])
    message: str = Field(..., description="Опис проблеми", examples=["Input should be greater than 0"])


class ErrorResponse(BaseModel):
    """Єдиний формат відповіді для всіх помилок 4xx/5xx."""

    code: str = Field(..., description="Машинозчитуваний код помилки", examples=["PLAN_NOT_FOUND"])
    message: str = Field(
        ...,
        description="Повідомлення, зрозуміле людині",
        examples=["План з ID 5 не знайдено"],
    )
    details: List[ErrorDetail] = Field(default_factory=list, description="Деталі по полях (для помилок валідації)")
    request_id: str = Field(
        ...,
        description="Ідентифікатор запиту для пошуку в журналах (збігається із заголовком X-Request-ID)",
        examples=[_EXAMPLE_REQUEST_ID],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Невалідні вхідні дані",
                    "details": [
                        {
                            "field": "items.0.credits",
                            "message": "Input should be greater than 0",
                        }
                    ],
                    "request_id": _EXAMPLE_REQUEST_ID,
                }
            ]
        }
    )


class ApiError(Exception):
    """Бізнес-помилка, яку хендлер перетворює на ErrorResponse."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[List[ErrorDetail]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers


_ERROR_DESCRIPTIONS: Dict[int, str] = {
    400: "Некоректний запит",
    401: "Неавторизований доступ: відсутній або некоректний JWT-токен",
    403: "Доступ заборонено: ресурс належить іншому студенту",
    404: "Ресурс не знайдено",
    409: "Конфлікт: дія неможлива в поточному стані ресурсу",
    413: "Файл завеликий",
    415: "Непідтримуваний тип файлу",
    422: "Помилка валідації вхідних даних",
    429: "Забагато запитів",
}
_DEFAULT_EXAMPLES: Dict[int, Tuple[str, str]] = {
    400: ("BAD_REQUEST", "Некоректний запит"),
    401: ("UNAUTHORIZED", _UNAUTHORIZED_MESSAGE),
    403: ("PLAN_FORBIDDEN", "Цей план належить іншому студенту"),
    404: ("NOT_FOUND", "Ресурс не знайдено"),
    409: ("CONFLICT", "Дія неможлива в поточному стані ресурсу"),
    413: ("FILE_TOO_LARGE", "Файл більший за 10 МБ"),
    415: ("UNSUPPORTED_FILE_TYPE", "Дозволені лише PDF і DOCX"),
    422: ("VALIDATION_ERROR", "Невалідні вхідні дані"),
    429: ("RATE_LIMITED", "Забагато запитів, спробуйте пізніше"),
}


def error_responses(*codes: int, overrides: Optional[Dict[int, Tuple[str, str]]] = None) -> dict:
    """
    Будує блок `responses` з моделлю ErrorResponse та власним прикладом для кожного коду,
    щоб помилки потрапили в OpenAPI. `overrides` задає конкретні (code, message) для ендпоінта.
    """
    examples = {**_DEFAULT_EXAMPLES, **(overrides or {})}
    result = {}
    for status_code in codes:
        error_code, message = examples[status_code]
        details = (
            [{"field": "items.0.credits", "message": "Input should be greater than 0"}] if status_code == 422 else []
        )
        result[status_code] = {
            "model": ErrorResponse,
            "description": _ERROR_DESCRIPTIONS[status_code],
            "content": {
                "application/json": {
                    "example": {
                        "code": error_code,
                        "message": message,
                        "details": details,
                        "request_id": _EXAMPLE_REQUEST_ID,
                    }
                }
            },
        }
    return result


def get_request_id(request: Request) -> str:
    """Повертає request_id поточного запиту (його виставляє RequestIdMiddleware)."""
    return getattr(request.state, "request_id", None) or f"req_{uuid.uuid4().hex[:16]}"


class RequestIdMiddleware:
    """Бере X-Request-ID від клієнта (якщо він безпечний) або генерує новий і додає його у відповідь."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Request(scope).headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else f"req_{uuid.uuid4().hex[:16]}"
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"]
                headers.append((REQUEST_ID_HEADER.lower().encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_header)


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    body = ErrorResponse(code=code, message=message, details=details or [], request_id=request_id)
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={REQUEST_ID_HEADER: request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        if exc.status_code in (401, 403):
            logger.warning(
                "%s %s -> %s %s [%s]",
                request.method,
                request.url.path,
                exc.status_code,
                exc.code,
                get_request_id(request),
            )
        return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = err["loc"]
            field = ".".join(str(part) for part in loc[1:]) or str(loc[0])
            details.append(ErrorDetail(field=field, message=err["msg"]))
        logger.info("%s %s -> 422 VALIDATION_ERROR [%s]", request.method, request.url.path, get_request_id(request))
        return _error_response(request, 422, "VALIDATION_ERROR", "Невалідні вхідні дані", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        return _error_response(request, exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.exception("Необроблена помилка %s %s [%s]", request.method, request.url.path, get_request_id(request))
        return _error_response(request, 500, "INTERNAL_ERROR", "Внутрішня помилка сервера")


class PaginationInfo(BaseModel):
    limit: int = Field(20, ge=1, le=100, description="Кількість елементів на сторінку")
    offset: int = Field(0, ge=0, description="Зсув для пагінації")
    total: int = Field(..., ge=0, description="Загальна кількість записів")
    has_more: bool = Field(..., description="Чи є наступні сторінки")

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"limit": 20, "offset": 0, "total": 2, "has_more": False}]}
    )


bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Access-токен, отриманий у POST /api/v1/auth/microsoft або /api/v1/auth/refresh.",
)


def cors_origins() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def assert_safe_environment() -> None:
    production = os.getenv("APP_ENV", "development") == "production"
    validate_auth_settings(production)
    if "*" in cors_origins():
        raise RuntimeError("CORS_ORIGINS=* несумісний з cookie-автентифікацією, вкажіть явні адреси")


async def get_current_student_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> int:
    if credentials is None or not credentials.credentials.strip():
        raise ApiError(401, "UNAUTHORIZED", _UNAUTHORIZED_MESSAGE)
    user_id = decode_access_token(credentials.credentials.strip())
    if user_id is None:
        raise ApiError(401, "UNAUTHORIZED", _UNAUTHORIZED_MESSAGE)
    return user_id
