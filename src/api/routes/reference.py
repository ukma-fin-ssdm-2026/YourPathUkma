"""
Ресурс «Довідники» (Reference): напрямки розвитку і викладачі (GET /directions, GET /instructors).

Дані поки що в пам'яті (заглушка). Назви напрямків збігаються з Discipline.directions
у каталозі, щоб фільтр GET /disciplines?direction= працював з тими самими значеннями.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

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


_DIRECTIONS = [
    Direction(id=1, name="Data Science", description="Аналіз даних і машинне навчання"),
    Direction(id=2, name="Cybersecurity", description=None),
    Direction(
        id=3,
        name="Software Engineering",
        description="Проєктування та розробка програмних систем",
    ),
]

_INSTRUCTORS = [
    Instructor(id=7, full_name="Петренко І. М."),
    Instructor(id=8, full_name="Коваленко О. В."),
    Instructor(id=9, full_name="Мельник Т. С."),
    Instructor(id=10, full_name="Шевченко А. П."),
]


@router.get(
    "/directions",
    response_model=DirectionsResponse,
    summary="Довідник напрямків розвитку",
    description="Усі напрямки без пагінації. `name` збігається зі значеннями в каталозі дисциплін.",
    responses={200: {"description": "Довідник отримано"}, **error_responses(401)},
)
async def list_directions():
    return DirectionsResponse(directions=_DIRECTIONS)


@router.get(
    "/instructors",
    response_model=PaginatedInstructorsResponse,
    summary="Довідник викладачів",
    description="Для вибору бажаних і небажаних викладачів та фільтра каталогу. Пошук за підрядком ПІБ.",
    responses={200: {"description": "Довідник отримано"}, **error_responses(401, 422)},
)
async def list_instructors(
    q: Optional[str] = Query(None, min_length=2, max_length=100, description="Підрядок ПІБ (від 2 символів)"),
    limit: int = Query(20, ge=1, le=100, description="Максимальна кількість викладачів на сторінку"),
    offset: int = Query(0, ge=0, description="Кількість викладачів, які треба пропустити"),
):
    result = list(_INSTRUCTORS)
    if q:
        result = [i for i in result if q.lower() in i.full_name.lower()]

    return PaginatedInstructorsResponse(
        instructors=result[offset : offset + limit],
        pagination=PaginationInfo(
            limit=limit,
            offset=offset,
            total=len(result),
            has_more=(offset + limit) < len(result),
        ),
    )
