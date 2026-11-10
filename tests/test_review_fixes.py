"""Регресійні тести до пунктів 1–3 і 5 рев'ю (подання плану, звірка сертифікатів, онбординг, експорт).

Пункт 4 (ліміт генерацій у UTC) лежить у tests/test_ai.py.
Тести змінюють seed-дані й повертають їх у вихідний стан у finally/фікстурах.
"""

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.common import get_current_student_id
from src.api.main import app
from src.db import enums as db_enums
from src.db.models import Course, IndividualPlan
from src.db.models.catalog import CertificateProgram, CertificateProgramCourse
from src.db.models.users import StudentProfile
from src.db.session import session_factory

STUDENT_ID = 42  # студент із seed.py, його авторизує autouse-фікстура з conftest.py


@pytest.fixture
def client():
    return TestClient(app)


@contextmanager
def profile_state(**fields):
    """Тимчасово змінює профіль студента 42 і повертає старі значення."""
    with session_factory()() as db:
        profile = db.get(StudentProfile, STUDENT_ID)
        old = {name: getattr(profile, name) for name in fields}
        for name, value in fields.items():
            setattr(profile, name, value)
        db.commit()
    try:
        yield
    finally:
        with session_factory()() as db:
            profile = db.get(StudentProfile, STUDENT_ID)
            for name, value in old.items():
                setattr(profile, name, value)
            db.commit()


def plan_body(course, course_year=2):
    return {
        "academic_year": 2027,
        "course": course_year,
        "load_levels": {"autumn": "medium", "spring": "medium", "summer": "medium"},
        "items": [
            {
                "course_id": course["id"],
                "title": course["title"],
                "trimester": course["trimester"],
                "credits": course["credits"],
                "is_free_elective": False,
            }
        ],
    }


@pytest.fixture
def elective():
    """Опублікована вибіркова дисципліна з каталогу seed."""
    with session_factory()() as db:
        course = db.scalar(
            select(Course)
            .where(
                Course.kind == db_enums.CourseKind.ELECTIVE,
                Course.publication_status == db_enums.PublicationStatus.PUBLISHED,
            )
            .order_by(Course.id)
            .limit(1)
        )
        if course is None:
            pytest.skip("У seed немає опублікованої вибіркової дисципліни")
        return {
            "id": course.id,
            "title": course.title,
            "trimester": course.trimester.number,
            "credits": course.credits,
        }


@pytest.fixture
def draft_plan(client, elective):
    """Створює чернетку через API й видаляє її після тесту."""
    with session_factory()() as db:
        course_year = db.get(StudentProfile, STUDENT_ID).course_year
    response = client.post("/api/v1/plans", json=plan_body(elective, course_year=max(course_year, 2)))
    if response.status_code != 201:
        pytest.skip(f"Не вдалося створити чернетку із seed-даними: {response.status_code} {response.text}")
    plan_id = response.json()["id"]
    yield plan_id
    with session_factory()() as db:
        plan = db.get(IndividualPlan, plan_id)
        if plan is not None:
            db.delete(plan)
            db.commit()


@contextmanager
def course_changed(course_id, **fields):
    with session_factory()() as db:
        course = db.get(Course, course_id)
        old = {name: getattr(course, name) for name in fields}
        for name, value in fields.items():
            setattr(course, name, value)
        db.commit()
    try:
        yield
    finally:
        with session_factory()() as db:
            course = db.get(Course, course_id)
            for name, value in old.items():
                setattr(course, name, value)
            db.commit()


# --- 1. Подання плану повторно перевіряє каталог ---


def test_submit_rejects_course_archived_after_draft_was_created(client, draft_plan, elective):
    with course_changed(elective["id"], publication_status=db_enums.PublicationStatus.ARCHIVED):
        response = client.post(f"/api/v1/plans/{draft_plan}/submit")
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    with session_factory()() as db:
        assert db.get(IndividualPlan, draft_plan).status == db_enums.PlanStatus.DRAFT


def test_submit_rejects_when_catalog_credits_changed(client, draft_plan, elective):
    with course_changed(elective["id"], credits=elective["credits"] + 1):
        response = client.post(f"/api/v1/plans/{draft_plan}/submit")
    assert response.status_code == 409
    assert response.json()["code"] == "PLAN_CATALOG_CHANGED"
    with session_factory()() as db:
        assert db.get(IndividualPlan, draft_plan).status == db_enums.PlanStatus.DRAFT


