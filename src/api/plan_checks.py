# Використання ШІ: Codex доповнив облік годин і кредитів #291; перевірка: pytest і лінтери.
"""
Перевірки плану, яким потрібні каталог і історія студента в БД. Точки входу: enforce_plan_rules (POST/PUT)
і enforce_submit_rules (подання плану).

Правила лежать у src/services/plan_rules.py, тут лише запити до БД і перетворення на ApiError (422).

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: tests/test_plan_rules.py
(збір порушень без БД), ручний запуск POST/PUT /plans у Swagger UI, Black, flake8, bandit.
Додатково (Claude): збір усіх правил в одному місці (дублікати, лише вільний вибір, ліміт 25, конфлікт з
документом деканату), enforce_submit_rules для подання плану. Перевірка: ручний огляд; pytest і лінтери
запустити перед комітом.
Додатково (Antigravity, Gemini 2.5 Pro): спільний облік кредитів студента (get_student_credit_summary),
виключення дублювання між історією та планами, перевірка ліміту 240 кредитів, блокування
(lock_student_for_credits) для issue #288. Перевірка: tests/test_credit_accounting_reconciliation.py, pytest.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.models import Course, IndividualPlan
from ..db.models.history import AcademicRecord
from ..db.models.users import StudentProfile
from ..services import plan_rules
from .common import ApiError, ErrorDetail

_COUNTED_STATUSES = (
    db_enums.PlanStatus.SUBMITTED,
    db_enums.PlanStatus.AWAITING_DEANERY,
    db_enums.PlanStatus.APPROVED,
)


@dataclass(frozen=True)
class StudentCreditSummary:
    """Спільний стан кредитів студента за програмою (AGENTS.md §4, §10, issue #288)."""

    history_total: float
    history_free: float
    history_professional: float
    committed_plans_total: float
    committed_plans_free: float
    committed_plans_professional: float
    total_used: float
    free_choice_used: float
    professional_used: float
    recorded_course_ids: Set[int]
    seen_committed_course_ids: Set[int]


def get_student_credit_summary(
    db: Session,
    student_id: int,
    exclude_plan_id: Optional[int] = None,
    exclude_academic_year: Optional[int] = None,
) -> StudentCreditSummary:
    """
    Спільний облік кредитів студента:
    1. Завершені дисципліни з AcademicRecord.
    2. Актуальні зобов'язання за активними планами (SUBMITTED, AWAITING_DEANERY, APPROVED), крім exclude_plan_id.
       Чернетки (DRAFT) не резервують кредити одночасно.
    3. Виключення подвійного обліку: якщо план або дисципліна вже є в AcademicRecord, вона не рахується з плану.
    """
    records = db.scalars(select(AcademicRecord).where(AcademicRecord.student_id == student_id)).all()

    history_total = 0.0
    history_free = 0.0
    history_prof = 0.0
    recorded_course_ids: Set[int] = set()
    recorded_plan_ids: Set[int] = set()

    for r in records:
        history_total += r.credits
        if r.category == db_enums.AcademicCategory.FREE_CHOICE:
            history_free += r.credits
        elif r.category == db_enums.AcademicCategory.PROFESSIONAL:
            history_prof += r.credits
        if r.course_id is not None:
            recorded_course_ids.add(r.course_id)
        if r.plan_id is not None:
            recorded_plan_ids.add(r.plan_id)

    query = select(IndividualPlan).where(
        IndividualPlan.student_id == student_id,
        IndividualPlan.status.in_(_COUNTED_STATUSES),
    )
    if exclude_plan_id is not None:
        query = query.where(IndividualPlan.id != exclude_plan_id)
    if exclude_academic_year is not None:
        query = query.where(IndividualPlan.academic_year != exclude_academic_year)

    committed_plans = db.scalars(query).all()

    committed_total = 0.0
    committed_free = 0.0
    committed_prof = 0.0

    for plan in committed_plans:
        if plan.id in recorded_plan_ids:
            continue
        for item in plan.items:
            if item.course_id in recorded_course_ids:
                continue
            credits = float(item.course.credits if item.course else item.credits)
            committed_total += credits
            if item.category == db_enums.PlanItemCategory.FREE_CHOICE:
                committed_free += credits
            elif item.category == db_enums.PlanItemCategory.PROFESSIONAL:
                committed_prof += credits

    total_used = round(history_total + committed_total, 1)
    free_choice_used = round(history_free + committed_free, 1)
    professional_used = round(history_prof + committed_prof, 1)

    return StudentCreditSummary(
        history_total=round(history_total, 1),
        history_free=round(history_free, 1),
        history_professional=round(history_prof, 1),
        committed_plans_total=round(committed_total, 1),
        committed_plans_free=round(committed_free, 1),
        committed_plans_professional=round(committed_prof, 1),
        total_used=total_used,
        free_choice_used=free_choice_used,
        professional_used=professional_used,
        recorded_course_ids=recorded_course_ids,
        seen_committed_course_ids=set(),
    )


def lock_student_for_credits(db: Session, student_id: int) -> None:
    """
    Блокує рядок StudentProfile до завершення транзакції (FOR UPDATE) для забезпечення
    атомарності перевірки лімітів при паралельних мутаціях (створення/зміна/подання планів, історія).
    На SQLite блокування ігнорується.
    """
    db.execute(select(StudentProfile.user_id).where(StudentProfile.user_id == student_id).with_for_update())


def free_elective_used_in_other_plans(db: Session, student_id: int, exclude_plan_id: Optional[int] = None) -> float:
    """
    Кредити вільного вибору в усіх завершених і поданих планах студента (без чернеток), крім `exclude_plan_id`.
    Ліміт 25 кредитів діє за ВСІ роки разом.
    """
    return get_student_credit_summary(db, student_id, exclude_plan_id).free_choice_used


def normative_course_ids(db: Session, student_id: int, academic_year: int) -> Set[int]:
    """Дисципліни каталогу, на які студента записав деканат у документі за цей рік."""
    from ..services.plan_workload import latest_parsed_document

    doc = latest_parsed_document(db, student_id, academic_year)
    return {entry.course_id for entry in doc.normative_courses if entry.course_id is not None} if doc else set()


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

    # Кредити рахуються за каталогом дисциплін
    current_free = round(
        sum(courses[item.course_id].credits for item in items if getattr(item, "is_free_elective", False)), 1
    )
    current_total = round(sum(courses[item.course_id].credits for item in items), 1)

    violations += plan_rules.check_free_elective_in_plan(current_free)
    credit_summary = get_student_credit_summary(db, student_id, exclude_plan_id)
    violations += plan_rules.check_free_elective_total(current_free, credit_summary.free_choice_used)
    violations += plan_rules.check_total_program_credits(current_total, credit_summary.total_used)

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
    from ..services.plan_workload import evaluate_plan_workload

    evaluation = evaluate_plan_workload(db, plan.student_id, plan.academic_year, items)
    violations += evaluation.errors
    if violations:
        raise ApiError(
            422,
            "PLAN_VALIDATION_FAILED",
            "План не проходить перевірку нормативів при поданні",
            _to_details(violations),
        )
