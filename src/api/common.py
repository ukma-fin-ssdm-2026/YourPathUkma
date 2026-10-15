"""
Спільні елементи API YourPathUkma: єдиний формат помилок, пагінація, заглушка автентифікації.

Використання ШІ: файл створено за допомогою Claude (Anthropic) за вимогами ЛР4 та api-design.md.
Перевірка: ручний запуск сервера, перегляд у Swagger UI (/api-docs), перевірка
відповідей 401/404/409/422 для кожної кінцевої точки, звірка форматів з docs/api/api-design.md.
"""

import os
from typing import Dict, List, Optional, Tuple
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException


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
    401: ("UNAUTHORIZED", "Відсутній або некоректний токен авторизації"),
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
                    }
                }
            },
        }
    return result


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        body = ErrorResponse(code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(
            status_code=exc.status_code, content=body.model_dump(mode="json"), headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            loc = err["loc"]
            field = ".".join(str(part) for part in loc[1:]) or str(loc[0])
            details.append(ErrorDetail(field=field, message=err["msg"]))
        body = ErrorResponse(code="VALIDATION_ERROR", message="Невалідні вхідні дані", details=details)
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        body = ErrorResponse(code=f"HTTP_{exc.status_code}", message=str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        body = ErrorResponse(code="INTERNAL_ERROR", message="Внутрішня помилка сервера")
        return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


class PaginationInfo(BaseModel):
    limit: int = Field(20, ge=1, le=100, description="Кількість елементів на сторінку")
    offset: int = Field(0, ge=0, description="Зсув для пагінації")
    total: int = Field(..., ge=0, description="Загальна кількість записів")
    has_more: bool = Field(..., description="Чи є наступні сторінки")

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"limit": 20, "offset": 0, "total": 2, "has_more": False}]}
    )


MOCK_STUDENT_ID = 42

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="JWT після входу через Google Workspace SSO. У заглушці приймається будь-який непорожній токен.",
)


async def get_current_student_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> int:
    if credentials is None:
        if os.getenv("MCP_DEV_MODE") == "1":
            return MOCK_STUDENT_ID
        raise ApiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації")
    if not credentials.credentials.strip():
        raise ApiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації")
    return MOCK_STUDENT_ID