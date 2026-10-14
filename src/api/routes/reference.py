"""
Ресурс «Довідники» (Reference): напрямки розвитку і викладачі (GET /directions, GET /instructors).

Дані поки що в пам'яті (заглушка). Назви напрямків збігаються з Discipline.directions
у каталозі, щоб фільтр GET /disciplines?direction= працював з тими самими значеннями.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ...db import models
from ...db.base import normalize_text
from ...db.session import get_db
from ..common import PaginationInfo, error_responses, get_current_student_id

router = APIRouter(prefix="/api/v1", tags=["Reference"], dependencies=[Depends(get_current_student_id)])


class Direction(BaseModel):
    id: int = Field(..., description="ID напрямку", examples=[1])
    name: str = Field(..., description="Назва напрямку", examples=["Data Science"])
    description: Optional[str] = Field(None, description="Опис напрямку")


class DirectionsResponse(BaseModel):
    directions: List[Direction] = Field(..., description="Усі напрямки розвитку")


class Instructor(BaseModel):
    id: int = Field(..., description="ID викладача", examples=[7])
    full_name: str = Field(..., description="ПІБ викладача", examples=["Петренко І. М."])


class PaginatedInstructorsResponse(BaseModel):
    instructors: List[Instructor] = Field(..., description="Список викладачів")
    pagination: PaginationInfo = Field(..., description="Метадані пагінації")


@router.get(
    "/directions",
    response_model=DirectionsResponse,
    summary="Довідник напрямків розвитку",
    description="Усі напрямки без пагінації. `name` збігається зі значеннями в каталозі дисциплін.",
    responses={200: {"description": "Довідник отримано"}, **error_responses(401)},
)
def list_directions(db: Session = Depends(get_db)):
    directions = db.scalars(select(models.Direction).order_by(models.Direction.id)).all()
    return DirectionsResponse(
        directions=[Direction(id=d.id, name=d.name, description=d.description) for d in directions]
    )


@router.get(
    "/instructors",
    response_model=PaginatedInstructorsResponse,
    summary="Довідник викладачів",
    description="Для вибору бажаних і небажаних викладачів та фільтра каталогу. Пошук за підрядком ПІБ.",
    responses={200: {"description": "Довідник отримано"}, **error_responses(401, 422)},
)
def list_instructors(
    db: Session = Depends(get_db),
    q: Optional[str] = Query(None, min_length=2, max_length=100, description="Підрядок ПІБ (від 2 символів)"),
    limit: int = Query(20, ge=1, le=100, description="Максимальна кількість викладачів на сторінку"),
    offset: int = Query(0, ge=0, description="Кількість викладачів, які треба пропустити"),
):
    query = select(models.Instructor)
    if q:
        query = query.where(models.Instructor.full_name_normalized.contains(normalize_text(q), autoescape=True))

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    instructors = db.scalars(query.order_by(models.Instructor.id).offset(offset).limit(limit)).all()

    return PaginatedInstructorsResponse(
        instructors=[Instructor(id=i.id, full_name=i.full_name) for i in instructors],
        pagination=PaginationInfo(
            limit=limit,
            offset=offset,
            total=total,
            has_more=(offset + limit) < total,
        ),
    )
