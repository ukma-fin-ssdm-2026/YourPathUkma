"""
Класифікація тижневого навантаження студента та автоматичний розрахунок для 4 курсу (AGENTS.md §4, FR-003, US-009).

Використання ШІ: функцію classify_load_level написано за допомогою Claude (Anthropic).
Доповнено функціями розрахунку та розподілу навантаження для 4 курсу (calculate_auto_load_levels, distribute_auto_load)
за допомогою Antigravity (Gemini 2.5 Pro, Google DeepMind) для задачі #292.
Перевірка: pytest (tests/test_load_levels.py, tests/test_auto_load_4th_year.py), ruff.
Додатково (Antigravity): узгоджено з єдиним модулем обліку кредитів get_student_credit_summary для issue #288.
Перевірка: pytest.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

LOW_LOAD_UPPER_BOUND = 20.0  # менше 20 год/тиждень: низьке
HIGH_LOAD_LOWER_BOUND = 23.0  # від 23 до 25 год/тиждень: високе
MAX_HOURS_PER_WEEK = 25.0
TOTAL_PROGRAM_CREDITS = 240.0


class AutoLoadError(Exception):
    """Базовий виняток автоматичного розрахунку навантаження."""

    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class TotalCreditsExceededError(AutoLoadError):
    """Зараховані кредити перевищують норматив 240."""

    def __init__(self, earned: float) -> None:
        super().__init__(
            code="TOTAL_CREDITS_EXCEEDED",
            message=f"Кількість зарахованих кредитів ({earned:g}) перевищує загальний норматив 240 кредитів",
        )


class InsufficientCatalogCoursesError(AutoLoadError):
    """У каталозі недостатньо вибіркових курсів для покриття залишку."""

    def __init__(self, available: float, needed: float) -> None:
        super().__init__(
            code="INSUFFICIENT_CATALOG_COURSES",
            message=(
                f"У каталозі недостатньо вибіркових дисциплін ({available:g} кр.) "
                f"для покриття необхідного залишку {needed:g} кр."
            ),
        )


class NormativeCreditsExceedRemainingError(AutoLoadError):
    """Обсяг нормативних дисциплін поточного року перевищує залишок до 240."""

    def __init__(self, normative: float, remaining: float) -> None:
        super().__init__(
            code="NORMATIVE_CREDITS_EXCEED_REMAINING",
            message=(
                f"Обсяг нормативних дисциплін ({normative:g} кр.) "
                f"перевищує залишок до виконання нормативу 240 ({remaining:g} кр.)"
            ),
        )


class LoadDistributionFailedError(AutoLoadError):
    """Неможливо розподілити навантаження без перевищення лімітів."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            code="LOAD_DISTRIBUTION_FAILED",
            message=f"Неможливо виконати автоматичний розподіл навантаження: {reason}",
        )


@dataclass(frozen=True)
class AutoLoadResult:
    autumn_level: str  # "low", "medium", "high"
    spring_level: str
    summer_level: str
    explanation: str
    earned_credits: float
    remaining_credits: float
    normative_credits: float
    remaining_elective_credits: float
    trimester_credits: Dict[str, float]  # {"autumn": 20.0, ...}


def classify_load_level(hours_per_week: float) -> str:
    """Повертає "low", "medium" або "high"; ValueError, якщо години поза діапазоном 0–25."""
    if not 0 <= hours_per_week <= MAX_HOURS_PER_WEEK:
        raise ValueError(f"Очікується 0–{MAX_HOURS_PER_WEEK:g} год/тиждень, отримано {hours_per_week:g}")
    if hours_per_week < LOW_LOAD_UPPER_BOUND:
        return "low"
    if hours_per_week < HIGH_LOAD_LOWER_BOUND:
        return "medium"
    return "high"