# --- 2. Скасування звірки не робить програму доступною ---


@pytest.fixture
def program_with_entries():
    """Тимчасова програма з двома звіреними записами (у seed сертифікатних програм немає)."""
    with session_factory()() as db:
        program = CertificateProgram(
            title="Тестова програма (review fixes)",
            source_url="",
            direction_ids=[],
            availability=db_enums.CertificateAvailability.AVAILABLE,
            courses=[
                CertificateProgramCourse(raw_title="Функціональне програмування", course_id=101),
                CertificateProgramCourse(raw_title="Основи кібербезпеки", course_id=102),
            ],
        )
        db.add(program)
        db.commit()
        data = {
            "program_id": program.id,
            "entry_ids": [entry.id for entry in program.courses],
            "course_ids": [101, 102],
        }
    yield data
    with session_factory()() as db:
        program = db.get(CertificateProgram, data["program_id"])
        if program is not None:
            db.delete(program)  # записи видаляються каскадом
            db.commit()


def put_match(client, data, entry_id, course_id):
    return client.put(
        f"/api/v1/admin/certificate-programs/{data['program_id']}/courses/{entry_id}",
        json={"course_id": course_id},
    )


def availability(program_id):
    with session_factory()() as db:
        return db.get(CertificateProgram, program_id).availability


def test_unmatching_entry_makes_program_unavailable(admin_client, program_with_entries):
    data = program_with_entries
    assert put_match(admin_client, data, data["entry_ids"][0], None).status_code == 200
    assert availability(data["program_id"]) == db_enums.CertificateAvailability.UNAVAILABLE


def test_program_becomes_available_only_when_all_entries_matched(admin_client, program_with_entries):
    data = program_with_entries
    first, second = data["entry_ids"]
    put_match(admin_client, data, first, None)
    put_match(admin_client, data, second, None)
    # Звірено один із двох: програма все ще недоступна
    put_match(admin_client, data, first, data["course_ids"][0])
    assert availability(data["program_id"]) == db_enums.CertificateAvailability.UNAVAILABLE
    # Звірено все: програма доступна
    put_match(admin_client, data, second, data["course_ids"][1])
    assert availability(data["program_id"]) == db_enums.CertificateAvailability.AVAILABLE


# --- 3. Плани вимагають онбордингу та правильного курсу ---


def test_create_plan_requires_onboarding(client, elective):
    with profile_state(specialty=""):
        response = client.post("/api/v1/plans", json=plan_body(elective))
    assert response.status_code == 409
    assert response.json()["code"] == "ONBOARDING_REQUIRED"


def test_create_plan_for_deleted_user_is_409_not_500(client, elective):
    app.dependency_overrides[get_current_student_id] = lambda: 999_999
    try:
        response = client.post("/api/v1/plans", json=plan_body(elective))
    finally:
        app.dependency_overrides[get_current_student_id] = lambda: STUDENT_ID
    assert response.status_code == 409
    assert response.json()["code"] == "ONBOARDING_REQUIRED"


def test_create_plan_rejects_course_above_student_course(client, elective):
    with profile_state(course_year=2):
        response = client.post("/api/v1/plans", json=plan_body(elective, course_year=3))
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_update_and_submit_require_onboarding(client, elective):
    with profile_state(specialty=""):
        assert client.put("/api/v1/plans/1", json=plan_body(elective)).status_code == 409
        assert client.post("/api/v1/plans/1/submit").status_code == 409


# --- 5. Експорт не віддає заглушку ---


def test_export_returns_501_instead_of_fake_pdf(client, draft_plan):
    response = client.get(f"/api/v1/plans/{draft_plan}/export")
    assert response.status_code == 501
    assert response.headers["content-type"].startswith("application/json")
    assert b"%PDF" not in response.content


def test_export_unknown_format_still_422(client, draft_plan):
    assert client.get(f"/api/v1/plans/{draft_plan}/export?format=docx").status_code == 422


def test_config_reports_plan_export_disabled(client):
    assert client.get("/api/v1/config").json()["features"]["plan_export"] is False
