"""
Адмінка: запуск парсингу (SyncJob) і черга модерації (contract.md §3.9, ADR-002).

POST/GET /admin/sync-jobs, GET /admin/sync-jobs/{id},
GET /admin/moderation-items, POST /admin/moderation-items/{id}/approve|reject, POST .../bulk-review.

Зміна каталогу від парсера потрапляє в `courses` лише після схвалення. Формат `payload` елемента
модерації описано в `CoursePayload` нижче: перевірте, що парсер формує його саме так.

TODO(команда): POST /admin/sync-jobs створює задачу зі статусом `queued`, але сам парсер сюди не підключено.
Поки воркер не підхопить задачу й не переведе її в `running`/`succeeded`/`failed`, нова задача для того
самого джерела дасть 409 SYNC_JOB_ALREADY_RUNNING (часткова унікальність у БД).
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ....db import enums as db_enums
from ....db.base import normalize_text, utcnow
from ....db.models.admin import ModerationItem, SyncJob
from ....db.models.catalog import Course
from ....db.models.users import User
from ....db.session import get_db
from ...common import ApiError, ErrorDetail, PaginationInfo, error_responses
from .common import client_ip, require_admin, write_audit

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

_FORBIDDEN = ("FORBIDDEN_ROLE", "Потрібна роль адміністратора")
_JOB_NOT_FOUND = ("SYNC_JOB_NOT_FOUND", "Задачу синхронізації з ID 31 не знайдено")
_ITEM_NOT_FOUND = ("MODERATION_ITEM_NOT_FOUND", "Елемент модерації з ID 501 не знайдено")
_ITEM_REVIEWED = ("MODERATION_ITEM_ALREADY_REVIEWED", "Елемент модерації вже схвалено або відхилено")

_ADD_REQUIRED = ("saz_code", "title", "credits", "trimester", "recommended_year", "kind")


# ---------- Схеми ----------


class UserRef(BaseModel):
    id: int
    full_name: str


class SyncJobCreate(BaseModel):
    source: db_enums.SyncSource = Field(..., examples=["saz_catalog"])


class SyncJobResponse(BaseModel):
    id: int = Field(..., examples=[31])
    source: db_enums.SyncSource
    initiator: db_enums.SyncInitiator
    initiated_by: Optional[UserRef] = Field(None, description="null, якщо задачу запустив планувальник")
    status: db_enums.SyncJobStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    added_count: int
    updated_count: int
    error_message: Optional[str] = None


class PaginatedSyncJobs(BaseModel):
    sync_jobs: List[SyncJobResponse]
    pagination: PaginationInfo


class ModerationItemResponse(BaseModel):
    id: int = Field(..., examples=[501])
    sync_job_id: int
    course_id: Optional[int] = Field(None, description="null для change_type = add до схвалення")
    change_type: db_enums.ModerationChangeType
    payload: Dict[str, Any] = Field(..., description="Рендерити як текст: вміст із САЗ недовірений (R5, R7)")
    diff: Optional[Dict[str, Any]] = Field(None, description="null для add")
    status: db_enums.ModerationStatus
    reviewed_by: Optional[UserRef] = None
    reviewed_at: Optional[datetime] = None


class PaginatedModerationItems(BaseModel):
    moderation_items: List[ModerationItemResponse]
    pagination: PaginationInfo


class RejectRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000, description="Необов'язкова причина відхилення")


class BulkReviewRequest(BaseModel):
    item_ids: List[int] = Field(..., min_length=1, max_length=100)
    decision: Literal["approve", "reject"]


class SkippedItem(BaseModel):
    id: int
    code: str


class BulkReviewResponse(BaseModel):
    approved: List[int]
    rejected: List[int]
    skipped: List[SkippedItem]


class CoursePayload(BaseModel):
    """
    Очікуваний вміст `moderation_items.payload` для add/update (зайві ключі ігноруються).
    add: обов'язкові saz_code, title, credits, trimester (1–3), recommended_year (1–4), kind.
    update: будь-яка підмножина title, description, credits, trimester, recommended_year, kind.
    remove: payload не читається, дисципліна архівується.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    saz_code: Optional[str] = Field(None, min_length=1, max_length=64)
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    description: Optional[str] = Field(None, max_length=20000)
    credits: Optional[float] = Field(None, gt=0, le=30)
    trimester: Optional[int] = Field(None, ge=1, le=3)
    recommended_year: Optional[int] = Field(None, ge=1, le=4)
    kind: Optional[db_enums.CourseKind] = None


# ---------- Допоміжні функції ----------


def _users_by_id(db: Session, ids: set) -> Dict[int, User]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))}