def distribute_auto_load(
    earned_credits: float,
    normative_by_trimester: Dict[str, float] | None = None,
    catalog_available_by_trimester: Dict[str, float] | None = None,
    total_program_credits: float = TOTAL_PROGRAM_CREDITS,
    max_hours_per_week: float = MAX_HOURS_PER_WEEK,
) -> AutoLoadResult:
    """Розподіляє навантаження 4 курсу за залишком кредитів до 240 (чиста бізнес-логіка).

    Враховує:
    - зараховані кредити студента;
    - нормативні дисципліни поточного року за триместрами;
    - доступність вибіркових курсів у каталозі по триместрах;
    - обмеження тижневого навантаження (максимум 25 год/тиждень на триместр).
    """
    earned = round(float(earned_credits), 1)
    if earned > total_program_credits:
        raise TotalCreditsExceededError(earned)

    remaining_total = round(total_program_credits - earned, 1)

    # Випадок, коли 240 вже зараховано (залишок 0)
    if remaining_total <= 0.0:
        return AutoLoadResult(
            autumn_level="low",
            spring_level="low",
            summer_level="low",
            explanation="Норматив у 240 кредитів уже виконано (залишок 0 кредитів). Навантаження мінімальне (low).",
            earned_credits=earned,
            remaining_credits=0.0,
            normative_credits=0.0,
            remaining_elective_credits=0.0,
            trimester_credits={"autumn": 0.0, "spring": 0.0, "summer": 0.0},
        )

    # Нормативні дисципліни поточного року
    norm: Dict[str, float] = {"autumn": 0.0, "spring": 0.0, "summer": 0.0}
    if normative_by_trimester:
        for k in ("autumn", "spring", "summer"):
            norm[k] = round(float(normative_by_trimester.get(k, 0.0)), 1)

    total_normative = round(sum(norm.values()), 1)
    if total_normative > remaining_total:
        raise NormativeCreditsExceedRemainingError(total_normative, remaining_total)

    for k in ("autumn", "spring", "summer"):
        if norm[k] > max_hours_per_week:
            raise LoadDistributionFailedError(
                f"Нормативні дисципліни в триместрі '{k}' ({norm[k]:g} кр.) "
                f"перевищують максимальне тижневе навантаження {max_hours_per_week:g} годин"
            )

    remaining_elective = round(remaining_total - total_normative, 1)

    # Максимальне навантаження за 3 триместри (3 * 25 = 75)
    max_year_capacity = 3 * max_hours_per_week
    if remaining_total > max_year_capacity:
        raise LoadDistributionFailedError(
            f"Залишок у {remaining_total:g} кредитів перевищує максимально можливе річне "
            f"навантаження ({max_year_capacity:g} кредитів за 3 триместри)"
        )

    elective_capacity = {k: round(max_hours_per_week - norm[k], 1) for k in ("autumn", "spring", "summer")}
    if remaining_elective > sum(elective_capacity.values()):
        raise LoadDistributionFailedError(
            f"Неможливо розподілити {remaining_elective:g} кр. вибіркових дисциплін "
            "без перевищення ліміту 25 год/тиждень"
        )

    # Перевірка наявності дисциплін у каталозі
    if catalog_available_by_trimester is not None and remaining_elective > 0:
        catalog_avail = {
            k: round(float(catalog_available_by_trimester.get(k, 0.0)), 1) for k in ("autumn", "spring", "summer")
        }
        total_catalog = round(sum(catalog_avail.values()), 1)
        if total_catalog < remaining_elective:
            raise InsufficientCatalogCoursesError(total_catalog, remaining_elective)

        max_elective = {k: min(elective_capacity[k], catalog_avail[k]) for k in ("autumn", "spring", "summer")}
        if round(sum(max_elective.values()), 1) < remaining_elective:
            raise LoadDistributionFailedError(
                "Неможливо розподілити вибіркові дисципліни через обмеження доступності курсів у каталозі по триместрах"
            )
    else:
        max_elective = elective_capacity

    # Цільовий розподіл: прагнемо збалансувати навантаження по триместрах (target = remaining_total / 3)
    target_per_tri = remaining_total / 3.0
    allocated: Dict[str, float] = {}
    for k in ("autumn", "spring", "summer"):
        desired = max(0.0, target_per_tri - norm[k])
        allocated[k] = min(max_elective[k], round(desired, 1))

    cur_allocated = round(sum(allocated.values()), 1)
    diff = round(remaining_elective - cur_allocated, 1)

    # Коригування залишку
    if diff > 0:
        while diff > 0.05:
            available_keys = [k for k in ("autumn", "spring", "summer") if allocated[k] < max_elective[k] - 0.05]
            if not available_keys:
                raise LoadDistributionFailedError("Неможливо розподілити залишок кредитів без перевищення лімітів")
            best_k = min(available_keys, key=lambda k: (norm[k] + allocated[k], -max_elective[k]))
            step = min(diff, round(max_elective[best_k] - allocated[best_k], 1))
            if step <= 0:
                break
            allocated[best_k] = round(allocated[best_k] + step, 1)
            diff = round(diff - step, 1)
    elif diff < 0:
        while diff < -0.05:
            available_keys = [k for k in ("autumn", "spring", "summer") if allocated[k] > 0.05]
            if not available_keys:
                break
            best_k = max(available_keys, key=lambda k: norm[k] + allocated[k])
            step = min(abs(diff), allocated[best_k])
            if step <= 0:
                break
            allocated[best_k] = round(allocated[best_k] - step, 1)
            diff = round(diff + step, 1)

    # Підсумкові кредити по триместрах (нормативні + вибіркові)
    final_totals = {k: round(norm[k] + allocated[k], 1) for k in ("autumn", "spring", "summer")}
    final_diff = round(remaining_total - sum(final_totals.values()), 1)
    if abs(final_diff) > 0.05:
        for k in ("autumn", "spring", "summer"):
            if 0 <= final_totals[k] + final_diff <= max_hours_per_week:
                final_totals[k] = round(final_totals[k] + final_diff, 1)
                break

    autumn_lvl = classify_load_level(final_totals["autumn"])
    spring_lvl = classify_load_level(final_totals["spring"])
    summer_lvl = classify_load_level(final_totals["summer"])

    explanation = (
        f"Автоматичний розрахунок для 4 курсу: зараховано {earned:g} кр., "
        f"нормативних у поточному році {total_normative:g} кр., залишок вибіркових {remaining_elective:g} кр. "
        f"Розподіл по триместрах: Осінь — {final_totals['autumn']:g} кр. ({autumn_lvl}), "
        f"Весна — {final_totals['spring']:g} кр. ({spring_lvl}), "
        f"Літо — {final_totals['summer']:g} кр. ({summer_lvl})."
    )

    return AutoLoadResult(
        autumn_level=autumn_lvl,
        spring_level=spring_lvl,
        summer_level=summer_lvl,
        explanation=explanation,
        earned_credits=earned,
        remaining_credits=remaining_total,
        normative_credits=total_normative,
        remaining_elective_credits=remaining_elective,
        trimester_credits=final_totals,
    )


