"""
Головний адаптер AI-генерації: оркеструє промпт → LLM → парсинг → серверна валідація → збереження.

Серверна пост-валідація (незалежно від відповіді LLM):
- Небажані викладачі справді виключені; якщо ні — UNWANTED_INSTRUCTOR_UNAVOIDABLE (FR-005, FR-006)
- Ліміт вільного вибору ≤ 25 кредитів за всі роки (FR-010)
- Усі course_id у відповіді існують у БД і є ELECTIVE
- Кількість альтернатив: 2–3 на слот (FR-009)
- Нормативні дисципліни деканату не потрапляють до слотів

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (FR-005, FR-006, FR-009, FR-010, REL-001, PERF-001),
AGENTS.md §5 та існуючими моделями БД. Перевірено: pytest tests/test_ai_worker.py, ruff check src/ai/adapter.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.models.ai import PlanGeneration, PlanGenerationNotice
from ..db.models.alternatives import PlanAlternative
from ..db.models.catalog import Course
from ..db.models.history import AcademicRecord
from ..db.models.plans import IndividualPlan, PlanItem
from ..db.session import session_factory
from . import llm_client, response_parser
from .llm_client import LLMError
from .prompt_builder import build_context, build_prompt
from .response_parser import LLMResponse, ParseError

logger = logging.getLogger("yourpath.ai.adapter")

FREE_ELECTIVE_LIMIT = 25.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fetch_course_map(db: Session, course_ids: list[int]) -> dict[int, Course]:
    """Завантажує дисципліни з БД за списком id."""
    if not course_ids:
        return {}
    courses = db.scalars(select(Course).where(Course.id.in_(course_ids))).all()
    return {c.id: c for c in courses}


def _used_free_choice_credits(db: Session, student_id: int, exclude_plan_id: int | None = None) -> float:
    """Рахує вже використані кредити вільного вибору за всі роки (крім поточного плану)."""
    records = db.scalars(
        select(AcademicRecord).where(
            AcademicRecord.student_id == student_id,
            AcademicRecord.category == db_enums.AcademicCategory.FREE_CHOICE,
        )
    ).all()
    return sum(r.credits for r in records)


def _validate_and_save(
    db: Session,
    generation: PlanGeneration,
    llm_response: LLMResponse,
    ctx,
    attempts: int,
) -> IndividualPlan:
    """
    Серверна пост-валідація відповіді LLM і збереження плану.
    Кидає ValueError при критичних порушеннях.
    """
    plan_items_data = llm_response.plan
    all_course_ids = [item.course_id for item in plan_items_data]
    for slot in llm_response.alternatives:
        for alt in slot.alternatives:
            all_course_ids.append(alt.course_id)

    # Перевірка: всі course_id існують і є ELECTIVE
    course_map = _fetch_course_map(db, list(set(all_course_ids)))
    invalid_ids = [cid for cid in all_course_ids if cid not in course_map]
    if invalid_ids:
        raise ValueError(f"LLM повернув неіснуючі course_id: {sorted(set(invalid_ids))}")

    normative_in_plan = [
        cid
        for cid in [item.course_id for item in plan_items_data]
        if course_map.get(cid) and course_map[cid].kind == db_enums.CourseKind.NORMATIVE
    ]
    if normative_in_plan:
        raise ValueError(f"LLM включив нормативні дисципліни у вибіркові слоти: {normative_in_plan}")

    # Перевірка нормативних дисциплін деканату
    normative_conflicts = [
        cid for cid in [item.course_id for item in plan_items_data] if cid in ctx.normative_course_ids
    ]
    if normative_conflicts:
        raise ValueError(f"LLM включив нормативні дисципліни деканату: {normative_conflicts}")

    # Серверна перевірка небажаних викладачів (FR-005, FR-006)
    notices: list[PlanGenerationNotice] = []
    unwanted_set = set(ctx.excluded_course_ids)
    for item in plan_items_data:
        if item.course_id in unwanted_set:
            # Перевіряємо чи є альтернативи без небажаних викладачів
            slot = next((s for s in llm_response.alternatives if s.for_course_id == item.course_id), None)
            has_safe_alt = slot and any(alt.course_id not in unwanted_set for alt in slot.alternatives)
            course = course_map.get(item.course_id)
            notice_msg = (
                f"Дисципліну «{course.title if course else item.course_id}» "
                f"викладає лише небажаний викладач" + ("" if has_safe_alt else " і безпечних альтернатив немає")
            )
            notices.append(
                PlanGenerationNotice(
                    code="UNWANTED_INSTRUCTOR_UNAVOIDABLE",
                    message=notice_msg,
                    course_id=item.course_id,
                )
            )
            logger.warning("UNWANTED_INSTRUCTOR_UNAVOIDABLE course_id=%d", item.course_id)

    # Перевірка ліміту вільного вибору (FR-010)
    used_in_other_years = _used_free_choice_credits(db, generation.student_id)
    new_free_credits = sum(
        course_map[item.course_id].credits
        for item in plan_items_data
        if item.category == "free_choice" and item.course_id in course_map
    )
    total_free = used_in_other_years + new_free_credits
    if total_free > FREE_ELECTIVE_LIMIT:
        raise ValueError(
            f"Ліміт вільного вибору перевищено: {total_free:.1f} > {FREE_ELECTIVE_LIMIT:.1f} кредитів (FR-010)"
        )

    # Збереження IndividualPlan
    plan = IndividualPlan(
        student_id=generation.student_id,
        academic_year=generation.academic_year,
        course_year=ctx.student_course_year,
        status=db_enums.PlanStatus.DRAFT,
        origin=db_enums.PlanOrigin.AI_GENERATED,
        load_autumn=db_enums.LoadLevel(ctx.load_levels.get("autumn", "medium")),
        load_spring=db_enums.LoadLevel(ctx.load_levels.get("spring", "medium")),
        load_summer=db_enums.LoadLevel(ctx.load_levels.get("summer", "medium")),
    )
    db.add(plan)
    db.flush()  # щоб отримати plan.id

    # Збереження PlanItem
    items_map: dict[int, PlanItem] = {}  # course_id → PlanItem
    for item_data in plan_items_data:
        course = course_map[item_data.course_id]
        category = (
            db_enums.PlanItemCategory.FREE_CHOICE
            if item_data.category == "free_choice"
            else db_enums.PlanItemCategory.PROFESSIONAL
        )
        trimester = db_enums.Trimester(item_data.trimester)
        plan_item = PlanItem(
            plan_id=plan.id,
            course_id=item_data.course_id,
            course=course,
            trimester=trimester,
            category=category,
            ai_explanation=item_data.explanation,
        )
        db.add(plan_item)
        db.flush()
        items_map[item_data.course_id] = plan_item

    # Перерахунок total_credits
    plan.total_credits = round(
        sum(course_map[i.course_id].credits for i in plan_items_data if i.course_id in course_map), 1
    )

    # Збереження PlanAlternative (FR-009)
    for slot in llm_response.alternatives:
        plan_item = items_map.get(slot.for_course_id)
        for rank, alt in enumerate(slot.alternatives, start=1):
            course = course_map.get(alt.course_id)
            if course is None:
                continue
            alternative = PlanAlternative(
                plan_id=plan.id,
                plan_item_id=plan_item.id if plan_item else None,
                course_id=alt.course_id,
                trimester=course.trimester,
                explanation=alt.explanation,
                rank=rank,
            )
            db.add(alternative)

    # Оновлення PlanGeneration
    generation.status = db_enums.GenerationStatus.SUCCEEDED
    generation.plan_id = plan.id
    generation.attempts = attempts
    generation.finished_at = _utcnow()
    generation.notices = notices

    db.commit()
    logger.info("AI plan saved: plan_id=%d generation_id=%d", plan.id, generation.id)
    return plan


def run(generation_id: int) -> None:
    """
    Головна функція воркера. Завантажує generation, будує промпт, викликає LLM, зберігає план.
    При помилці після вичерпання retry — позначає generation як failed.
    REL-001: llm_client виконує ≥ 2 повторних спроби при помилці LLM.
    """
    SessionLocal = session_factory()
    attempts = 0

    with SessionLocal() as db:
        generation = db.get(PlanGeneration, generation_id)
        if generation is None:
            logger.error("Generation %d not found", generation_id)
            return
        if generation.status != db_enums.GenerationStatus.PENDING:
            logger.warning("Generation %d is not pending (status=%s), skipping", generation_id, generation.status)
            return

        logger.info("Starting AI generation: generation_id=%d student_id=%d", generation_id, generation.student_id)

    try:
        # Збираємо контекст (read-only)
        with SessionLocal() as db:
            ctx = build_context(db, generation.student_id, generation.academic_year)

        system_prompt, user_prompt_full, sha256 = _split_prompt(ctx)

        # Оновлюємо prompt_sha256
        with SessionLocal() as db:
            gen = db.get(PlanGeneration, generation_id)
            gen.prompt_sha256 = sha256
            db.commit()

        # Виклик LLM з retry (REL-001)
        raw_response, attempts = llm_client.generate(system_prompt, user_prompt_full)

        # Парсинг відповіді
        llm_response = response_parser.parse(raw_response)

        # Збереження
        with SessionLocal() as db:
            gen = db.get(PlanGeneration, generation_id)
            _validate_and_save(db, gen, llm_response, ctx, attempts)

    except LLMError as exc:
        attempts = exc.attempts
        _mark_failed(SessionLocal, generation_id, "AI_UNAVAILABLE", str(exc), attempts)
        logger.error("LLM unavailable for generation %d: %s", generation_id, exc)

    except ParseError as exc:
        _mark_failed(SessionLocal, generation_id, "RESPONSE_PARSE_ERROR", str(exc), attempts)
        logger.error("Parse error for generation %d: %s", generation_id, exc)

    except ValueError as exc:
        _mark_failed(SessionLocal, generation_id, "VALIDATION_ERROR", str(exc), attempts)
        logger.error("Validation error for generation %d: %s", generation_id, exc)

    except Exception as exc:
        _mark_failed(SessionLocal, generation_id, "INTERNAL_ERROR", str(exc), attempts)
        logger.exception("Unexpected error for generation %d", generation_id)


def _split_prompt(ctx) -> tuple[str, str, str]:
    """Розбиває повний промпт на system + user і повертає sha256."""
    full_prompt, sha256 = build_prompt(ctx)
    # build_prompt повертає system+user concatenated — ділимо по маркеру
    # Для llm_client нам потрібно system окремо + user окремо
    # prompt_builder.build_prompt повертає повний текст для sha256,
    # тому викликаємо окремо
    system_part, user_part = _extract_parts(ctx)
    return system_part, user_part, sha256


def _extract_parts(ctx) -> tuple[str, str]:
    """Повертає (system_prompt, user_prompt) для LLM API."""
    import json

    # Перебудовуємо промпт щоб отримати частини окремо
    # Дублюємо логіку build_prompt для розділення
    all_excluded = (
        set(ctx.excluded_course_ids)
        | set(ctx.normative_course_ids)
        | set(ctx.history_professional_ids)
        | set(ctx.history_free_choice_ids)
    )
    available = [c for c in ctx.available_courses if c.id not in all_excluded]
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
        f"8. Free elective budget remaining: {max(0.0, 25.0 - ctx.history_free_choice_credits_used):.1f} credits.\n"
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

    return system_prompt, json.dumps(user_data, ensure_ascii=False)


def _mark_failed(SessionLocal, generation_id: int, error_code: str, error_message: str, attempts: int) -> None:
    """Позначає генерацію як failed у БД."""
    try:
        with SessionLocal() as db:
            gen = db.get(PlanGeneration, generation_id)
            if gen:
                gen.status = db_enums.GenerationStatus.FAILED
                gen.error_code = error_code
                gen.error_message = error_message[:1000]
                gen.attempts = attempts
                gen.finished_at = _utcnow()
                db.commit()
    except Exception:
        logger.exception("Failed to mark generation %d as failed", generation_id)
