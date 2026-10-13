"""
Ресурс «Дисципліни» (Disciplines): read-only каталог вибіркових і нормативних дисциплін (use-case 9).
Дані в реальній системі надходять із САЗ парсингом; тут — заглушки.
"""

from enum import Enum
from typing import List, Optional
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from ..common import (
    ApiError,
    ErrorDetail,
    PaginationInfo,
    error_responses,
    get_current_student_id,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Disciplines"],
    dependencies=[Depends(get_current_student_id)],
)


class DisciplineType(str, Enum):
    NORMATIVE = "normative"
    ELECTIVE = "elective"


class Discipline(BaseModel):
    id: int = Field(..., description="Унікальний ID дисципліни (як у каталозі САЗ)", examples=[101])
    title: str = Field(..., description="Назва дисципліни", examples=["Функціональне програмування"])
    description: str = Field(..., description="Короткий опис змісту")
    discipline_type: DisciplineType = Field(..., description="Нормативна (від деканату) або вибіркова")
    instructor: str = Field(..., description="Викладач", examples=["Петренко І. М."])
    recommended_year: int = Field(..., ge=1, le=4, description="Рекомендований рік навчання")
    trimester: int = Field(..., ge=1, le=3, description="Триместр (1 — осінь, 2 — весна, 3 — літо)")
    credits: float = Field(..., gt=0, description="Кількість кредитів ECTS")
    directions: List[str] = Field(
        default_factory=list,
        description="Напрямки, для яких дисципліна профорієнтовна. Порожньо — дисципліна вільного вибору",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 101,
                    "title": "Функціональне програмування",
                    "description": "Основи функціональної парадигми.",
                    "discipline_type": "elective",
                    "instructor": "Петренко І. М.",
                    "recommended_year": 2,
                    "trimester": 1,
                    "credits": 5.0,
                    "directions": ["Software Engineering", "Data Science"],
                }
            ]
        }
    )


class PaginatedDisciplinesResponse(BaseModel):
    disciplines: List[Discipline] = Field(..., description="Список дисциплін")
    pagination: PaginationInfo = Field(..., description="Метадані пагінації")


_CATALOG = [
    Discipline(
        id=101,
        title="Функціональне програмування",
        description="Основи функціональної парадигми.",
        discipline_type=DisciplineType.ELECTIVE,
        instructor="Петренко І. М.",
        recommended_year=2,
        trimester=1,
        credits=5.0,
        directions=["Software Engineering", "Data Science"],
    ),
    Discipline(
        id=102,
        title="Основи кібербезпеки",
        description="Базові принципи захисту інформації.",
        discipline_type=DisciplineType.ELECTIVE,
        instructor="Коваленко О. В.",
        recommended_year=3,
        trimester=2,
        credits=4.0,
        directions=["Cybersecurity"],
    ),
    Discipline(
        id=205,
        title="Управління цифровим продуктом",
        description="Життєвий цикл цифрового продукту.",
        discipline_type=DisciplineType.ELECTIVE,
        instructor="Мельник Т. С.",
        recommended_year=2,
        trimester=2,
        credits=3.0,
        directions=[],
    ),
    Discipline(
        id=301,
        title="Алгоритми та структури даних",
        description="Нормативна дисципліна від деканату.",
        discipline_type=DisciplineType.NORMATIVE,
        instructor="Шевченко А. П.",
        recommended_year=2,
        trimester=1,
        credits=6.0,
        directions=[],
    ),
]


@router.get(
    "/disciplines",
    response_model=PaginatedDisciplinesResponse,
    summary="Отримати каталог дисциплін",
    description="Каталог дисциплін з фільтрами (напрямок, триместр, викладач, кредити, рік, тип) та offset-пагінацією.",
    responses={200: {"description": "Каталог отримано"}, **error_responses(401, 422)},
)
async def list_disciplines(
    limit: int = Query(20, ge=1, le=100, description="Максимальна кількість дисциплін на сторінку"),
    offset: int = Query(0, ge=0, description="Кількість дисциплін, які треба пропустити"),
    direction: Optional[str] = Query(
        None,
        min_length=2,
        max_length=50,
        description="Напрямок розвитку, напр. Data Science",
    ),
    trimester: Optional[int] = Query(None, ge=1, le=3, description="Триместр (1 — осінь, 2 — весна, 3 — літо)"),
    instructor: Optional[str] = Query(None, min_length=2, max_length=100, description="Частина імені викладача"),
    min_credits: Optional[float] = Query(None, ge=0, description="Мінімум кредитів"),
    max_credits: Optional[float] = Query(None, ge=0, description="Максимум кредитів"),
    recommended_year: Optional[int] = Query(None, ge=1, le=4, description="Рекомендований рік навчання"),
    discipline_type: Optional[DisciplineType] = Query(None, description="Тип дисципліни"),
):
    if min_credits is not None and max_credits is not None and min_credits > max_credits:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Невалідні параметри запиту",
            [
                ErrorDetail(
                    field="min_credits",
                    message="min_credits не може бути більшим за max_credits",
                )
            ],
        )

    result = list(_CATALOG)
    if direction:
        result = [d for d in result if direction.lower() in [x.lower() for x in d.directions]]
    if trimester:
        result = [d for d in result if d.trimester == trimester]
    if instructor:
        result = [d for d in result if instructor.lower() in d.instructor.lower()]
    if min_credits is not None:
        result = [d for d in result if d.credits >= min_credits]
    if max_credits is not None:
        result = [d for d in result if d.credits <= max_credits]
    if recommended_year:
        result = [d for d in result if d.recommended_year == recommended_year]
    if discipline_type:
        result = [d for d in result if d.discipline_type == discipline_type]

    return PaginatedDisciplinesResponse(
        disciplines=result[offset : offset + limit],
        pagination=PaginationInfo(
            limit=limit,
            offset=offset,
            total=len(result),
            has_more=(offset + limit) < len(result),
        ),
    )


@router.get(
    "/disciplines/{discipline_id}",
    response_model=Discipline,
    summary="Отримати дисципліну за ID",
    description="Детальна інформація про дисципліну з каталогу.",
    responses={
        200: {"description": "Дисципліну знайдено"},
        **error_responses(
            401,
            404,
            422,
            overrides={404: ("DISCIPLINE_NOT_FOUND", "Дисципліну з ID 999 не знайдено")},
        ),
    },
)
async def get_discipline(
    discipline_id: int = Path(..., gt=0, description="Унікальний ідентифікатор дисципліни", examples=[101]),
):
    for discipline in _CATALOG:
        if discipline.id == discipline_id:
            return discipline
    raise ApiError(404, "DISCIPLINE_NOT_FOUND", f"Дисципліну з ID {discipline_id} не знайдено")
