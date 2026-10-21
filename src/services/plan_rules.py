"""
Чисті бізнес-правила індивідуального плану (AGENTS.md §4 і §10) без залежності від FastAPI та БД.

Функції приймають прості значення й повертають список порушень, тому тестуються без сервера.
Перетворення порушень на відповідь 422 робить шар API (src/api/plan_checks.py).

Використання ШІ: файл створено за допомогою Claude (Anthropic) за вимогами AGENTS.md і contract.md.
Додатково (Claude): правила дублікатів, «лише вільний вибір», ліміту в межах плану й конфлікту з нормативними
дисциплінами деканату перенесено сюди з плану API, щоб мати одне джерело правил.
Перевірка: unit-тести tests/test_plan_rules.py (потрібно оновити й запустити), Black, flake8, bandit, ручний огляд.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

FREE_ELECTIVE_LIMIT = 25.0
ANNUAL_MIN_CREDITS = 57.0
COURSE_WITHOUT_LOAD_CHOICE = 4


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    field: Optional[str] = None


@dataclass(frozen=True)
class CatalogFlag:
    """Що клієнт заявив про елемент плану і що каталог каже про дисципліну."""

    index: int
    has_directions: bool
    is_free_elective: bool


def check_duplicate_courses(course_ids: Sequence[int]) -> List[Violation]:
    """Одна дисципліна не може бути в плані двічі (UNIQUE plan_id, course_id)."""
    if len(course_ids) == len(set(course_ids)):
        return []
    return [
        Violation(
            code="DUPLICATE_COURSE",
            message="Дисципліни в плані не повинні повторюватись (course_id має бути унікальним)",
        )
    ]


def check_not_only_free_electives(free_flags: Sequence[bool]) -> List[Violation]:
    """Лише вільний вибір без профорієнтовних заборонено (AGENTS.md §4)."""
    if free_flags and all(free_flags):
        return [
            Violation(
                code="ONLY_FREE_ELECTIVES",
                message="Не можна обрати лише дисципліни вільного вибору без профорієнтовних",
            )
        ]
    return []


def check_free_elective_in_plan(current_credits: float) -> List[Violation]:
    """Ліміт 25 кредитів вільного вибору в межах самого плану."""
    total = round(current_credits, 1)
    if total <= FREE_ELECTIVE_LIMIT:
        return []
    return [
        Violation(
            code="FREE_ELECTIVE_LIMIT_EXCEEDED",
            message=f"Перевищено ліміт вільного вибору: {total:g} > {FREE_ELECTIVE_LIMIT:g} кредитів",
        )
    ]


def check_free_elective_flags(flags: Iterable[CatalogFlag]) -> List[Violation]:
    """
    Прапорець is_free_elective надходить від клієнта, тому йому не можна довіряти.
    Дисципліна без жодного напрямку в каталозі завжди є вільним вибором (use-case 9, §2.2 документації).
    Без цієї перевірки студент позначає все як профорієнтовне й обходить ліміт у 25 кредитів.
    """
    violations: List[Violation] = []
    for flag in flags:
        if not flag.has_directions and not flag.is_free_elective:
            violations.append(
                Violation(
                    code="FREE_ELECTIVE_FLAG_MISMATCH",
                    message=(
                        "Дисципліна не профорієнтовна для жодного напрямку: "
                        "це вільний вибір (is_free_elective=true)"
                    ),
                    field=f"items.{flag.index}.is_free_elective",
                )
            )
    return violations


def check_free_elective_total(current_credits: float, used_in_other_years: float) -> List[Violation]:
    """
    Ліміт 25 кредитів вільного вибору діє сумарно за всі 4 роки.
    Перевірку в межах одного плану робить check_free_elective_in_plan, тому тут лише випадок,
    коли в інші роки вже є вибір.
    """
    if used_in_other_years <= 0:
        return []
    total = round(current_credits + used_in_other_years, 1)
    if total <= FREE_ELECTIVE_LIMIT:
        return []
    remaining = max(0.0, round(FREE_ELECTIVE_LIMIT - used_in_other_years, 1))
    return [
        Violation(
            code="FREE_ELECTIVE_TOTAL_EXCEEDED",
            message=(
                f"Перевищено ліміт вільного вибору за всі роки: {total} > {FREE_ELECTIVE_LIMIT:g} кредитів "
                f"(в інші роки вже використано {used_in_other_years:g}, у цьому плані можна обрати не більше "
                f"{remaining:g})"
            ),
            field="items",
        )
    ]


def check_deanery_conflicts(courses: Iterable[Tuple[int, int]], normative_ids: Set[int]) -> List[Violation]:
    """
    courses: пари (індекс елемента, course_id). Не можна обрати вибірково дисципліну,
    на яку студента вже записав деканат (AGENTS.md §4, «Документ деканату»).
    """
    return [
        Violation(
            code="NORMATIVE_CONFLICT",
            message=f"Дисципліна {course_id} уже є в нормативному плані деканату на цей рік",
            field=f"items.{index}.course_id",
        )
        for index, course_id in courses
        if course_id in normative_ids
    ]


def check_load_levels(course_year: int, load_levels_sent: bool) -> List[Violation]:
    """4 курс: вибір навантаження вимкнено, воно рахується автоматично (AGENTS.md §4)."""
    if course_year == COURSE_WITHOUT_LOAD_CHOICE and load_levels_sent:
        return [
            Violation(
                code="LOAD_LEVELS_NOT_ALLOWED",
                message="На 4 курсі навантаження розраховується автоматично, load_levels передавати не можна",
                field="load_levels",
            )
        ]
    return []

def free_elective_remaining(used: float) -> float:
    """
        Функція що дозволяє порахувати к-ть кредитів вільного вибору, що може обрати студент
        на основі того, скільки у нього вже обрано кредитів вільного вибору.
    """
    if used < 0:
        raise ValueError
    return round(max(0, FREE_ELECTIVE_LIMIT - used), 1)

def check_annual_minimum(year_credits: float) -> List[Violation]:
    """Мінімум 57 кредитів за навчальний рік, навіть за низького навантаження (AGENTS.md §4)."""
    if year_credits < 0:
        raise ValueError("Кількість кредитів не може бути від'ємною")
    if year_credits >= ANNUAL_MIN_CREDITS:
        return []
    missing = round(ANNUAL_MIN_CREDITS - year_credits, 1)
    return [
        Violation(
            code="ANNUAL_MINIMUM_NOT_MET",
            message=f"Замало кредитів за рік: {year_credits:g} < {ANNUAL_MIN_CREDITS:g}, бракує {missing:g}"
        )
    ]
