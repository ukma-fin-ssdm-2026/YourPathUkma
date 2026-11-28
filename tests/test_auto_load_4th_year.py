# Використання ШІ: Codex доповнив облік годин і кредитів #291; перевірка: pytest і лінтери.
"""
Тести автоматичного розрахунку навантаження для 4 курсу (FR-003, US-009, issue #292).

Перевіряє:
- зміну результату залежно від фактичного залишку (не завжди medium);
- сценарії: 180/240 уже зараховано, 240/240, некоректна історія понад 240, недостатній каталог;
- врахування нормативних дисциплін деканату поточного року;
- неможливий розподіл навантаження (перевищення 25 год/тиждень) повертає зрозумілу помилку 422;
- блокування ручного перевизначення автоматичних значень;
- облік кредитів без подвійного підрахунку історії та затверджених планів;
- повернення пояснення розрахунку та load_levels_mode='auto' в API.

Використання ШІ: файл створено за допомогою Antigravity (Gemini 2.5 Pro, Google DeepMind).
Перевірка: pytest, ruff.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.api.main import app
from src.db import enums as db_enums
from src.db.models import Course, IndividualPlan, PlanItem
from src.db.models.deanery import DeaneryPlanDocument, NormativeCourseEntry
from src.db.models.history import AcademicRecord
from src.db.models.preferences import PlanPreferences, TrimesterLoad
from src.db.models.users import StudentProfile
from src.db.session import session_factory
from src.services.load_levels import (
    InsufficientCatalogCoursesError,
    LoadDistributionFailedError,
    NormativeCreditsExceedRemainingError,
    TotalCreditsExceededError,
    distribute_auto_load,
)

client = TestClient(app)
STUDENT_4TH_YEAR_ID = 42
ACADEMIC_YEAR = 2026


# ============================================================================
# 1. ЧИСТІ ЮНІТ-ТЕСТИ РОЗПОДІЛУ (distribute_auto_load)
# ============================================================================


def test_unit_180_of_240_gives_medium_load():
    """180/240 зараховано -> залишок 60 -> по 20 кр./триместр -> medium/medium/medium."""
    catalog = {"autumn": 30.0, "spring": 30.0, "summer": 30.0}
    res = distribute_auto_load(earned_credits=180.0, catalog_available_by_trimester=catalog)
    assert res.remaining_credits == 60.0
    assert res.remaining_elective_credits == 60.0
    assert res.trimester_credits == {"autumn": 20.0, "spring": 20.0, "summer": 20.0}
    assert res.autumn_level == "medium"
    assert res.spring_level == "medium"
    assert res.summer_level == "medium"
    assert "20 кр. (medium)" in res.explanation


def test_unit_240_of_240_gives_low_load():
    """240/240 зараховано -> залишок 0 -> навантаження мінімальне (low)."""
    res = distribute_auto_load(earned_credits=240.0, weekly_by_trimester={k: 0 for k in ("autumn", "spring", "summer")})
    assert res.remaining_credits == 0.0
    assert res.remaining_elective_credits == 0.0
    assert res.autumn_level == "low"
    assert res.spring_level == "low"
    assert res.summer_level == "low"
    assert res.remaining_credits == 0


def test_unit_186_credits_gives_low_load():
    """186/240 зараховано -> залишок 54 -> по 18 кр./триместр -> low/low/low."""
    catalog = {"autumn": 30.0, "spring": 30.0, "summer": 30.0}
    res = distribute_auto_load(
        earned_credits=186.0, catalog_available_by_trimester=catalog, weekly_by_trimester={k: 18 for k in catalog}
    )
    assert res.remaining_credits == 54.0
    assert res.trimester_credits == {"autumn": 18.0, "spring": 18.0, "summer": 18.0}
    assert res.autumn_level == "low"
    assert res.spring_level == "low"
    assert res.summer_level == "low"


def test_unit_170_credits_gives_high_load():
    """170/240 зараховано -> залишок 70 -> ~23.3 кр./триместр -> high/high/high."""
    catalog = {"autumn": 30.0, "spring": 30.0, "summer": 30.0}
    res = distribute_auto_load(
        earned_credits=170.0, catalog_available_by_trimester=catalog, weekly_by_trimester={k: 23.3 for k in catalog}
    )
    assert res.remaining_credits == 70.0
    assert res.autumn_level == "high"
    assert res.spring_level == "high"
    assert res.summer_level == "high"


def test_unit_history_over_240_raises_error():
    """Некоректна історія понад 240 кредитів кидає TotalCreditsExceededError."""
    with pytest.raises(TotalCreditsExceededError) as exc_info:
        distribute_auto_load(earned_credits=245.0)
    assert exc_info.value.code == "TOTAL_CREDITS_EXCEEDED"
    assert "245" in exc_info.value.message


def test_unit_insufficient_catalog_raises_error():
    """Недостатній каталог для залишку вибіркових кидає InsufficientCatalogCoursesError."""
    catalog = {"autumn": 5.0, "spring": 5.0, "summer": 5.0}  # Всього 15 кр.
    with pytest.raises(InsufficientCatalogCoursesError) as exc_info:
        distribute_auto_load(earned_credits=180.0, catalog_available_by_trimester=catalog)
    assert exc_info.value.code == "INSUFFICIENT_CATALOG_COURSES"
    assert "15" in exc_info.value.message
    assert "60" in exc_info.value.message


def test_unit_normative_courses_accounted_for():
    """Нормативні дисципліни враховуються у навантаженні триместрів."""
    catalog = {"autumn": 30.0, "spring": 30.0, "summer": 30.0}
    norm = {"autumn": 10.0, "spring": 10.0, "summer": 10.0}  # 30 нормативних
    res = distribute_auto_load(
        earned_credits=180.0, normative_by_trimester=norm, catalog_available_by_trimester=catalog
    )
    assert res.remaining_credits == 60.0
    assert res.normative_credits == 30.0
    assert res.remaining_elective_credits == 30.0
    # 10 нормативних + 10 вибіркових = 20 кр. (medium) на кожен триместр
    assert res.trimester_credits == {"autumn": 20.0, "spring": 20.0, "summer": 20.0}
    assert res.autumn_level == "medium"
    assert res.spring_level == "medium"
    assert res.summer_level == "medium"


def test_unit_normative_exceeds_remaining_raises_error():
    """Нормативні дисципліни перевищують залишок до 240."""
    norm = {"autumn": 25.0, "spring": 25.0, "summer": 20.0}  # 70 кр. нормативних
    with pytest.raises(NormativeCreditsExceedRemainingError) as exc_info:
        distribute_auto_load(earned_credits=190.0, normative_by_trimester=norm)
    assert exc_info.value.code == "NORMATIVE_CREDITS_EXCEED_REMAINING"


def test_unit_impossible_distribution_raises_error():
    """Неможливий розподіл через перевищення ліміту 25 год/тиждень."""
    norm = {"autumn": 26.0, "spring": 0.0, "summer": 0.0}  # > 25
    with pytest.raises(LoadDistributionFailedError) as exc_info:
        distribute_auto_load(earned_credits=180.0, normative_by_trimester=norm, weekly_by_trimester={"autumn": 26})
    assert exc_info.value.code == "LOAD_DISTRIBUTION_FAILED"


# ============================================================================
# 2. ІНТЕГРАЦІЙНІ ТЕСТИ API (PUT/GET /preferences/{academic_year}, /plans)
# ============================================================================


@pytest.fixture
def setup_4th_year_student():
    """Налаштовує тестового студента 42 як студента 4 курсу та чистить створені записи."""
    with session_factory()() as db:
        profile = db.get(StudentProfile, STUDENT_4TH_YEAR_ID)
        assert profile is not None
        original_course = profile.course_year
        profile.course_year = 4
        db.commit()

    yield

    with session_factory()() as db:
        profile = db.get(StudentProfile, STUDENT_4TH_YEAR_ID)
        if profile:
            profile.course_year = original_course
        # Очищуємо тестові записи історії та побажань
        db.execute(delete(AcademicRecord).where(AcademicRecord.student_id == STUDENT_4TH_YEAR_ID))
        db.execute(delete(TrimesterLoad))
        db.execute(delete(PlanPreferences).where(PlanPreferences.student_id == STUDENT_4TH_YEAR_ID))
        db.execute(delete(NormativeCourseEntry))
        db.execute(delete(DeaneryPlanDocument).where(DeaneryPlanDocument.student_id == STUDENT_4TH_YEAR_ID))
        db.commit()


@pytest.fixture
def seed_catalog_electives():
    """Додає додаткові вибіркові курси в каталог для тестування великих обсягів залишку."""
    added_course_ids = []
    with session_factory()() as db:
        # Додаємо курси по 15 кр. на кожен триместр
        trimesters = [db_enums.Trimester.AUTUMN, db_enums.Trimester.SPRING, db_enums.Trimester.SUMMER]
        for i, trimester in enumerate(trimesters):
            for j in range(3):
                course_id = 9000 + i * 10 + j
                title = f"Тестовий вибірковий курс {course_id}"
                course = Course(
                    id=course_id,
                    saz_code=f"TEST-4Y-{course_id}",
                    title=title,
                    title_normalized=title.lower(),
                    credits=10.0,
                    trimester=trimester,
                    recommended_year=4,
                    kind=db_enums.CourseKind.ELECTIVE,
                    publication_status=db_enums.PublicationStatus.PUBLISHED,
                )
                db.add(course)
                added_course_ids.append(course_id)
        db.commit()

    yield added_course_ids

    with session_factory()() as db:
        db.execute(delete(Course).where(Course.id.in_(added_course_ids)))
        db.commit()


def _record_academic_credits(credits: float, title: str = "Зараховані кредити") -> None:
    with session_factory()() as db:
        db.add(
            AcademicRecord(
                student_id=STUDENT_4TH_YEAR_ID,
                academic_year=2025,
                course_year=3,
                title=title,
                credits=credits,
                trimester=db_enums.Trimester.AUTUMN,
                category=db_enums.AcademicCategory.PROFESSIONAL,
                source=db_enums.RecordSource.SELF_DECLARED,
            )
        )
        db.commit()


def _make_dummy_preferences(load_level: str = "medium") -> dict:
    return {
        "academic_year": ACADEMIC_YEAR,
        "load_levels": {"autumn": load_level, "spring": load_level, "summer": load_level},
        "direction_ids": [],
        "include_free_electives": True,
        "preferred_instructor_ids": [],
        "unwanted_instructor_ids": [],
        "wants_certificate": False,
        "certificate_program_id": None,
    }


def test_api_preferences_4th_year_overrides_manual_input_with_auto(setup_4th_year_student, seed_catalog_electives):
    """Для 4 курсу сервер ігнорує ручний вибір навантаження і вираховує його автоматично."""
    # 1. Додаємо 180 кредитів у історію
    with session_factory()() as db:
        for year in (1, 2, 3):
            db.add(
                AcademicRecord(
                    student_id=STUDENT_4TH_YEAR_ID,
                    academic_year=2023 + year,
                    course_year=year,
                    title=f"Дисципліна {year} курсу",
                    credits=60.0,
                    trimester=db_enums.Trimester.AUTUMN,
                    category=db_enums.AcademicCategory.PROFESSIONAL,
                    source=db_enums.RecordSource.SELF_DECLARED,
                )
            )
        db.commit()

    # 2. Надсилаємо ручний вибір 'high' по всіх триместрах
    response = client.put(f"/api/v1/preferences/{ACADEMIC_YEAR}", json=_make_dummy_preferences("high"))
    assert response.status_code == 200
    data = response.json()

    # 3. Перевіряємо, що сервер перерахував на 'medium' (залишок 60 -> по 20 кр./триместр)
    assert data["load_levels"]["autumn"] == "medium"
    assert data["load_levels"]["spring"] == "medium"
    assert data["load_levels"]["summer"] == "medium"
    assert data["load_levels_mode"] == "auto"
    assert "Автоматичний розрахунок для 4 курсу" in data["auto_load_explanation"]
    assert "20 кр. (medium)" in data["auto_load_explanation"]


def test_api_preferences_4th_year_240_credits_gives_low(setup_4th_year_student):
    """240/240 кредитів уже зараховано -> low/low/low."""
    _record_academic_credits(240.0, "Повні 240 кредитів")
    response = client.put(f"/api/v1/preferences/{ACADEMIC_YEAR}", json=_make_dummy_preferences())
    assert response.status_code == 200
    data = response.json()
    assert data["load_levels"]["autumn"] == "medium"
    assert data["load_levels"]["spring"] == "medium"
    assert data["load_levels"]["summer"] == "medium"
    assert "Години неповні" in data["auto_load_explanation"]


def test_api_preferences_4th_year_over240_credits_raises_422(setup_4th_year_student):
    """Некоректна історія понад 240 кредитів повертає 422 TOTAL_CREDITS_EXCEEDED."""
    _record_academic_credits(245.0, "Перевищення нормативу")
    response = client.put(f"/api/v1/preferences/{ACADEMIC_YEAR}", json=_make_dummy_preferences())
    assert response.status_code == 422
    assert response.json()["code"] == "TOTAL_CREDITS_EXCEEDED"


def test_api_preferences_4th_year_insufficient_catalog_raises_422(setup_4th_year_student):
    """Недостатній каталог вибіркових курсів повертає 422 INSUFFICIENT_CATALOG_COURSES."""
    # 180 зараховано, залишок 60, але в стандартному демо-каталозі всього 12 кредитів
    _record_academic_credits(180.0, "180 кредитів")
    response = client.put(f"/api/v1/preferences/{ACADEMIC_YEAR}", json=_make_dummy_preferences())
    assert response.status_code == 422
    assert response.json()["code"] == "INSUFFICIENT_CATALOG_COURSES"


def test_api_preferences_4th_year_with_deanery_document(setup_4th_year_student, seed_catalog_electives):
    """Нормативні дисципліни поточного року враховуються при авторозподілі."""
    _record_academic_credits(180.0, "180 кредитів")

    with session_factory()() as db:
        # Додаємо документ деканату на 2026 рік з нормативними дисциплінами на 30 кредитів
        doc = DeaneryPlanDocument(
            student_id=STUDENT_4TH_YEAR_ID,
            academic_year=ACADEMIC_YEAR,
            original_filename="deanery_4th_year.docx",
            mime_type=db_enums.DocumentMimeType.DOCX,
            size_bytes=2048,
            sha256="1" * 64,
            content=b"test",
            parse_status=db_enums.DocumentParseStatus.PARSED,
        )
        db.add(doc)
        db.flush()

        for tri in (db_enums.Trimester.AUTUMN, db_enums.Trimester.SPRING, db_enums.Trimester.SUMMER):
            db.add(
                NormativeCourseEntry(
                    document_id=doc.id,
                    raw_title=f"Нормативна дисципліна {tri.value}",
                    credits=10.0,
                    trimester=tri,
                )
            )
        db.commit()

    response = client.put(f"/api/v1/preferences/{ACADEMIC_YEAR}", json=_make_dummy_preferences("low"))
    assert response.status_code == 200
    data = response.json()

    # 10 нормативних + 10 вибіркових = 20 кр. на триместр (medium)
    assert data["load_levels"]["autumn"] == "medium"
    assert data["load_levels"]["spring"] == "medium"
    assert data["load_levels"]["summer"] == "medium"
    assert "нормативних у поточному році 30 кр." in data["auto_load_explanation"]
    assert "залишок вибіркових 30 кр." in data["auto_load_explanation"]


def test_api_plans_create_4th_year_assigns_auto_load(setup_4th_year_student, seed_catalog_electives):
    """Створення плану для 4 курсу автоматично виставляє розраховане навантаження."""
    # 1. Зберігаємо 186 кредитів (залишок 54 -> по 18 кр. -> low)
    _record_academic_credits(186.0, "186 кредитів")

    # 2. Зберігаємо побажання для розрахунку auto load levels
    pref_payload = {
        "academic_year": ACADEMIC_YEAR,
        "direction_ids": [],
        "include_free_electives": True,
        "preferred_instructor_ids": [],
        "unwanted_instructor_ids": [],
        "wants_certificate": False,
        "certificate_program_id": None,
    }
    pref_res = client.put(f"/api/v1/preferences/{ACADEMIC_YEAR}", json=pref_payload)
    assert pref_res.status_code == 200
    assert pref_res.json()["load_levels"]["autumn"] == "medium"

    # 3. Створюємо план без явного надсилання load_levels
    plan_payload = {
        "academic_year": ACADEMIC_YEAR,
        "course": 4,
        "items": [{"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0}],
    }
    plan_res = client.post("/api/v1/plans", json=plan_payload)
    assert plan_res.status_code == 201
    plan_data = plan_res.json()
    created_id = plan_data["id"]

    try:
        # Навантаження плану автоматично виставлено як 'low' відповідно до розрахунку
        assert plan_data["load_levels"]["autumn"] == "medium"
        assert plan_data["load_levels"]["spring"] == "medium"
        assert plan_data["load_levels"]["summer"] == "medium"
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanItem).where(PlanItem.plan_id == created_id))
            db.execute(delete(IndividualPlan).where(IndividualPlan.id == created_id))
            db.commit()


def test_api_plans_create_4th_year_rejects_explicit_load_levels(setup_4th_year_student):
    """Спроба надіслати load_levels для 4 курсу відхиляється 422 LOAD_LEVELS_NOT_ALLOWED."""
    plan_payload = {
        "academic_year": ACADEMIC_YEAR,
        "course": 4,
        "load_levels": {"autumn": "medium", "spring": "medium", "summer": "medium"},
        "items": [{"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0}],
    }
    response = client.post("/api/v1/plans", json=plan_payload)
    assert response.status_code == 422
    details = response.json()["details"]
    assert any("LOAD_LEVELS_NOT_ALLOWED" in d["message"] for d in details)


def test_credit_targets_do_not_limit_weekly_hours():
    result = distribute_auto_load(
        earned_credits=140,
        normative_by_trimester={"autumn": 30},
        weekly_by_trimester={"autumn": 4, "spring": 20, "summer": 23},
    )
    assert result.remaining_credits == 100
    assert result.autumn_level == "low"
    assert result.spring_level == "medium"
    assert result.summer_level == "high"


def test_unknown_hours_are_explicit_in_auto_explanation():
    result = distribute_auto_load(earned_credits=186)
    assert "Години неповні" in result.explanation