def calculate_auto_load_levels(
    db: Session,
    student_id: int,
    academic_year: int,
    total_program_credits: float = TOTAL_PROGRAM_CREDITS,
) -> AutoLoadResult:
    """Вираховує автоматичні рівні навантаження для студента 4 курсу за даними БД.

    Враховує:
    - зараховані кредити з AcademicRecord та затверджених планів попередніх років (без подвійного обліку);
    - нормативні дисципліни поточного року з розпізнаного документа деканату;
    - доступні вибіркові дисципліни з каталогу за триместрами.
    """
    from sqlalchemy import select

    # 1. Зараховані кредити без подвійного обліку (спільний облік історії та активних планів)
    from ..api.plan_checks import get_student_credit_summary
    from ..db import enums as db_enums
    from ..db.models.catalog import Course
    from ..db.models.deanery import DeaneryPlanDocument

    summary = get_student_credit_summary(db, student_id, exclude_academic_year=academic_year)
    earned_credits = summary.total_used
    recorded_course_ids = set(summary.recorded_course_ids) | set(summary.seen_committed_course_ids)

    # 2. Нормативні дисципліни поточного року з документа деканату
    doc = db.scalar(
        select(DeaneryPlanDocument)
        .where(
            DeaneryPlanDocument.student_id == student_id,
            DeaneryPlanDocument.academic_year == academic_year,
            DeaneryPlanDocument.parse_status == db_enums.DocumentParseStatus.PARSED,
        )
        .order_by(DeaneryPlanDocument.id.desc())
    )

    normative_by_trimester = {"autumn": 0.0, "spring": 0.0, "summer": 0.0}
    if doc and doc.normative_courses:
        for nc in doc.normative_courses:
            tri_key = nc.trimester.value
            normative_by_trimester[tri_key] = round(normative_by_trimester[tri_key] + nc.credits, 1)

    # 3. Доступні вибіркові дисципліни з каталогу по триместрах
    catalog_courses = db.scalars(
        select(Course).where(
            Course.kind == db_enums.CourseKind.ELECTIVE,
            Course.publication_status == db_enums.PublicationStatus.PUBLISHED,
        )
    ).all()

    catalog_available = {"autumn": 0.0, "spring": 0.0, "summer": 0.0}
    for c in catalog_courses:
        if c.id not in recorded_course_ids:
            tri_key = c.trimester.value
            catalog_available[tri_key] = round(catalog_available[tri_key] + c.credits, 1)

    return distribute_auto_load(
        earned_credits=earned_credits,
        normative_by_trimester=normative_by_trimester,
        catalog_available_by_trimester=catalog_available,
        total_program_credits=total_program_credits,
    )
