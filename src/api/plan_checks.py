"""
Перевірки плану, яким потрібні каталог і історія студента в БД. Точки входу: enforce_plan_rules (POST/PUT)
і enforce_submit_rules (подання плану).

Правила лежать у src/services/plan_rules.py, тут лише запити до БД і перетворення на ApiError (422).

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: tests/test_plan_rules.py
(збір порушень без БД), ручний запуск POST/PUT /plans у Swagger UI, Black, flake8, bandit.
Додатково (Claude): збір усіх правил в одному місці (дублікати, лише вільний вибір, ліміт 25, конфлікт з
документом деканату), enforce_submit_rules для подання плану. Перевірка: ручний огляд; pytest і лінтери
запустити перед комітом.
"""

from typing import Dict, List, Optional, Sequence, Set

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.models import Course, IndividualPlan
from ..db.models import PlanItem as PlanItemRow
from ..db.models.deanery import DeaneryPlanDocument, NormativeCourseEntry
from ..services import plan_rules
from .common import ApiError, ErrorDetail

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


def normative_course_ids(db: Session, student_id: int, academic_year: int) -> Set[int]:
    """Дисципліни каталогу, на які студента записав деканат у документі за цей рік."""
    rows = db.scalars(
        select(NormativeCourseEntry.course_id)
        .join(DeaneryPlanDocument, DeaneryPlanDocument.id == NormativeCourseEntry.document_id)
        .where(
            DeaneryPlanDocument.student_id == student_id,
            DeaneryPlanDocument.academic_year == academic_year,
            NormativeCourseEntry.course_id.is_not(None),
        )
    )
    return set(rows)


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


def _collect_violations(
    db: Session,
    student_id: int,
    academic_year: int,
    items: Sequence,
    courses: Dict[int, Course],
    exclude_plan_id: Optional[int] = None,
) -> List[plan_rules.Violation]:
    violations = plan_rules.check_duplicate_courses([item.course_id for item in items])
    violations += plan_rules.check_not_only_free_electives([item.is_free_elective for item in items])
    violations += collect_catalog_flag_violations(items, courses)

    current_free = round(
        sum(getattr(item, "credits", 0.0) or 0.0 for item in items if getattr(item, "is_free_elective", False)), 1
    )
    violations += plan_rules.check_free_elective_in_plan(current_free)
    used = free_elective_used_in_other_years(db, student_id, academic_year, exclude_plan_id)
    violations += plan_rules.check_free_elective_total(current_free, used)

    normative = normative_course_ids(db, student_id, academic_year)
    violations += plan_rules.check_deanery_conflicts(
        [(index, item.course_id) for index, item in enumerate(items)], normative
    )
    return violations


def _to_details(violations: List[plan_rules.Violation]) -> List[ErrorDetail]:
    return [ErrorDetail(field=v.field or "items", message=f"{v.code}: {v.message}") for v in violations]


def enforce_plan_rules(
    db: Session,
    student_id: int,
    payload,
    courses: Dict[int, Course],
    exclude_plan_id: Optional[int] = None,
) -> None:
    """Викликати після _check_catalog. Збирає всі порушення й кидає один 422 VALIDATION_ERROR."""
    violations = _collect_violations(db, student_id, payload.academic_year, payload.items, courses, exclude_plan_id)
    violations += plan_rules.check_load_levels(payload.course, "load_levels" in payload.model_fields_set)

    if violations:
        raise ApiError(422, "VALIDATION_ERROR", "План порушує бізнес-правила", _to_details(violations))


def enforce_submit_rules(db: Session, plan: IndividualPlan, items: Sequence, courses: Dict[int, Course]) -> None:
    """Перевірки перед поданням плану. Порушення → 422 PLAN_VALIDATION_FAILED."""
    violations: List[plan_rules.Violation] = []
    if not items:
        violations.append(
            plan_rules.Violation(code="EMPTY_PLAN", message="План не містить жодної дисципліни", field="items")
        )
    else:
        violations += _collect_violations(db, plan.student_id, plan.academic_year, items, courses, plan.id)
    if violations:
        raise ApiError(
            422,
            "PLAN_VALIDATION_FAILED",
            "План не проходить перевірку нормативів при поданні",
            _to_details(violations),
        )
