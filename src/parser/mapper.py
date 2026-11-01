"""
ParsedCourse -> payload елемента модерації (формат `CoursePayload` у src/api/routes/admin/sync.py).

Правила:
- `trimester` береться з першого семестру курсу (Осінь=1, Весна=2, Літо=3); решта семестрів лишається в `semesters`;
- `credits` — кредити першого семестру, тобто те, що студент отримує в обраному триместрі;
- `kind` = normative, лише якщо курс обов'язковий для всіх своїх спеціальностей (такі курси задає деканат,
  у план студента вони не додаються); решта — elective;
- зайві ключі (`semesters`, `happened`, `specialties`, ...) схема payload ігнорує, але їх бачить модератор.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_mapper.py.
"""

from typing import Any, Dict

from ..db import enums as db_enums
from .models import ParsedCourse

TITLE_MAX = 300
DESCRIPTION_MAX = 20000

_TRIMESTER_BY_SEASON = {"Осінь": 1, "Весна": 2, "Літо": 3}
_MANDATORY_PREFIX = "Обов"  # «Обов`язкова»: апостроф у САЗ буває різний


class MappingError(ValueError):
    """Курс не можна перетворити на payload (бракує обов'язкового поля). Курс пропускається й рахується."""


def _kind(course: ParsedCourse) -> db_enums.CourseKind:
    if course.specialties and all(s.type.startswith(_MANDATORY_PREFIX) for s in course.specialties):
        return db_enums.CourseKind.NORMATIVE
    return db_enums.CourseKind.ELECTIVE


def course_to_payload(course: ParsedCourse) -> Dict[str, Any]:
    if not course.semesters:
        raise MappingError(f"Курс {course.saz_code}: немає семестрів")
    season = course.semesters[0].season
    if season not in _TRIMESTER_BY_SEASON:
        raise MappingError(f"Курс {course.saz_code}: невідома пора року {season!r}")
    if course.credits is None or course.credits <= 0:
        raise MappingError(f"Курс {course.saz_code}: немає кредитів")
    if course.recommended_year is None or not 1 <= course.recommended_year <= 4:
        raise MappingError(f"Курс {course.saz_code}: рік навчання поза межами 1–4 ({course.recommended_year})")

    return {
        "saz_code": course.saz_code,
        "title": course.title[:TITLE_MAX],
        "description": (course.description or "")[:DESCRIPTION_MAX],
        "credits": course.credits,
        "trimester": _TRIMESTER_BY_SEASON[season],
        "recommended_year": course.recommended_year,
        "kind": _kind(course).value,
        # лише для модератора
        "happened": course.happened,
        "semesters": [{"number": s.number, "season": s.season, "credits": s.credits} for s in course.semesters],
        "specialties": [{"name": s.name, "type": s.type} for s in course.specialties],
        "instructors": list(course.instructors),
        "faculty": course.faculty,
        "department": course.department,
        "level": course.level,
        "academic_year": course.academic_year,
        "saz_internal_id": course.saz_internal_id,
    }
