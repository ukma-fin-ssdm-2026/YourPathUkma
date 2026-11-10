"""Адмінські маршрути для віддаленого входу до САЗ.

Використання ШІ: маршрути додано Codex. Перевірка: pytest і OpenAPI.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from ....db.models.users import User
from ....db.session import get_db
from ....parser.config import SazSettings, load_settings, remote_login_enabled
from ....parser.fetcher import clear_session_state
from ....parser.remote_login import LoginBusy, LoginNotFound, LoginPending, LoginUnavailable, remote_login
from ...common import ApiError
from .common import client_ip, require_admin, write_audit

router = APIRouter(prefix="/api/v1/admin/saz-session", tags=["Admin"])
NO_STORE = {"Cache-Control": "no-store"}


class SessionStatus(BaseModel):
    connected: bool


class LoginStarted(BaseModel):
    id: str


class Click(BaseModel):
    kind: Literal["click"]
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)


class Key(BaseModel):
    kind: Literal["key"]
    key: Literal[
        "Enter",
        "Tab",
        "Shift+Tab",
        "Backspace",
        "Delete",
        "Escape",
        "ArrowUp",
        "ArrowDown",
        "ArrowLeft",
        "ArrowRight",
        "Home",
        "End",
        "PageUp",
        "PageDown",
        "Control+A",
    ]


class Text(BaseModel):
    kind: Literal["text"]
    text: str = Field(min_length=1, max_length=512, repr=False)


class LoginInput(BaseModel):
    host: str = Field(min_length=1, max_length=64)
    action: Annotated[Click | Key | Text, Field(discriminator="kind")]


def configured_settings() -> SazSettings:
    if not remote_login_enabled():
        raise ApiError(503, "SAZ_REMOTE_LOGIN_DISABLED", "Віддалений вхід до САЗ вимкнено")
    try:
        return load_settings()
    except ValueError:
        raise ApiError(503, "SAZ_REMOTE_LOGIN_CONFIG", "Віддалений вхід до САЗ не налаштовано") from None


async def browser_call(operation):
    try:
        return await operation
    except LoginNotFound:
        raise ApiError(404, "SAZ_LOGIN_NOT_FOUND", "Вікно входу закрито або час входу вичерпано") from None
    except LoginBusy:
        raise ApiError(409, "SAZ_LOGIN_BUSY", "Вхід до САЗ уже відкрито") from None
    except LoginPending:
        raise ApiError(409, "SAZ_LOGIN_PENDING", "Завершіть вхід до САЗ у вікні браузера") from None
    except LoginUnavailable:
        raise ApiError(503, "SAZ_LOGIN_UNAVAILABLE", "Не вдалося відкрити або перевірити вікно входу до САЗ") from None


@router.get("", response_model=SessionStatus, summary="Стан серверної сесії САЗ")
def session_status(response: Response, _admin: User = Depends(require_admin)):
    response.headers.update(NO_STORE)
    return SessionStatus(connected=configured_settings().state_path.is_file())


@router.delete("", status_code=204, summary="Відключити серверну сесію САЗ")
def disconnect_session(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        clear_session_state(configured_settings())
    except OSError:
        raise ApiError(503, "SAZ_SESSION_UNAVAILABLE", "Не вдалося видалити сесію САЗ") from None
    write_audit(db, actor_id=admin.id, action="saz_session.disconnect", object_type="SazSession", ip=client_ip(request))
    db.commit()
    return Response(status_code=204, headers=NO_STORE)


@router.post(
    "/login",
    response_model=LoginStarted,
    status_code=201,
    summary="Відкрити браузер для входу до САЗ",
    openapi_extra={"x-ai-usage": "Використання ШІ: Codex додав віддалений вхід. Перевірка: pytest."},
)
async def start_login(response: Response, admin: User = Depends(require_admin)):
    response.headers.update(NO_STORE)
    settings = configured_settings()
    return LoginStarted(id=await browser_call(remote_login.start(admin.id, settings)))


@router.get(
    "/login/{login_id}/frame",
    summary="Кадр браузера САЗ",
    responses={200: {"content": {"image/jpeg": {}}, "description": "Кадр браузера"}},
)
async def login_frame(login_id: str, admin: User = Depends(require_admin)):
    configured_settings()
    frame, host = await browser_call(remote_login.frame(admin.id, login_id))
    return Response(frame, media_type="image/jpeg", headers={**NO_STORE, "X-SAZ-Login-Host": host})


@router.post("/login/{login_id}/input", status_code=204, summary="Керувати браузером САЗ")
async def login_input(login_id: str, request: Request, admin: User = Depends(require_admin)):
    configured_settings()
    # Parsing here keeps typed credentials out of FastAPI's validation error handler.
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 4096:
            raise HTTPException(status_code=413)
        data.extend(chunk)
    try:
        command = LoginInput.model_validate_json(data)
    except ValidationError:
        raise ApiError(422, "SAZ_LOGIN_INPUT_INVALID", "Некоректна дія у вікні входу") from None
    await browser_call(remote_login.input(admin.id, login_id, command.host, command.action))
    return Response(status_code=204, headers=NO_STORE)


@router.post("/login/{login_id}/complete", status_code=204, summary="Зберегти перевірену сесію САЗ")
async def complete_login(
    login_id: str, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    configured_settings()
    await browser_call(remote_login.complete(admin.id, login_id))
    write_audit(db, actor_id=admin.id, action="saz_session.connect", object_type="SazSession", ip=client_ip(request))
    db.commit()
    return Response(status_code=204, headers=NO_STORE)


@router.delete("/login/{login_id}", status_code=204, summary="Закрити браузер САЗ")
async def cancel_login(login_id: str, admin: User = Depends(require_admin)):
    configured_settings()
    await browser_call(remote_login.cancel(admin.id, login_id))
    return Response(status_code=204, headers=NO_STORE)
