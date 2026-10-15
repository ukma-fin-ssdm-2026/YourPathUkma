"""
Адмінка: журнал аудиту (contract.md §3.9). Лише читання: журнал append-only (SEC-001).

GET /admin/audit-log, GET /admin/audit-log/{id}.
`old_value`/`new_value` містять PII, тому в списку їх немає, їх показує лише запис за id.
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.routes.admin.common import require_admin


from ....db import enums as db_enums
from ....db.models.admin import AuditLog
from ....db.models.users import User
from ....db.session import get_db
from ...common import ApiError, PaginationInfo, error_responses

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

_FORBIDDEN = ("FORBIDDEN_ROLE", "Потрібна роль адміністратора")


class Actor(BaseModel):
    id: int
    full_name: str


class AuditLogEntry(BaseModel):
    id: int = Field(..., examples=[9001])
    actor: Optional[Actor] = Field(None, description="null для анонімних спроб")
    action: str = Field(..., examples=["plan.read"])
    object_type: str = Field(..., examples=["IndividualPlan"])
    object_id: Optional[int] = None
    outcome: db_enums.AuditOutcome
    ip: Optional[str] = None
    created_at: datetime


class AuditLogEntryDetail(AuditLogEntry):
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class PaginatedAuditLog(BaseModel):
    audit_log: List[AuditLogEntry]
    pagination: PaginationInfo


def _entry_fields(entry: AuditLog, actor_name: Optional[str]) -> dict:
    return dict(
        id=entry.id,
        actor=Actor(id=entry.actor_id, full_name=actor_name) if entry.actor_id is not None and actor_name else None,
        action=entry.action,
        object_type=entry.object_type,
        object_id=entry.object_id,
        outcome=entry.outcome,
        ip=str(entry.ip) if entry.ip else None,
        created_at=entry.created_at,
    )


@router.get(
    "/audit-log",
    response_model=PaginatedAuditLog,
    summary="Журнал доступу і змін",
    description=(
        "Сортування за `created_at` за спаданням. Приклад у контракті показує `limit = 50`, тому для журналу "
        "значення за замовчуванням 50 (максимум 100)."
    ),
    responses={200: {"description": "Журнал отримано"}, **error_responses(401, 403, 422, overrides={403: _FORBIDDEN})},
)
def list_audit_log(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor_id: Optional[int] = Query(None, gt=0),
    action: Optional[str] = Query(None, min_length=1, max_length=64, description="Напр. plan.read, user.update"),
    object_type: Optional[str] = Query(None, min_length=1, max_length=64),
    object_id: Optional[int] = Query(None, gt=0),
    outcome: Optional[db_enums.AuditOutcome] = Query(None),
    date_from: Optional[datetime] = Query(None, alias="from", description="created_at >= from"),
    date_to: Optional[datetime] = Query(None, alias="to", description="created_at <= to"),
):
    filters = []
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)
    if action:
        filters.append(AuditLog.action == action)
    if object_type:
        filters.append(AuditLog.object_type == object_type)
    if object_id:
        filters.append(AuditLog.object_id == object_id)
    if outcome:
        filters.append(AuditLog.outcome == outcome)
    if date_from:
        filters.append(AuditLog.created_at >= date_from)
    if date_to:
        filters.append(AuditLog.created_at <= date_to)

    total = db.scalar(select(func.count(AuditLog.id)).where(*filters))
    rows = db.execute(
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return PaginatedAuditLog(
        audit_log=[AuditLogEntry(**_entry_fields(entry, name)) for entry, name in rows],
        pagination=PaginationInfo(limit=limit, offset=offset, total=total, has_more=(offset + limit) < total),
    )


@router.get(
    "/audit-log/{entry_id}",
    response_model=AuditLogEntryDetail,
    summary="Запис журналу з old_value/new_value",
    responses={
        200: {"description": "Запис знайдено"},
        **error_responses(
            401,
            403,
            404,
            422,
            overrides={403: _FORBIDDEN, 404: ("AUDIT_ENTRY_NOT_FOUND", "Запис журналу з ID 9001 не знайдено")},
        ),
    },
)
def get_audit_entry(entry_id: int = Path(..., gt=0, examples=[9001]), db: Session = Depends(get_db)):
    row = db.execute(
        select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.actor_id).where(AuditLog.id == entry_id)
    ).first()
    if row is None:
        raise ApiError(404, "AUDIT_ENTRY_NOT_FOUND", f"Запис журналу з ID {entry_id} не знайдено")
    entry, name = row
    return AuditLogEntryDetail(**_entry_fields(entry, name), old_value=entry.old_value, new_value=entry.new_value)