def _ref(users: Dict[int, User], user_id: Optional[int]) -> Optional[UserRef]:
    user = users.get(user_id) if user_id is not None else None
    return UserRef(id=user.id, full_name=user.full_name) if user else None


def _job_response(job: SyncJob, users: Dict[int, User]) -> SyncJobResponse:
    return SyncJobResponse(
        id=job.id,
        source=job.source,
        initiator=job.initiator,
        initiated_by=_ref(users, job.initiated_by),
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        added_count=job.added_count,
        updated_count=job.updated_count,
        error_message=job.error_message,
    )


def _item_response(item: ModerationItem, users: Dict[int, User]) -> ModerationItemResponse:
    return ModerationItemResponse(
        id=item.id,
        sync_job_id=item.sync_job_id,
        course_id=item.course_id,
        change_type=item.change_type,
        payload=item.payload or {},
        diff=item.diff,
        status=item.status,
        reviewed_by=_ref(users, item.reviewed_by),
        reviewed_at=item.reviewed_at,
    )


def _payload_error(message: str, details: Optional[List[ErrorDetail]] = None) -> ApiError:
    return ApiError(422, "MODERATION_PAYLOAD_INVALID", message, details or [])


def _check_change(db: Session, item: ModerationItem) -> Tuple[Optional[Course], Optional[CoursePayload]]:
    if item.change_type == db_enums.ModerationChangeType.REMOVE:
        course = db.get(Course, item.course_id) if item.course_id else None
        if course is None:
            raise _payload_error("Дисципліну для архівації не знайдено в каталозі")
        return course, None

    try:
        data = CoursePayload.model_validate(item.payload or {})
    except ValidationError as exc:
        raise _payload_error(
            "Некоректний payload елемента модерації",
            [ErrorDetail(field=".".join(str(p) for p in e["loc"]) or "payload", message=e["msg"]) for e in exc.errors()],
        )

    if item.change_type == db_enums.ModerationChangeType.ADD:
        missing = [name for name in _ADD_REQUIRED if getattr(data, name) is None]
        if missing:
            raise _payload_error(
                "Для додавання дисципліни бракує полів",
                [ErrorDetail(field=name, message="Поле обов'язкове для change_type = add") for name in missing],
            )
        if db.scalar(select(Course.id).where(Course.saz_code == data.saz_code)) is not None:
            raise _payload_error(
                "Дисципліна з таким saz_code уже є в каталозі",
                [ErrorDetail(field="saz_code", message=f"saz_code {data.saz_code} уже використовується")],
            )
        return None, data

    course = db.get(Course, item.course_id) if item.course_id else None
    if course is None:
        raise _payload_error("Дисципліну для оновлення не знайдено в каталозі")
    return course, data


def _apply_change(db: Session, item: ModerationItem, course: Optional[Course], data: Optional[CoursePayload]) -> None:
    change = item.change_type
    if change == db_enums.ModerationChangeType.ADD:
        course = Course(
            saz_code=data.saz_code,
            title=data.title,
            title_normalized=normalize_text(data.title),
            description=data.description or "",
            credits=data.credits,
            trimester=db_enums.Trimester.from_number(data.trimester),
            recommended_year=data.recommended_year,
            kind=data.kind,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
            last_sync_job_id=item.sync_job_id,
        )
        db.add(course)
        db.flush()
        item.course_id = course.id
    elif change == db_enums.ModerationChangeType.UPDATE:
        if data.title is not None:
            course.title = data.title
            course.title_normalized = normalize_text(data.title)
        if data.description is not None:
            course.description = data.description
        if data.credits is not None:
            course.credits = data.credits
        if data.trimester is not None:
            course.trimester = db_enums.Trimester.from_number(data.trimester)
        if data.recommended_year is not None:
            course.recommended_year = data.recommended_year
        if data.kind is not None:
            course.kind = data.kind
        course.last_sync_job_id = item.sync_job_id
    else:  # REMOVE
        course.publication_status = db_enums.PublicationStatus.ARCHIVED
        course.last_sync_job_id = item.sync_job_id


