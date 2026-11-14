"""
Інтеграційні тести AI-воркера: adapter.run() з mock LLM-клієнтом.

Перевіряє повний flow: pending → succeeded/failed, збереження плану,
альтернативи (FR-009), ліміт вільного вибору (FR-010), retry при помилці LLM (REL-001).

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind)
за requirements.md (FR-009, FR-010, REL-001), AGENTS.md §5.
Перевірено: pytest tests/test_ai_worker.py, ruff check.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select

from src.ai import adapter
from src.db import enums as db_enums
from src.db.base import utcnow
from src.db.models.ai import PlanGeneration, PlanGenerationNotice
from src.db.models.alternatives import PlanAlternative
from src.db.models.catalog import Course
from src.db.models.plans import IndividualPlan
from src.db.session import session_factory

# ---------------------------------------------------------------------------
# Fixtures та helpers
# ---------------------------------------------------------------------------

ACADEMIC_YEAR = 2027


def _make_valid_llm_response(course_ids: list[int], alt_ids: list[tuple[int, list[int]]]) -> str:
    """Генерує валідну LLM відповідь для заданих course_id."""
    plan = [
        {
            "trimester": "autumn",
            "course_id": cid,
            "category": "professional",
            "explanation": f"Пояснення для {cid}",
        }
        for cid in course_ids
    ]
    alternatives = [
        {
            "for_course_id": for_id,
            "alternatives": [{"course_id": alt_id, "explanation": f"Alt {alt_id}"} for alt_id in alts],
        }
        for for_id, alts in alt_ids
    ]
    return json.dumps({"plan": plan, "alternatives": alternatives, "notices": []})


@pytest.fixture(autouse=True)
def cleanup_ai_data():
    """Очищає тестові дані AI-генерацій після кожного тесту."""

    def wipe():
        with session_factory()() as db:
            db.execute(delete(PlanAlternative))
            db.execute(delete(PlanGenerationNotice))
            db.execute(delete(PlanGeneration))
            # Видаляємо лише AI-генеровані плани
            db.execute(delete(IndividualPlan).where(IndividualPlan.origin == db_enums.PlanOrigin.AI_GENERATED))
            db.commit()

    wipe()
    yield
    wipe()


@pytest.fixture
def student_id() -> int:
    from src.db.models.users import StudentProfile

    with session_factory()() as db:
        sid = db.scalar(select(StudentProfile.user_id).order_by(StudentProfile.user_id).limit(1))
    assert sid is not None, "Seed не містить профілю студента"
    return sid


@pytest.fixture
def elective_courses() -> list[int]:
    """Повертає перші 3 вибіркові дисципліни зі seed."""
    with session_factory()() as db:
        ids = list(
            db.scalars(
                select(Course.id)
                .where(
                    Course.kind == db_enums.CourseKind.ELECTIVE,
                    Course.publication_status == db_enums.PublicationStatus.PUBLISHED,
                )
                .order_by(Course.id)
                .limit(3)
            )
        )
    if len(ids) < 3:
        pytest.skip("Seed не містить достатньо вибіркових дисциплін (потрібно ≥ 3)")
    return ids


@pytest.fixture
def generation(student_id: int) -> int:
    """Створює PlanGeneration зі статусом pending."""
    with session_factory()() as db:
        gen = PlanGeneration(student_id=student_id, academic_year=ACADEMIC_YEAR)
        db.add(gen)
        db.commit()
        return gen.id


# ---------------------------------------------------------------------------
# Тести успішної генерації
# ---------------------------------------------------------------------------


def test_run_creates_plan_on_success(generation: int, elective_courses: list[int]):
    """adapter.run() → plan_id заповнюється, status=succeeded."""
    main_id, alt1_id, alt2_id = elective_courses
    llm_text = _make_valid_llm_response(
        [main_id],
        [(main_id, [alt1_id, alt2_id])],
    )

    with patch("src.ai.llm_client.generate", return_value=(llm_text, 1)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        assert gen.status == db_enums.GenerationStatus.SUCCEEDED
        assert gen.plan_id is not None
        assert gen.finished_at is not None
        assert gen.attempts == 1

        plan = db.get(IndividualPlan, gen.plan_id)
        assert plan is not None
        assert plan.origin == db_enums.PlanOrigin.AI_GENERATED
        assert len(plan.items) == 1
        assert plan.items[0].course_id == main_id
        assert plan.items[0].ai_explanation == f"Пояснення для {main_id}"


def test_generated_plan_api_response_includes_ai_explanations_and_alternatives(
    generation: int, elective_courses: list[int], student_id: int
):
    """GET /plans/{plan_id} повертає ai_explanation та alternatives для кожного слота (FR-009, contract.md)."""
    from fastapi.testclient import TestClient

    from src.api.common import get_current_student_id
    from src.api.main import app
    from src.api.onboarding import get_onboarded_student

    main_id, alt1_id, alt2_id = elective_courses
    llm_text = _make_valid_llm_response(
        [main_id],
        [(main_id, [alt1_id, alt2_id])],
    )

    with patch("src.ai.llm_client.generate", return_value=(llm_text, 1)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        plan_id = gen.plan_id

    app.dependency_overrides[get_current_student_id] = lambda: student_id
    app.dependency_overrides[get_onboarded_student] = lambda: SimpleNamespace(user_id=student_id)
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/plans/{plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        item = data["items"][0]
        assert item["course_id"] == main_id
        assert item["ai_explanation"] == f"Пояснення для {main_id}"
        assert len(item["alternatives"]) == 2
        assert item["alternatives"][0]["course_id"] == alt1_id
        assert item["alternatives"][0]["rank"] == 1
        assert item["alternatives"][1]["course_id"] == alt2_id
        assert item["alternatives"][1]["rank"] == 2
    finally:
        app.dependency_overrides.pop(get_current_student_id, None)
        app.dependency_overrides.pop(get_onboarded_student, None)


def test_run_saves_alternatives(generation: int, elective_courses: list[int]):
    """FR-009: 2–3 альтернативи на слот зберігаються в plan_alternatives."""
    main_id, alt1_id, alt2_id = elective_courses
    llm_text = _make_valid_llm_response(
        [main_id],
        [(main_id, [alt1_id, alt2_id])],
    )

    with patch("src.ai.llm_client.generate", return_value=(llm_text, 1)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        alts = db.scalars(select(PlanAlternative).where(PlanAlternative.plan_id == gen.plan_id)).all()
        assert len(alts) == 2
        alt_course_ids = {a.course_id for a in alts}
        assert alt1_id in alt_course_ids
        assert alt2_id in alt_course_ids
        # Перевіряємо rank
        ranks = sorted(a.rank for a in alts)
        assert ranks == [1, 2]


def test_run_plan_item_category_professional(generation: int, elective_courses: list[int]):
    """Категорія professional зберігається правильно."""
    main_id, alt1_id, alt2_id = elective_courses
    llm_text = json.dumps(
        {
            "plan": [{"trimester": "autumn", "course_id": main_id, "category": "professional", "explanation": "Test"}],
            "alternatives": [
                {
                    "for_course_id": main_id,
                    "alternatives": [
                        {"course_id": alt1_id, "explanation": ""},
                        {"course_id": alt2_id, "explanation": ""},
                    ],
                }
            ],
            "notices": [],
        }
    )
    with patch("src.ai.llm_client.generate", return_value=(llm_text, 1)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        plan = db.get(IndividualPlan, gen.plan_id)
        item = plan.items[0]
        assert item.category == db_enums.PlanItemCategory.PROFESSIONAL


# ---------------------------------------------------------------------------
# Тести помилок LLM та retry (REL-001)
# ---------------------------------------------------------------------------


def test_run_marks_failed_on_llm_error(generation: int):
    """При LLMError generation → failed."""
    from src.ai.llm_client import LLMError

    with patch("src.ai.llm_client.generate", side_effect=LLMError("timeout", 2)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        assert gen.status == db_enums.GenerationStatus.FAILED
        assert gen.error_code == "AI_UNAVAILABLE"
        assert gen.finished_at is not None
        assert gen.plan_id is None


def test_run_marks_failed_on_parse_error(generation: int):
    """При ParseError generation → failed."""
    with patch("src.ai.llm_client.generate", return_value=("not valid json {{", 1)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        assert gen.status == db_enums.GenerationStatus.FAILED
        assert gen.error_code == "RESPONSE_PARSE_ERROR"


def test_run_stores_attempt_count(generation: int):
    """Кількість спроб зберігається в attempts (REL-001)."""
    from src.ai.llm_client import LLMError

    with patch("src.ai.llm_client.generate", side_effect=LLMError("fail", 3)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        assert gen.attempts == 3


# ---------------------------------------------------------------------------
# Тести серверної валідації
# ---------------------------------------------------------------------------


def test_run_fails_on_nonexistent_course_id(generation: int):
    """LLM повернув неіснуючий course_id → validation error."""
    llm_text = json.dumps(
        {
            "plan": [{"trimester": "autumn", "course_id": 999999, "category": "professional", "explanation": ""}],
            "alternatives": [
                {
                    "for_course_id": 999999,
                    "alternatives": [
                        {"course_id": 999998, "explanation": ""},
                        {"course_id": 999997, "explanation": ""},
                    ],
                }
            ],
            "notices": [],
        }
    )
    with patch("src.ai.llm_client.generate", return_value=(llm_text, 1)):
        adapter.run(generation)

    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        assert gen.status == db_enums.GenerationStatus.FAILED
        assert gen.error_code == "VALIDATION_ERROR"


def test_run_skips_already_pending(student_id: int, generation: int, elective_courses: list[int]):
    """Генерація вже не pending → воркер пропускає її."""
    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        gen.status = db_enums.GenerationStatus.SUCCEEDED
        gen.finished_at = utcnow()
        db.commit()

    with patch("src.ai.llm_client.generate") as mock_llm:
        adapter.run(generation)
        mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# Тести FR-010: ліміт вільного вибору
# ---------------------------------------------------------------------------


def test_run_fails_when_free_elective_limit_exceeded(generation: int, elective_courses: list[int]):
    """FR-010: генерація fails якщо new free_choice credits перевищують ліміт."""
    from src.db.models.history import AcademicRecord

    main_id, alt1_id, alt2_id = elective_courses

    # Додаємо запис що студент вже використав 24 кредити вільного вибору
    with session_factory()() as db:
        gen = db.get(PlanGeneration, generation)
        student = gen.student_id
        record = AcademicRecord(
            student_id=student,
            academic_year=2025,
            course_year=2,
            title="Попередній вільний вибір",
            credits=24.0,
            trimester=db_enums.Trimester.AUTUMN,
            category=db_enums.AcademicCategory.FREE_CHOICE,
            source=db_enums.RecordSource.ADMIN,
        )
        db.add(record)
        db.commit()

    # LLM пропонує ще 4 кредити вільного вибору → 24+4=28 > 25
    with session_factory()() as db:
        course = db.get(Course, main_id)
        course_credits = course.credits if course else 4.0

    llm_text = json.dumps(
        {
            "plan": [{"trimester": "autumn", "course_id": main_id, "category": "free_choice", "explanation": ""}],
            "alternatives": [
                {
                    "for_course_id": main_id,
                    "alternatives": [
                        {"course_id": alt1_id, "explanation": ""},
                        {"course_id": alt2_id, "explanation": ""},
                    ],
                }
            ],
            "notices": [],
        }
    )

    try:
        with patch("src.ai.llm_client.generate", return_value=(llm_text, 1)):
            adapter.run(generation)

        with session_factory()() as db:
            gen = db.get(PlanGeneration, generation)
            # Якщо credits курсу ≤ 1 — ліміт може не порушитись, пропускаємо
            if gen.status == db_enums.GenerationStatus.SUCCEEDED and course_credits <= 1.0:
                pytest.skip("Кредити дисципліни замалі для порушення ліміту")
            if course_credits > 1.0:
                assert gen.status == db_enums.GenerationStatus.FAILED
                assert gen.error_code == "VALIDATION_ERROR"
    finally:
        # Прибираємо тестовий запис
        with session_factory()() as db:
            db.execute(delete(AcademicRecord).where(AcademicRecord.title == "Попередній вільний вибір"))
            db.commit()


def test_run_generation_task_calls_adapter_run():
    from src.ai.worker import run_generation_task

    with patch("src.ai.adapter.run") as mock_run:
        run_generation_task(42)
        mock_run.assert_called_once_with(42)


def test_run_generation_task_handles_unexpected_exception():
    from src.ai.worker import run_generation_task

    with patch("src.ai.adapter.run", side_effect=RuntimeError("Unexpected error")):
        # Should not raise exception
        run_generation_task(42)
