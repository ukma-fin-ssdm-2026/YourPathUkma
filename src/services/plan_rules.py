"""
Чисті бізнес-правила індивідуального плану (AGENTS.md §4 і §10) без залежності від FastAPI та БД.

Функції приймають прості значення й повертають список порушень, тому тестуються без сервера.
Перетворення порушень на відповідь 422 робить шар API (src/api/plan_checks.py).

Використання ШІ: файл створено за допомогою Claude (Anthropic) за вимогами AGENTS.md і contract.md.
Перевірка: unit-тести tests/test_plan_rules.py, Black, flake8, bandit, ручний огляд командою.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional

FREE_ELECTIVE_LIMIT = 25.0
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
                    message="Дисципліна не профорієнтовна для жодного напрямку: це вільний вибір (is_free_elective=true)",
                    field=f"items.{flag.index}.is_free_elective",
                )
            )
    return violations


def check_free_elective_total(current_credits: float, used_in_other_years: float) -> List[Violation]:
    """
    Ліміт 25 кредитів вільного вибору діє сумарно за всі 4 роки.
    Перевірку в межах одного плану робить collect_rule_errors, тому тут лише випадок, коли в інші роки вже є вибір.
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