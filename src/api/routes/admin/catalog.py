"""
Адмінка: напрямки розвитку і профорієнтовність дисциплін (contract.md §3.9).

POST/PATCH/DELETE /admin/directions, PUT /admin/disciplines/{id}/directions.
Поля дисципліни (назва, кредити, триместр) адмін напряму не редагує: лише через чергу модерації (ADR-002).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ....db.base import normalize_text
from ....db.models.catalog import Course, CourseDirection, Direction
from ....db.models.preferences import PreferenceDirection
from ....db.models.users import User
from ....db.session import get_db
from ...common import ApiError, ErrorDetail, error_responses
from ..disciplines import Discipline, to_discipline
from .common import client_ip, require_admin, write_audit

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

_FORBIDDEN = ("FORBIDDEN_ROLE", "Потрібна роль адміністратора")
_NOT_FOUND = ("DIRECTION_NOT_FOUND", "Напрямку з ID 1 не знайдено")
_NAME_TAKEN = ("DIRECTION_NAME_TAKEN", "Напрямок з назвою «Data Science» уже існує")


class DirectionResponse(BaseModel):
    id: int = Field(..., examples=[1])
    name: str = Field(..., examples=["Data Science"])
    description: Optional[str] = None


class DirectionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=2, max_length=50, examples=["Data Science"])
    description: Optional[str] = Field(None, max_length=2000)


class DirectionPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=2000, description="Явний null очищає опис")


class DisciplineDirectionsRequest(BaseModel):
    direction_ids: List[int] = Field(
        ..., max_length=50, description="Повна заміна переліку; порожній масив = вільний вибір для всіх"
    )


def _get_direction(db: Session, direction_id: int) -> Direction:
    direction = db.get(Direction, direction_id)
    if direction is None:
        raise ApiError(404, "DIRECTION_NOT_FOUND", f"Напрямку з ID {direction_id} не знайдено")
    return direction


def _name_taken(db: Session, name: str, exclude_id: Optional[int] = None) -> bool:
    query = select(Direction.id).where(Direction.name_normalized == normalize_text(name))
    if exclude_id is not None:
        query = query.where(Direction.id != exclude_id)
    return db.scalar(query) is not None


def _name_taken_error(name: str) -> ApiError:
    return ApiError(409, "DIRECTION_NAME_TAKEN", f"Напрямок з назвою «{name}» уже існує")


def _to_response(direction: Direction) -> DirectionResponse:
    return DirectionResponse(id=direction.id, name=direction.name, description=direction.description)


@router.post(
    "/directions",
    response_model=DirectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити напрямок",
    description="Назва унікальна без урахування регістру й зайвих пробілів.",
    responses={
        201: {"description": "Напрямок створено"},
        **error_responses(401, 403, 409, 422, overrides={403: _FORBIDDEN, 409: _NAME_TAKEN}),
    },
)
def create_direction(
    payload: DirectionCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if _name_taken(db, payload.name):
        raise _name_taken_error(payload.name)
    direction = Direction(
        name=payload.name, name_normalized=normalize_text(payload.name), description=payload.description
    )
    db.add(direction)
    try:
        db.flush()
        write_audit(
            db,
            actor_id=admin.id,
            action="direction.create",
            object_type="Direction",
            object_id=direction.id,
            new_value={"name": direction.name, "description": direction.description},
            ip=client_ip(request),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _name_taken_error(payload.name)
    return _to_response(direction)


@router.patch(
    "/directions/{direction_id}",
    response_model=DirectionResponse,
    summary="Змінити напрямок",
    description="`name` і/або `description`. Явний `description: null` очищає опис.",
    responses={
        200: {"description": "Напрямок оновлено"},
        **error_responses(401, 403, 404, 409, 422, overrides={403: _FORBIDDEN, 404: _NOT_FOUND, 409: _NAME_TAKEN}),
    },
)
def patch_direction(
    payload: DirectionPatch,
    request: Request,
    direction_id: int = Path(..., gt=0, examples=[1]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    direction = _get_direction(db, direction_id)
    old, new = {}, {}
    if payload.name is not None and payload.name != direction.name:
        if _name_taken(db, payload.name, exclude_id=direction.id):
            raise _name_taken_error(payload.name)
        old["name"], new["name"] = direction.name, payload.name
        direction.name = payload.name
        direction.name_normalized = normalize_text(payload.name)
    if "description" in payload.model_fields_set and payload.description != direction.description:
        old["description"], new["description"] = direction.description, payload.description
        direction.description = payload.description

    if new:
        write_audit(
            db,
            actor_id=admin.id,
            action="direction.update",
            object_type="Direction",
            object_id=direction.id,
            old_value=old,
            new_value=new,
            ip=client_ip(request),
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise _name_taken_error(payload.name or "")
    return _to_response(direction)


@router.delete(
    "/directions/{direction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити напрямок",
    description=(
        "409 `DIRECTION_IN_USE`, якщо напрямок прив'язаний до дисциплін або збережених побажань: "
        "спершу відв'язати."
    ),
    responses={
        204: {"description": "Напрямок видалено"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={
                403: _FORBIDDEN,
                404: _NOT_FOUND,
                409: ("DIRECTION_IN_USE", "Напрямок використовується, видалити його не можна"),
            },
        ),
    },
)
def delete_direction(
    request: Request,
    direction_id: int = Path(..., gt=0, examples=[1]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    direction = _get_direction(db, direction_id)
    used_by_courses = db.scalar(
        select(func.count()).select_from(CourseDirection).where(CourseDirection.direction_id == direction.id)
    )
    used_by_preferences = db.scalar(
        select(func.count()).select_from(PreferenceDirection).where(PreferenceDirection.direction_id == direction.id)
    )
    if used_by_courses or used_by_preferences:
        raise ApiError(409, "DIRECTION_IN_USE", "Напрямок використовується, видалити його не можна")
    write_audit(
        db,
        actor_id=admin.id,
        action="direction.delete",
        object_type="Direction",
        object_id=direction.id,
        old_value={"name": direction.name, "description": direction.description},
        ip=client_ip(request),
    )
    db.delete(direction)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/disciplines/{discipline_id}/directions",
    response_model=Discipline,
    summary="Прив'язати дисципліну до напрямків",
    description=(
        "Повністю замінює перелік напрямків, для яких дисципліна профорієнтовна. "
        "Порожній масив робить дисципліну вільним вибором для всіх."
    ),
    responses={
        200: {"description": "Прив'язку оновлено"},
        **error_responses(
            401,
            403,
            404,
            422,
            overrides={403: _FORBIDDEN, 404: ("DISCIPLINE_NOT_FOUND", "Дисципліну з ID 101 не знайдено")},
        ),
    },
)
def set_discipline_directions(
    payload: DisciplineDirectionsRequest,
    request: Request,
    discipline_id: int = Path(..., gt=0, examples=[101]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    course = db.get(Course, discipline_id)
    if course is None:
        raise ApiError(404, "DISCIPLINE_NOT_FOUND", f"Дисципліну з ID {discipline_id} не знайдено")

    ids = list(dict.fromkeys(payload.direction_ids))
    directions = list(db.scalars(select(Direction).where(Direction.id.in_(ids)))) if ids else []
    missing = [i for i in ids if i not in {d.id for d in directions}]
    if missing:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Невалідні вхідні дані",
            [ErrorDetail(field="direction_ids", message=f"DIRECTION_NOT_FOUND: id {i} не існує") for i in missing],
        )

    old_ids = sorted(d.id for d in course.directions)
    course.directions = sorted(directions, key=lambda d: d.id)
    write_audit(
        db,
        actor_id=admin.id,
        action="discipline.directions.update",
        object_type="Course",
        object_id=course.id,
        old_value={"direction_ids": old_ids},
        new_value={"direction_ids": sorted(ids)},
        ip=client_ip(request),
    )
    db.commit()
    return to_discipline(course)
