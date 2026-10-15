"""
Перевірки плану, яким потрібні каталог і історія студента в БД. Єдина точка входу: enforce_plan_rules.

Правила лежать у src/services/plan_rules.py, тут лише запити до БД і перетворення на ApiError (422).

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: tests/test_plan_rules.py
(збір порушень без БД), ручний запуск POST/PUT /plans у Swagger UI, Black, flake8, bandit.
Припущення: у PlanItem є колонка plan_id (за коментарем у plans.py про UNIQUE (plan_id, course_id)).
"""

from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.models import Course, IndividualPlan, PlanItem as PlanItemRow
from ..services import plan_rules
from .common import ApiError, ErrorDetail

# Чернетки не рахуються: це ще не зобов'язання студента
_COUNTED_STATUSES = (
    db_enums.PlanStatus.SUBMITTED,
    db_enums.PlanStatus.AWAITING_DEANERY,
    db_enums.PlanStatus.APPROVED,
)


def free_elective_used_in_other_years(
    db: Session, student_id: int, academic_year: int, exclude_plan_id: Optional[int] = None
) -> float:
    """Кредити вільного вибору в планах студента за інші навчальні роки (без чернеток)."""
    query = (
        select(func.coalesce(func.sum(Course.credits), 0.0))
        .select_from(PlanItemRow)
        .join(IndividualPlan, IndividualPlan.id == PlanItemRow.plan_id)
        .join(Course, Course.id == PlanItemRow.course_id)
        .where(
            IndividualPlan.student_id == student_id,
            IndividualPlan.academic_year != academic_year,
            IndividualPlan.status.in_(_COUNTED_STATUSES),
            PlanItemRow.category == db_enums.PlanItemCategory.FREE_CHOICE,
        )
    )
    if exclude_plan_id is not None:
        query = query.where(IndividualPlan.id != exclude_plan_id)
    return float(db.scalar(query) or 0.0)


def collect_catalog_flag_violations(items: Sequence, courses: Dict[int, Course]) -> List[plan_rules.Violation]:
    """items: елементи плану з course_id та is_free_elective; courses: дисципліни, які вже знайдено в каталозі."""
    flags = [
        plan_rules.CatalogFlag(
            index=index,
            has_directions=bool(courses[item.course_id].directions),
            is_free_elective=item.is_free_elective,
        )
        for index, item in enumerate(items)
    ]
    return plan_rules.check_free_elective_flags(flags)


def enforce_plan_rules(
    db: Session,
    student_id: int,
    payload,
    courses: Dict[int, Course],
    exclude_plan_id: Optional[int] = None,
) -> None:
    """Викликати після _check_catalog. Збирає всі порушення й кидає один 422 VALIDATION_ERROR."""
    violations = collect_catalog_flag_violations(payload.items, courses)

    current_free = sum(item.credits for item in payload.items if item.is_free_elective)
    used = free_elective_used_in_other_years(db, student_id, payload.academic_year, exclude_plan_id)
    violations += plan_rules.check_free_elective_total(current_free, used)

    violations += plan_rules.check_load_levels(payload.course, "load_levels" in payload.model_fields_set)

    if violations:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "План порушує бізнес-правила",
            [ErrorDetail(field=v.field or "items", message=f"{v.code}: {v.message}") for v in violations],
        )