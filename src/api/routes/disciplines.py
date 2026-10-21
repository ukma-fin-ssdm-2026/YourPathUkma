"""
Ресурс «Дисципліни» (Disciplines): read-only каталог вибіркових і нормативних дисциплін (use-case 9).
Дані в реальній системі надходять із САЗ парсингом; тут — заглушки.
"""

from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ...db.base import normalize_text
from ...db.enums import CourseKind, PublicationStatus, Trimester
from ...db.models import Course, CourseDirection, CourseInstructor, Direction, Instructor
from ...db.session import get_db
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


def to_discipline(course: Course) -> Discipline:
    lecturers = [ci.instructor.full_name for ci in course.course_instructors]
    return Discipline(
        id=course.id,
        title=course.title,
        description=course.description,
        discipline_type=DisciplineType(course.kind.value),
        instructor=", ".join(lecturers),
        recommended_year=course.recommended_year,
        trimester=course.trimester.number,
        credits=course.credits,
        directions=[direction.name for direction in course.directions],
    )


@router.get(
    "/disciplines",
    response_model=PaginatedDisciplinesResponse,
    summary="Отримати каталог дисциплін",
    description="Каталог дисциплін з фільтрами (напрямок, триместр, викладач, кредити, рік, тип) та offset-пагінацією.",
    responses={200: {"description": "Каталог отримано"}, **error_responses(401, 422)},
)
def list_disciplines(
    db: Session = Depends(get_db),
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

    query = select(Course).where(Course.publication_status == PublicationStatus.PUBLISHED)
    if direction:
        query = query.where(
            Course.id.in_(
                select(CourseDirection.course_id)
                .join(Direction, Direction.id == CourseDirection.direction_id)
                .where(Direction.name_normalized == normalize_text(direction))
            )
        )
    if trimester:
        query = query.where(Course.trimester == Trimester.from_number(trimester))
    if instructor:
        query = query.where(
            Course.id.in_(
                select(CourseInstructor.course_id)
                .join(Instructor, Instructor.id == CourseInstructor.instructor_id)
                .where(Instructor.full_name_normalized.contains(normalize_text(instructor), autoescape=True))
            )
        )
    if min_credits is not None:
        query = query.where(Course.credits >= min_credits)
    if max_credits is not None:
        query = query.where(Course.credits <= max_credits)
    if recommended_year:
        query = query.where(Course.recommended_year == recommended_year)
    if discipline_type:
        query = query.where(Course.kind == CourseKind(discipline_type.value))

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    courses = db.scalars(
        query.options(selectinload(Course.course_instructors), selectinload(Course.directions))
        .order_by(Course.id)
        .offset(offset)
        .limit(limit)
    ).all()

    return PaginatedDisciplinesResponse(
        disciplines=[to_discipline(course) for course in courses],
        pagination=PaginationInfo(
            limit=limit,
            offset=offset,
            total=total,
            has_more=(offset + limit) < total,
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
def get_discipline(
    discipline_id: int = Path(..., gt=0, description="Унікальний ідентифікатор дисципліни", examples=[101]),
    db: Session = Depends(get_db),
):
    query = (
        select(Course)
        .where(Course.id == discipline_id, Course.publication_status == PublicationStatus.PUBLISHED)
        .options(selectinload(Course.course_instructors), selectinload(Course.directions))
    )
    course = db.scalar(query)
    if course is not None:
        return to_discipline(course)
    raise ApiError(404, "DISCIPLINE_NOT_FOUND", f"Дисципліну з ID {discipline_id} не знайдено")
