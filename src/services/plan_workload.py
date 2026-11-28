"""One authoritative annual-credit and contact-hour evaluation for API and AI.

Використання ШІ: Codex реалізував #291; перевірка: pytest, PostgreSQL.
ECTS never becomes contact hours. Legacy unknown values stay unknown.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from ..db import enums
from ..db.models.catalog import Course
from ..db.models.deanery import DeaneryPlanDocument
from ..db.models.history import AcademicRecord
from .load_levels import classify_load_level
from .plan_rules import Violation, check_annual_minimum

SEASONS = {"Осінь": 1, "Весна": 2, "Літо": 3}


def weekly_hours(course, trimester):
    """Ambiguous/missing semester data is unknown; zero is a known value."""
    if course is None:
        return None
    matches = [s for s in course.semesters or [] if SEASONS.get(s.get("season")) == trimester]
    if len(matches) != 1:
        return None
    return matches[0].get("weekly_hours")


@dataclass
class WorkloadEvaluation:
    year_total_credits: float
    credits_by_trimester: dict
    workload_by_trimester: dict
    errors: list
    warnings: list
    complete: bool


def latest_parsed_document(db, student_id, academic_year):
    return db.scalar(
        select(DeaneryPlanDocument)
        .where(
            DeaneryPlanDocument.student_id == student_id,
            DeaneryPlanDocument.academic_year == academic_year,
            DeaneryPlanDocument.parse_status == enums.DocumentParseStatus.PARSED,
        )
        .order_by(DeaneryPlanDocument.uploaded_at.desc(), DeaneryPlanDocument.id.desc())
        .limit(1)
    )


def evaluate_plan_workload(db, student_id, academic_year, items, load_levels=None):
    """Prefer catalog credits, latest parsed document, then deduplicated history.

    A course occurring in two semesters is two learning units. A repeated source
    for the same course and trimester contributes only once. Older uploaded
    documents never add their mirrored academic records to the current year.
    """
    doc = latest_parsed_document(db, student_id, academic_year)
    history = db.scalars(
        select(AcademicRecord).where(
            AcademicRecord.student_id == student_id, AcademicRecord.academic_year == academic_year
        )
    ).all()
    normative = doc.normative_courses if doc else []
    ids = {i.course_id for i in [*items, *normative, *history] if i.course_id is not None}
    courses = {c.id: c for c in db.scalars(select(Course).where(Course.id.in_(ids)))} if ids else {}
    # Reconcile a legacy unlinked entry only when its normalized name has one
    # known identity. Same-name distinct courses must never be silently merged.
    aliases = {}
    for course in courses.values():
        name = " ".join(course.title.casefold().split())
        aliases.setdefault(name, set()).add(course.id)
    credits = {str(t): Decimal(0) for t in (1, 2, 3)}
    hours = {str(t): Decimal(0) for t in (1, 2, 3)}
    missing = {str(t): [] for t in (1, 2, 3)}
    seen = set()

    def add(course_id, title, trimester, value, source):
        normalized_title = " ".join(title.casefold().split())
        matches = aliases.get(normalized_title, set())
        if course_id is None and len(matches) == 1:
            course_id = next(iter(matches))
        key = (course_id if course_id is not None else normalized_title, trimester)
        if key in seen:
            return
        seen.add(key)
        tri = str(trimester)
        credits[tri] += Decimal(str(value))
        weekly = weekly_hours(courses.get(course_id), trimester)
        if weekly is None:
            missing[tri].append({"course_id": course_id, "title": title, "source": source})
        else:
            hours[tri] += Decimal(str(weekly))

    for item in items:
        course = courses.get(item.course_id)
        add(item.course_id, item.title, item.trimester, float(course.credits) if course else item.credits, "plan")
    for entry in normative:
        add(entry.course_id, entry.raw_title, entry.trimester.number, entry.credits, "deanery")
    for record in history:
        if record.document_id is not None and (doc is None or record.document_id != doc.id):
            continue
        add(record.course_id, record.title, record.trimester.number, record.credits, "history")

    total = round(float(sum(credits.values())), 1)
    errors, warnings = [], []
    complete = doc is not None and not any(missing.values())
    workload = {}
    for tri in ("1", "2", "3"):
        known = float(hours[tri])
        workload[tri] = {
            "known_weekly_hours": known,
            "complete": doc is not None and not missing[tri],
            "missing_courses": missing[tri],
            "level": classify_load_level(known) if known <= 25 and doc is not None and not missing[tri] else None,
        }
        if known > 25:
            errors.append(
                Violation(
                    "WEEKLY_LOAD_EXCEEDED",
                    f"Триместр {tri}: {known:g} год/тиждень перевищує максимум 25",
                    f"workload.{tri}",
                )
            )
    if not complete:
        warnings.append(
            Violation(
                "WORKLOAD_DATA_INCOMPLETE",
                "Перевірка годин неповна: потрібні години всіх дисциплін і розпізнаний документ деканату",
                "workload",
            )
        )
    for violation in check_annual_minimum(total):
        warnings.append(Violation("YEAR_CREDITS_BELOW_MIN", violation.message, "items"))
    levels = load_levels or {}
    if total >= 57 and any(getattr(v, "value", v) == "low" for v in levels.values()):
        warnings.append(
            Violation(
                "LOW_LOAD_FUTURE_INCREASE",
                "За низького навантаження навантаження наступних років може зрости",
                "load_levels",
            )
        )
    return WorkloadEvaluation(total, {t: float(c) for t, c in credits.items()}, workload, errors, warnings, complete)
