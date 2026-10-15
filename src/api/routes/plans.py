"""
Ресурс «Індивідуальні плани» (Plans): CRUD, перевірка, подання, експорт.

Використання ШІ: файл доопрацьовано за допомогою Claude (Anthropic): єдиний формат помилок,
enum-и, бізнес-валідація з AGENTS.md (вільний вибір ≤ 25 кредитів, заборона «лише вільний вибір»,
унікальність дисциплін), статус 409 для не-чернеток, схема безпеки Bearer.
Перевірка: ручний запуск, перевірка кожної кінцевої точки у Swagger UI, звірка з docs/api/api-design.md.

Додатково (Claude, Anthropic): виклик enforce_plan_rules у create_plan і update_plan (серверна перевірка
прапорця вільного вибору проти каталогу, ліміт 25 кредитів за всі роки, заборона load_levels на 4 курсі);
видалено невикористані заглушки. Перевірка: tests/test_plan_rules.py, Black, flake8, bandit.

Додатково (Claude, Anthropic): розв'язано конфлікт злиття (submit і export збережено, заглушки видалено);
бізнес-правила винесено в plan_rules і збираються разом у enforce_plan_rules (усі порушення в одній 422,
а не лише перше з model_validator); submit перевіряє план через enforce_submit_rules (каталог, деканат, ліміти);
title елемента до 300 символів (як у БД); кредити округлюються до 0.1. Перевірка: ручний огляд, pytest і
лінтери запустити перед комітом.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db import enums as db_enums
from ...db.models import Course, IndividualPlan
from ...db.models import PlanItem as PlanItemRow
from ...db.session import get_db
from ...services import plan_rules
from ..common import ApiError, ErrorDetail, PaginationInfo, error_responses, get_current_student_id
from ..plan_checks import enforce_plan_rules, enforce_submit_rules

router = APIRouter(prefix="/api/v1", tags=["Plans"])

_PLAN_NOT_FOUND = ("PLAN_NOT_FOUND", "План з ID 5 не знайдено")
_PLAN_NOT_EDITABLE = ("PLAN_NOT_EDITABLE", "Редагувати можна лише план у статусі draft")
_PLAN_NOT_DELETABLE = ("PLAN_NOT_DELETABLE", "Видаляти можна лише план у статусі draft")

FREE_ELECTIVE_LIMIT = plan_rules.FREE_ELECTIVE_LIMIT


class PlanStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    AWAITING_DEANERY = "awaiting_deanery"
    APPROVED = "approved"


class LoadLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LoadLevels(BaseModel):
    autumn: LoadLevel = Field(LoadLevel.MEDIUM, description="Навантаження на осінній триместр")
    spring: LoadLevel = Field(LoadLevel.MEDIUM, description="Навантаження на весняний триместр")
    summer: LoadLevel = Field(LoadLevel.MEDIUM, description="Навантаження на літній триместр")


class PlanItem(BaseModel):
    course_id: int = Field(..., gt=0, description="Унікальний ID дисципліни з каталогу САЗ", examples=[101])
    title: str = Field(
        ...,
        min_length=2,
        max_length=300,
        description="Назва дисципліни",
        examples=["Функціональне програмування"],
    )
    trimester: int = Field(
        ...,
        ge=1,
        le=3,
        description="Номер триместру (1 — осінь, 2 — весна, 3 — літо)",
        examples=[1],
    )
    credits: float = Field(..., gt=0, le=30, description="Кількість кредитів ECTS", examples=[5.0])
    is_free_elective: bool = Field(False, description="Чи є дисципліна вільним вибором (ліміт 25 кредитів)")


class RuleIssue(BaseModel):
    code: str = Field(
        ...,
        description="Машинозчитуваний код",
        examples=["FREE_ELECTIVE_LIMIT_EXCEEDED"],
    )
    message: str = Field(..., description="Повідомлення українською")
    field: Optional[str] = Field(None, description="Поле, до якого належить порушення, або null")


def collect_rule_errors(items: List[PlanItem]) -> List[RuleIssue]:
    """Бізнес-правила плану, яким не потрібні БД чи каталог (contract.md, §2.4). Правила лежать у plan_rules."""
    violations = plan_rules.check_duplicate_courses([item.course_id for item in items])
    violations += plan_rules.check_not_only_free_electives([item.is_free_elective for item in items])
    violations += plan_rules.check_free_elective_in_plan(sum(item.credits for item in items if item.is_free_elective))
    return [RuleIssue(code=v.code, message=v.message, field=v.field) for v in violations]


class PlanPayload(BaseModel):
    """Тіло плану без бізнес-перевірок: його приймає і POST /plans/validate, який має повертати 200."""

    academic_year: int = Field(..., ge=2024, le=2030, description="Навчальний рік", examples=[2026])
    course: int = Field(
        ...,
        ge=2,
        le=4,
        description="Курс навчання (на 1 курсі план формує деканат)",
        examples=[2],
    )
    load_levels: LoadLevels = Field(default_factory=LoadLevels, description="Навантаження по триместрах")
    items: List[PlanItem] = Field(..., min_length=1, max_length=30, description="Список вибіркових дисциплін")


class CreatePlanRequest(PlanPayload):
    """Тіло POST/PUT /plans. Бізнес-правила перевіряє enforce_plan_rules, щоб повернути всі порушення разом."""


class PlanResponse(BaseModel):
    id: int = Field(..., description="Унікальний ідентифікатор індивідуального плану", examples=[1])
    student_id: int = Field(..., description="ID студента-власника", examples=[42])
    academic_year: int = Field(..., description="Навчальний рік", examples=[2026])
    course: int = Field(..., description="Курс навчання", examples=[2])
    load_levels: LoadLevels = Field(..., description="Навантаження по триместрах")
    items: List[PlanItem] = Field(..., description="Вибіркові дисципліни плану")
    status: PlanStatus = Field(..., description="Статус плану")
    total_credits: float = Field(..., description="Сумарна кількість кредитів ECTS", examples=[8.0])
    free_elective_credits: float = Field(..., description="Кредити вільного вибору в плані", examples=[3.0])
    created_at: datetime = Field(..., description="Дата створення плану")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "student_id": 42,
                    "academic_year": 2026,
                    "course": 2,
                    "load_levels": {
                        "autumn": "medium",
                        "spring": "high",
                        "summer": "low",
                    },
                    "items": [
                        {
                            "course_id": 101,
                            "title": "Функціональне програмування",
                            "trimester": 1,
                            "credits": 5.0,
                            "is_free_elective": False,
                        }
                    ],
                    "status": "draft",
                    "total_credits": 5.0,
                    "free_elective_credits": 0.0,
                    "created_at": "2026-10-08T10:00:00Z",
                }
            ]
        }
    )


class PaginatedPlansResponse(BaseModel):
    plans: List[PlanResponse] = Field(..., description="Список індивідуальних планів")
    pagination: PaginationInfo = Field(..., description="Метадані пагінації")


class PlanSummary(BaseModel):
    total_credits: float = Field(..., description="Кредити вибіркових дисциплін плану", examples=[8.0])
    free_elective_credits: float = Field(..., description="Кредити вільного вибору в плані", examples=[3.0])
    free_elective_used_all_years: float = Field(
        ..., description="Вільний вибір, використаний за всі роки", examples=[3.0]
    )
    free_elective_remaining: float = Field(
        ...,
        description="Скільки кредитів вільного вибору ще можна обрати",
        examples=[22.0],
    )
    year_total_credits: float = Field(..., description="Сума кредитів за рік", examples=[8.0])
    credits_by_trimester: Dict[str, float] = Field(..., description="Кредити по триместрах (ключі 1, 2, 3)")


class PlanValidationResponse(BaseModel):
    valid: bool = Field(..., description="true, якщо немає жодної помилки")
    errors: List[RuleIssue] = Field(..., description="Порушення правил")
    warnings: List[RuleIssue] = Field(..., description="Попередження")
    summary: PlanSummary = Field(..., description="Підсумок кредитів для індикаторів у конструкторі")


def _plan_items(plan: IndividualPlan) -> List[PlanItem]:
    return [
        PlanItem(
            course_id=item.course_id,
            title=item.course.title,
            trimester=item.trimester.number,
            credits=item.course.credits,
            is_free_elective=item.category == db_enums.PlanItemCategory.FREE_CHOICE,
        )
        for item in plan.items
    ]


def _to_response(plan: IndividualPlan) -> PlanResponse:
    """Перетворює ORM-план на PlanResponse з підрахунком кредитів."""
    items = _plan_items(plan)
    return PlanResponse(
        id=plan.id,
        student_id=plan.student_id,
        academic_year=plan.academic_year,
        course=plan.course_year,
        load_levels=LoadLevels(
            autumn=plan.load_autumn.value,
            spring=plan.load_spring.value,
            summer=plan.load_summer.value,
        ),
        items=items,
        status=PlanStatus(plan.status.value),
        total_credits=round(sum(item.credits for item in items), 1),
        free_elective_credits=round(sum(item.credits for item in items if item.is_free_elective), 1),
        created_at=plan.created_at,
    )


def _find_plan(db: Session, plan_id: int, student_id: int) -> IndividualPlan:
    """Повертає план або кидає 404 (немає) / 403 (чужий план)."""
    plan = db.get(IndividualPlan, plan_id)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", f"План з ID {plan_id} не знайдено")
    if plan.student_id != student_id:
        raise ApiError(403, "PLAN_FORBIDDEN", "Цей план належить іншому студенту")
    return plan


def _check_catalog(db: Session, items: List[PlanItem]) -> Dict[int, Course]:
    """
    Звіряє елементи плану з каталогом (contract.md §2.4): дисципліна існує й опублікована, вона вибіркова,
    кредити й триместр збігаються. Порушення → 422 з деталями по кожному елементу.
    """
    ids = [item.course_id for item in items]
    courses = {
        course.id: course
        for course in db.scalars(
            select(Course).where(Course.id.in_(ids), Course.publication_status == db_enums.PublicationStatus.PUBLISHED)
        )
    }
    details: List[ErrorDetail] = []
    for index, item in enumerate(items):
        field = f"items.{index}.course_id"
        course = courses.get(item.course_id)
        if course is None:
            details.append(
                ErrorDetail(field=field, message=f"COURSE_NOT_FOUND: дисципліни {item.course_id} немає в каталозі")
            )
        elif course.kind == db_enums.CourseKind.NORMATIVE:
            details.append(
                ErrorDetail(field=field, message=f"NORMATIVE_NOT_ALLOWED: «{course.title}» — нормативна дисципліна")
            )
        elif course.credits != item.credits or course.trimester.number != item.trimester:
            details.append(
                ErrorDetail(
                    field=field,
                    message=(
                        f"COURSE_DATA_MISMATCH: у каталозі «{course.title}» має {course.credits} кредитів "
                        f"і триместр {course.trimester.number}"
                    ),
                )
            )
    if details:
        raise ApiError(422, "VALIDATION_ERROR", "План не відповідає каталогу дисциплін", details)
    return courses


def _apply_payload(plan: IndividualPlan, payload: CreatePlanRequest, courses: Dict[int, Course]) -> None:
    plan.academic_year = payload.academic_year
    plan.course_year = payload.course
    plan.load_autumn = db_enums.LoadLevel(payload.load_levels.autumn.value)
    plan.load_spring = db_enums.LoadLevel(payload.load_levels.spring.value)
    plan.load_summer = db_enums.LoadLevel(payload.load_levels.summer.value)
    plan.total_credits = round(sum(courses[item.course_id].credits for item in payload.items), 1)
    plan.items = [
        PlanItemRow(
            course_id=item.course_id,
            course=courses[item.course_id],
            trimester=db_enums.Trimester.from_number(item.trimester),
            category=(
                db_enums.PlanItemCategory.FREE_CHOICE
                if item.is_free_elective
                else db_enums.PlanItemCategory.PROFESSIONAL
            ),
        )
        for item in payload.items
    ]


@router.post(
    "/plans",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити новий індивідуальний план (чернетку)",
    description=(
        "Створює план вибіркових дисциплін для поточного студента. "
        "Серверна валідація: унікальність дисциплін, ліміт вільного вибору (25 кредитів), "
        "заборона плану лише з вільного вибору, конфлікт з нормативними дисциплінами деканату."
    ),
    responses={
        201: {"description": "План успішно створено"},
        **error_responses(401, 422),
    },
)
def create_plan(
    payload: CreatePlanRequest,
    response: Response,
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    courses = _check_catalog(db, payload.items)
    enforce_plan_rules(db, student_id, payload, courses)
    plan = IndividualPlan(student_id=student_id, status=db_enums.PlanStatus.DRAFT, origin=db_enums.PlanOrigin.MANUAL)
    _apply_payload(plan, payload, courses)
    db.add(plan)
    db.commit()
    response.headers["Location"] = f"/api/v1/plans/{plan.id}"
    return _to_response(plan)


@router.get(
    "/plans",
    response_model=PaginatedPlansResponse,
    summary="Отримати список планів студента",
    description="Повертає плани поточного студента з offset-пагінацією та фільтрами за статусом і навчальним роком.",
    responses={
        200: {"description": "Список планів отримано"},
        **error_responses(401, 422),
    },
)
def list_plans(
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100, description="Максимальна кількість планів на сторінку"),
    offset: int = Query(0, ge=0, description="Кількість планів, які треба пропустити"),
    plan_status: Optional[PlanStatus] = Query(None, alias="status", description="Фільтр за статусом плану"),
    academic_year: Optional[int] = Query(None, ge=2024, le=2030, description="Фільтр за навчальним роком"),
):
    query = select(IndividualPlan).where(IndividualPlan.student_id == student_id)
    if plan_status:
        query = query.where(IndividualPlan.status == db_enums.PlanStatus(plan_status.value))
    if academic_year:
        query = query.where(IndividualPlan.academic_year == academic_year)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    plans = db.scalars(
        query.order_by(IndividualPlan.created_at.desc(), IndividualPlan.id.desc()).offset(offset).limit(limit)
    ).all()

    return PaginatedPlansResponse(
        plans=[_to_response(plan) for plan in plans],
        pagination=PaginationInfo(
            limit=limit,
            offset=offset,
            total=total,
            has_more=(offset + limit) < total,
        ),
    )


@router.get(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    summary="Отримати план за ID",
    description="Детальна інформація про конкретний індивідуальний план поточного студента.",
    responses={
        200: {"description": "План знайдено"},
        **error_responses(401, 403, 404, 422, overrides={404: _PLAN_NOT_FOUND}),
    },
)
def get_plan(
    plan_id: int = Path(..., gt=0, description="Унікальний ідентифікатор плану", examples=[1]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    return _to_response(_find_plan(db, plan_id, student_id))


@router.put(
    "/plans/{plan_id}",
    response_model=PlanResponse,
    summary="Оновити індивідуальний план",
    description="Повне оновлення плану. Дозволено лише для планів у статусі `draft`, інакше — 409.",
    responses={
        200: {"description": "План успішно оновлено"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={404: _PLAN_NOT_FOUND, 409: _PLAN_NOT_EDITABLE},
        ),
    },
)
def update_plan(
    payload: CreatePlanRequest,
    plan_id: int = Path(..., gt=0, description="Унікальний ідентифікатор плану", examples=[1]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    plan = _find_plan(db, plan_id, student_id)
    if plan.status != db_enums.PlanStatus.DRAFT:
        raise ApiError(409, "PLAN_NOT_EDITABLE", "Редагувати можна лише план у статусі draft")
    courses = _check_catalog(db, payload.items)
    enforce_plan_rules(db, student_id, payload, courses, exclude_plan_id=plan.id)
    plan.items.clear()
    db.flush()
    _apply_payload(plan, payload, courses)
    db.commit()
    return _to_response(plan)


@router.delete(
    "/plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити індивідуальний план",
    description="Видаляє план, лише якщо він у статусі `draft`, інакше — 409.",
    responses={
        204: {"description": "План успішно видалено"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={404: _PLAN_NOT_FOUND, 409: _PLAN_NOT_DELETABLE},
        ),
    },
)
def delete_plan(
    plan_id: int = Path(..., gt=0, description="Унікальний ідентифікатор плану", examples=[1]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    plan = _find_plan(db, plan_id, student_id)
    if plan.status != db_enums.PlanStatus.DRAFT:
        raise ApiError(409, "PLAN_NOT_DELETABLE", "Видаляти можна лише план у статусі draft")
    db.delete(plan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/plans/validate",
    response_model=PlanValidationResponse,
    summary="Перевірити план без збереження",
    description=(
        "Для живих підказок у конструкторі. Завжди 200, якщо тіло відповідає схемі; "
        "порушення правил повертаються в `errors`. Поки без БД: не перевіряються каталог, "
        "нормативні дисципліни, документ деканату, вільний вибір попередніх років і попередження про навантаження."
    ),
    dependencies=[Depends(get_current_student_id)],
    responses={200: {"description": "Перевірку виконано"}, **error_responses(401, 422)},
)
async def validate_plan(payload: PlanPayload):
    errors = collect_rule_errors(payload.items)
    total = round(sum(item.credits for item in payload.items), 1)
    free = round(sum(item.credits for item in payload.items if item.is_free_elective), 1)
    by_trimester = {"1": 0.0, "2": 0.0, "3": 0.0}
    for item in payload.items:
        by_trimester[str(item.trimester)] += item.credits
    by_trimester = {key: round(value, 1) for key, value in by_trimester.items()}

    return PlanValidationResponse(
        valid=not errors,
        errors=errors,
        warnings=[],  # TODO: LOW_LOAD_FUTURE_INCREASE і YEAR_CREDITS_BELOW_MIN потребують нормативних дисциплін року
        summary=PlanSummary(
            total_credits=total,
            free_elective_credits=free,
            free_elective_used_all_years=free,  # TODO: додати вільний вибір попередніх років з історії студента
            free_elective_remaining=max(0.0, round(FREE_ELECTIVE_LIMIT - free, 1)),
            year_total_credits=total,  # TODO: додати нормативні дисципліни року
            credits_by_trimester=by_trimester,
        ),
    )


@router.post(
    "/plans/{plan_id}/submit",
    response_model=PlanResponse,
    summary="Подати індивідуальний план",
    description="Переводить план зі статусу draft у submitted. Перевіряє всі нормативи.",
    responses={
        200: {"description": "План успішно подано"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={
                404: _PLAN_NOT_FOUND,
                409: ("PLAN_NOT_SUBMITTABLE", "Подати можна лише план у статусі draft"),
                422: ("PLAN_VALIDATION_FAILED", "План не проходить перевірку нормативів"),
            },
        ),
    },
)
def submit_plan(
    plan_id: int = Path(..., gt=0, examples=[1]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    plan = _find_plan(db, plan_id, student_id)
    if plan.status != db_enums.PlanStatus.DRAFT:
        raise ApiError(409, "PLAN_NOT_SUBMITTABLE", "Подати можна лише план у статусі draft")

    courses = {row.course_id: row.course for row in plan.items}
    enforce_submit_rules(db, plan, _plan_items(plan), courses)

    plan.status = db_enums.PlanStatus.SUBMITTED
    db.commit()
    return _to_response(plan)


@router.get(
    "/plans/{plan_id}/export",
    summary="Експорт плану в PDF",
    description="Фіксація і експорт плану у форматі PDF (use-case 16).",
    responses={
        200: {"description": "Файл PDF", "content": {"application/pdf": {}}},
        **error_responses(401, 403, 404, 422, overrides={404: _PLAN_NOT_FOUND}),
    },
)
def export_plan(
    plan_id: int = Path(..., gt=0, examples=[1]),
    export_format: str = Query("pdf", alias="format", description="Формат експорту (поки лише pdf)"),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    plan = _find_plan(db, plan_id, student_id)

    if export_format.lower() != "pdf":
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Невалідні вхідні дані",
            [ErrorDetail(field="format", message="Підтримується лише формат pdf")],
        )

    # TODO (команда): реалізувати генерацію реального PDF з даними плану. Поки повертається заглушка.
    pdf_content = b"%PDF-1.4\n%Fake PDF content for endpoint testing\n%%EOF"

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="plan-{plan.academic_year}.pdf"'},
    )