def _review_item(
    db: Session,
    item_id: int,
    decision: Literal["approve", "reject"],
    admin: User,
    ip: Optional[str],
    reason: Optional[str] = None,
) -> ModerationItem:
    item = db.get(ModerationItem, item_id)
    if item is None:
        raise ApiError(404, "MODERATION_ITEM_NOT_FOUND", f"Елемент модерації з ID {item_id} не знайдено")
    if item.status != db_enums.ModerationStatus.PENDING:
        raise ApiError(409, "MODERATION_ITEM_ALREADY_REVIEWED", "Елемент модерації вже схвалено або відхилено")

    course = data = None
    if decision == "approve":
        course, data = _check_change(db, item)

    new_status = db_enums.ModerationStatus.APPROVED if decision == "approve" else db_enums.ModerationStatus.REJECTED
    claimed = db.execute(
        update(ModerationItem)
        .where(ModerationItem.id == item.id, ModerationItem.status == db_enums.ModerationStatus.PENDING)
        .values(
            status=new_status,
            reviewed_by=admin.id,
            reviewed_at=utcnow(),
            review_reason=reason if decision == "reject" else None,
        )
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise ApiError(409, "MODERATION_ITEM_ALREADY_REVIEWED", "Елемент модерації вже схвалено або відхилено")
    db.refresh(item)

    if decision == "approve":
        _apply_change(db, item, course, data)
    write_audit(
        db,
        actor_id=admin.id,
        action=f"moderation.{decision}",
        object_type="ModerationItem",
        object_id=item.id,
        new_value={"change_type": item.change_type.value, "course_id": item.course_id, "sync_job_id": item.sync_job_id},
        ip=ip,
    )
    db.commit()
    return item


# ---------- SyncJob ----------


@router.post(
    "/sync-jobs",
    response_model=SyncJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустити парсинг",
    description="Створює задачу зі статусом `queued`. На джерело не більше однієї активної задачі (409).",
    responses={
        202: {"description": "Задачу поставлено в чергу"},
        **error_responses(
            401,
            403,
            409,
            422,
            overrides={
                403: _FORBIDDEN,
                409: ("SYNC_JOB_ALREADY_RUNNING", "Для цього джерела вже виконується синхронізація"),
            },
        ),
    },
)
def start_sync_job(
    payload: SyncJobCreate,
    request: Request,
    response: Response,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conflict = ApiError(409, "SYNC_JOB_ALREADY_RUNNING", "Для цього джерела вже виконується синхронізація")
    active = db.scalar(
        select(SyncJob.id).where(
            SyncJob.source == payload.source,
            SyncJob.status.in_([db_enums.SyncJobStatus.QUEUED, db_enums.SyncJobStatus.RUNNING]),
        )
    )
    if active is not None:
        raise conflict

    job = SyncJob(
        source=payload.source,
        initiator=db_enums.SyncInitiator.ADMIN,
        initiated_by=admin.id,
        status=db_enums.SyncJobStatus.QUEUED,
    )
    db.add(job)
    try:
        db.flush()
        write_audit(
            db,
            actor_id=admin.id,
            action="sync_job.start",
            object_type="SyncJob",
            object_id=job.id,
            new_value={"source": payload.source.value},
            ip=client_ip(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict
    response.headers["Location"] = f"/api/v1/admin/sync-jobs/{job.id}"
    return _job_response(job, {admin.id: admin})


@router.get(
    "/sync-jobs",
    response_model=PaginatedSyncJobs,
    summary="Журнал синхронізацій",
    description="Сортування за `started_at` за спаданням.",
    responses={200: {"description": "Журнал отримано"}, **error_responses(401, 403, 422, overrides={403: _FORBIDDEN})},
)
def list_sync_jobs(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: Optional[db_enums.SyncSource] = Query(None),
    job_status: Optional[db_enums.SyncJobStatus] = Query(None, alias="status"),
):
    filters = []
    if source:
        filters.append(SyncJob.source == source)
    if job_status:
        filters.append(SyncJob.status == job_status)
    total = db.scalar(select(func.count(SyncJob.id)).where(*filters))
    jobs = db.scalars(
        select(SyncJob).where(*filters).order_by(SyncJob.started_at.desc(), SyncJob.id.desc()).offset(offset).limit(limit)
    ).all()
    users = _users_by_id(db, {j.initiated_by for j in jobs})
    return PaginatedSyncJobs(
        sync_jobs=[_job_response(j, users) for j in jobs],
        pagination=PaginationInfo(limit=limit, offset=offset, total=total, has_more=(offset + limit) < total),
    )


@router.get(
    "/sync-jobs/{job_id}",
    response_model=SyncJobResponse,
    summary="Деталі синхронізації",
    description="Сирий HTML-знімок (`raw_snapshot`) в API не повертається. Фронтенд опитує, доки статус `queued`/`running`.",
    responses={
        200: {"description": "Задачу знайдено"},
        **error_responses(401, 403, 404, 422, overrides={403: _FORBIDDEN, 404: _JOB_NOT_FOUND}),
    },
)
def get_sync_job(job_id: int = Path(..., gt=0, examples=[31]), db: Session = Depends(get_db)):
    job = db.get(SyncJob, job_id)
    if job is None:
        raise ApiError(404, "SYNC_JOB_NOT_FOUND", f"Задачу синхронізації з ID {job_id} не знайдено")
    return _job_response(job, _users_by_id(db, {job.initiated_by}))


# ---------- Модерація ----------


@router.get(
    "/moderation-items",
    response_model=PaginatedModerationItems,
    summary="Черга модерації",
    description="За замовчуванням лише `pending`. Сортування за `id` зростанням: найстаріші першими.",
    responses={200: {"description": "Чергу отримано"}, **error_responses(401, 403, 422, overrides={403: _FORBIDDEN})},
)
def list_moderation_items(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    item_status: db_enums.ModerationStatus = Query(db_enums.ModerationStatus.PENDING, alias="status"),
    sync_job_id: Optional[int] = Query(None, gt=0),
    change_type: Optional[db_enums.ModerationChangeType] = Query(None),
):
    filters = [ModerationItem.status == item_status]
    if sync_job_id:
        filters.append(ModerationItem.sync_job_id == sync_job_id)
    if change_type:
        filters.append(ModerationItem.change_type == change_type)
    total = db.scalar(select(func.count(ModerationItem.id)).where(*filters))
    items = db.scalars(select(ModerationItem).where(*filters).order_by(ModerationItem.id).offset(offset).limit(limit)).all()
    users = _users_by_id(db, {i.reviewed_by for i in items})
    return PaginatedModerationItems(
        moderation_items=[_item_response(i, users) for i in items],
        pagination=PaginationInfo(limit=limit, offset=offset, total=total, has_more=(offset + limit) < total),
    )


@router.post(
    "/moderation-items/bulk-review",
    response_model=BulkReviewResponse,
    summary="Масово схвалити або відхилити",
    description=(
        "Кожен елемент обробляється окремо. Те, що не вдалося, повертається в `skipped` з кодом "
        "(`MODERATION_ITEM_NOT_FOUND`, `MODERATION_ITEM_ALREADY_REVIEWED`, `MODERATION_PAYLOAD_INVALID`)."
    ),
    responses={200: {"description": "Пакет оброблено"}, **error_responses(401, 403, 422, overrides={403: _FORBIDDEN})},
)
def bulk_review(
    payload: BulkReviewRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ip = client_ip(request)
    approved: List[int] = []
    rejected: List[int] = []
    skipped: List[SkippedItem] = []
    for item_id in dict.fromkeys(payload.item_ids):
        try:
            with db.begin_nested():
                _review_item(db, item_id, payload.decision, admin, ip)
        except ApiError as exc:
            skipped.append(SkippedItem(id=item_id, code=exc.code))
        except IntegrityError:
            skipped.append(SkippedItem(id=item_id, code="CONFLICT"))
        except Exception:
            skipped.append(SkippedItem(id=item_id, code="INTERNAL_ERROR"))
        else:
            (approved if payload.decision == "approve" else rejected).append(item_id)
    db.commit()
    return BulkReviewResponse(approved=approved, rejected=rejected, skipped=skipped)


@router.post(
    "/moderation-items/{item_id}/approve",
    response_model=ModerationItemResponse,
    summary="Схвалити зміну",
    description=(
        "Застосовує зміну до каталогу: `add` створює дисципліну, `update` змінює поля, `remove` архівує. "
        "Якщо `payload` непридатний — 422 `MODERATION_PAYLOAD_INVALID`, елемент лишається `pending`."
    ),
    responses={
        200: {"description": "Зміну схвалено й застосовано"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={403: _FORBIDDEN, 404: _ITEM_NOT_FOUND, 409: _ITEM_REVIEWED},
        ),
    },
)
def approve_item(
    request: Request,
    item_id: int = Path(..., gt=0, examples=[501]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        item = _review_item(db, item_id, "approve", admin, client_ip(request))
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Каталог змінив інший запит, повторіть спробу")
    return _item_response(item, {admin.id: admin})


@router.post(
    "/moderation-items/{item_id}/reject",
    response_model=ModerationItemResponse,
    summary="Відхилити зміну",
    description="Тіло необов'язкове: `{ \"reason\": \"...\" }`. Каталог не змінюється.",
    responses={
        200: {"description": "Зміну відхилено"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={403: _FORBIDDEN, 404: _ITEM_NOT_FOUND, 409: _ITEM_REVIEWED},
        ),
    },
)
def reject_item(
    request: Request,
    payload: Optional[RejectRequest] = None,
    item_id: int = Path(..., gt=0, examples=[501]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = _review_item(db, item_id, "reject", admin, client_ip(request), reason=payload.reason if payload else None)
    return _item_response(item, {admin.id: admin})