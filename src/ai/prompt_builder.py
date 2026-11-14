"""
Побудова анонімізованого промпту для LLM AI-рекомендацій (FR-005, SEC-001, AGENTS.md §5).

КРИТИЧНО:
- Імена небажаних викладачів у промпт НЕ включаються — тільки course_id для виключення (R1).
- Дані інших студентів у промпт НЕ включаються (AGENTS.md §5).
- AI/ML-модуль має read-only доступ до БД.

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (FR-005, SEC-001), AGENTS.md §5 та існуючими моделями БД.
Перевірено: pytest tests/test_ai_prompt_builder.py, ruff check src/ai/prompt_builder.py.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.plan_checks import normative_course_ids as fetch_normative_course_ids
from ..db import enums as db_enums
from ..db.models.catalog import Course, Direction
from ..db.models.history import AcademicRecord
from ..db.models.plans import IndividualPlan
from ..db.models.preferences import PlanPreferences
from ..db.models.users import StudentProfile
from ..services.plan_rules import FREE_ELECTIVE_LIMIT


@dataclass
class CourseContext:
    """Дані про дисципліну для промпту (анонімізовано: без імен викладачів)."""

    id: int
    title: str
    description: str
    credits: float
    trimester: str  # "autumn" | "spring" | "summer"
    recommended_year: int
    direction_ids: list[int]
    instructor_ids: list[int]  # для серверної фільтрації небажаних (не передається в LLM як текст)


@dataclass
class PromptContext:
    """Повний контекст для побудови промпту."""

    student_course_year: int
    student_specialty: Optional[str]
    academic_year: int
    direction_ids: list[int]
    direction_names: list[str]
    include_free_electives: bool
    wants_certificate: bool
    certificate_program_id: Optional[int]
    load_levels: dict[str, str]  # {"autumn": "medium", ...}
    # Каталог вибіркових (вже відфільтровано: лише ELECTIVE + PUBLISHED)
    available_courses: list[CourseContext]
    # Курси, виключені через небажаних викладачів (FR-005)
    excluded_course_ids: list[int]
    # Нормативні дисципліни деканату поточного року (виключаються зі слотів)
    normative_course_ids: list[int]
    # Академічна історія студента (пройдені course_id за категоріями)
    history_professional_ids: list[int]
    history_free_choice_ids: list[int]
    history_free_choice_credits_used: float
    # Плани попередніх років (AI-генеровані або ручні, без даних інших студентів)
    past_plan_course_ids: list[int]


def build_context(db: Session, student_id: int, academic_year: int) -> PromptContext:
    """
    Збирає read-only контекст для побудови промпту.
    Небажані викладачі → excluded_course_ids (не передаються як імена в LLM).
    """
    # --- Профіль студента ---
    profile = db.get(StudentProfile, student_id)
    course_year = profile.course_year if profile else 2
    specialty = profile.specialty if profile else None

    # --- Побажання ---
    prefs: Optional[PlanPreferences] = db.scalar(
        select(PlanPreferences).where(
            PlanPreferences.student_id == student_id,
            PlanPreferences.academic_year == academic_year,
        )
    )

    direction_ids: list[int] = []
    direction_names: list[str] = []
    load_levels: dict[str, str] = {"autumn": "medium", "spring": "medium", "summer": "medium"}
    unwanted_instructor_ids: list[int] = []
    include_free_electives = True
    wants_certificate = False
    certificate_program_id = None

    if prefs:
        direction_ids = [pd.direction_id for pd in prefs.directions]
        load_levels = {tl.trimester.value: tl.load_level.value for tl in prefs.trimester_loads}
        unwanted_instructor_ids = [
            ip.instructor_id
            for ip in prefs.instructor_preferences
            if ip.kind == db_enums.InstructorPreferenceKind.UNWANTED
        ]
        include_free_electives = prefs.include_free_electives
        wants_certificate = prefs.wants_certificate
        certificate_program_id = prefs.certificate_program_id

    # Назви напрямків
    if direction_ids:
        directions = db.scalars(select(Direction).where(Direction.id.in_(direction_ids))).all()
        direction_names = [d.name for d in directions]

    # --- Каталог вибіркових (read-only) ---
    all_elective_courses = db.scalars(
        select(Course).where(
            Course.kind == db_enums.CourseKind.ELECTIVE,
            Course.publication_status == db_enums.PublicationStatus.PUBLISHED,
        )
    ).all()

    # Визначаємо course_id для виключення через небажаних викладачів (FR-005)
    excluded_course_ids: list[int] = []
    course_contexts: list[CourseContext] = []

    for course in all_elective_courses:
        instructor_ids = [ci.instructor_id for ci in course.course_instructors]
        course_contexts.append(
            CourseContext(
                id=course.id,
                title=course.title,
                description=course.description[:500] if course.description else "",
                credits=course.credits,
                trimester=course.trimester.value,
                recommended_year=course.recommended_year,
                direction_ids=[d.id for d in course.directions],
                instructor_ids=instructor_ids,
            )
        )
        # Якщо хоч один викладач небажаний — виключаємо курс
        if unwanted_instructor_ids and set(instructor_ids) & set(unwanted_instructor_ids):
            excluded_course_ids.append(course.id)

    # --- Нормативні дисципліни деканату поточного року ---
    normative_ids = sorted(fetch_normative_course_ids(db, student_id, academic_year))

    # --- Академічна історія студента (лише власна, FR-005, AGENTS.md §5) ---
    history_records = db.scalars(select(AcademicRecord).where(AcademicRecord.student_id == student_id)).all()

    history_professional_ids: list[int] = []
    history_free_choice_ids: list[int] = []
    history_free_choice_credits = 0.0

    for rec in history_records:
        if rec.course_id is None:
            continue
        if rec.category == db_enums.AcademicCategory.FREE_CHOICE:
            history_free_choice_ids.append(rec.course_id)
            history_free_choice_credits += rec.credits
        elif rec.category in (db_enums.AcademicCategory.PROFESSIONAL, db_enums.AcademicCategory.NORMATIVE):
            history_professional_ids.append(rec.course_id)

    # --- Плани попередніх років ---
    past_plans = db.scalars(
        select(IndividualPlan).where(
            IndividualPlan.student_id == student_id,
            IndividualPlan.academic_year < academic_year,
        )
    ).all()
    past_plan_course_ids = list({item.course_id for plan in past_plans for item in plan.items})

    return PromptContext(
        student_course_year=course_year,
        student_specialty=specialty,
        academic_year=academic_year,
        direction_ids=direction_ids,
        direction_names=direction_names,
        include_free_electives=include_free_electives,
        wants_certificate=wants_certificate,
        certificate_program_id=certificate_program_id,
        load_levels=load_levels,
        available_courses=course_contexts,
        excluded_course_ids=excluded_course_ids,
        normative_course_ids=normative_ids,
        history_professional_ids=history_professional_ids,
        history_free_choice_ids=history_free_choice_ids,
        history_free_choice_credits_used=history_free_choice_credits,
        past_plan_course_ids=past_plan_course_ids,
    )


def build_prompt(ctx: PromptContext) -> tuple[str, str]:
    """
    Будує системний + користувацький промпт.
    Повертає (prompt_text, sha256_hex).
    Небажані викладачі НЕ включаються як текст — тільки excluded_course_ids.
    """
    # Доступні курси (виключаємо excluded + нормативні + вже пройдені)
    all_excluded = (
        set(ctx.excluded_course_ids)
        | set(ctx.normative_course_ids)
        | set(ctx.history_professional_ids)
        | set(ctx.history_free_choice_ids)
    )
    available = [c for c in ctx.available_courses if c.id not in all_excluded]

    # Компактне представлення курсів для промпту
    courses_data = [
        {
            "id": c.id,
            "title": c.title,
            "description": c.description,
            "credits": c.credits,
            "trimester": c.trimester,
            "recommended_year": c.recommended_year,
            "direction_ids": c.direction_ids,
        }
        for c in available
    ]

    free_elective_budget = max(0.0, FREE_ELECTIVE_LIMIT - ctx.history_free_choice_credits_used)

    system_prompt = (
        "You are an academic planning assistant for NaUKMA Faculty of Informatics. "
        "Your task is to build a personalized individual study plan for a student based on their preferences, "
        "academic history, and available elective courses.\n\n"
        "RULES:\n"
        "1. Only use courses from the provided catalog (available_courses). Do not invent course IDs.\n"
        "2. Each course can appear at most once in the plan.\n"
        "3. Assign each course to its correct trimester as listed in the catalog.\n"
        "4. For each plan slot, provide exactly 2-3 alternative courses from the same trimester.\n"
        "5. Write explanations in Ukrainian.\n"
        "6. Consider the student's load level preferences per trimester.\n"
        "7. Prioritize courses matching the student's direction_ids.\n"
        f"8. Free elective budget remaining: {free_elective_budget:.1f} credits.\n"
        "9. Do not include courses the student has already completed (past_course_ids).\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "plan": [\n'
        '    {"trimester": "autumn|spring|summer", "course_id": <int>, '
        '"category": "professional|free_choice", "explanation": "<Ukrainian text>"}\n'
        "  ],\n"
        '  "alternatives": [\n'
        '    {"for_course_id": <int>, "alternatives": [{"course_id": <int>, "explanation": "<Ukrainian text>"}, ...]}\n'
        "  ],\n"
        '  "notices": [\n'
        '    {"code": "<string>", "message": "<Ukrainian text>", "course_id": <int|null>}\n'
        "  ]\n"
        "}"
    )

    user_data = {
        "student": {
            "course_year": ctx.student_course_year,
            "specialty": ctx.student_specialty,
            "academic_year": ctx.academic_year,
        },
        "preferences": {
            "direction_ids": ctx.direction_ids,
            "direction_names": ctx.direction_names,
            "load_levels": ctx.load_levels,
            "include_free_electives": ctx.include_free_electives,
            "wants_certificate": ctx.wants_certificate,
        },
        "past_course_ids": ctx.past_plan_course_ids,
        "available_courses": courses_data,
    }

    user_prompt = json.dumps(user_data, ensure_ascii=False)
    full_text = system_prompt + "\n\n" + user_prompt
    sha256 = hashlib.sha256(full_text.encode()).hexdigest()
    return full_text, sha256
