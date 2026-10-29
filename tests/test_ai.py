"""Тести AI-генерації плану: POST/GET /plan-generations і моделі PlanGeneration (contract.md §3.7).

Використання ШІ: файл створено за допомогою Claude за ai.py і contract.md §3.7.
Перевірка: pytest, ruff check.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from src.api.common import get_current_student_id
from src.api.main import app
from src.api.onboarding import get_onboarded_student
from src.db import enums as db_enums
from src.db.base import utcnow
from src.db.models.ai import PlanGeneration, PlanGenerationNotice
from src.db.models.plans import IndividualPlan
from src.db.models.users import StudentProfile, User
from src.db.session import session_factory

URL = "/api/v1/plan-generations"
PAYLOAD = {
    "academic_year": 2027,
    "load_levels": {"autumn": "low", "spring": "medium", "summer": "high"},
    "direction_ids": [],
    "include_free_electives": True,
    "preferred_instructor_ids": [],
    "unwanted_instructor_ids": [],
    "wants_certificate": False,
    "certificate_program_id": None,
}
Status = db_enums.GenerationStatus


def add_generation(student_id, status=Status.SUCCEEDED, created_at=None, **fields):
    """Створює генерацію напряму в БД і повертає її id."""
    with session_factory()() as db:
        generation = PlanGeneration(
            student_id=student_id,
            academic_year=2027,
            status=status,
            created_at=created_at or utcnow(),
            **fields,
        )
        db.add(generation)
        db.commit()
        return generation.id


@pytest.fixture(autouse=True)
def clean_generations():
    def wipe():
        with session_factory()() as db:
            db.execute(delete(PlanGenerationNotice))
            db.execute(delete(PlanGeneration))
            db.commit()

    wipe()
    yield
    wipe()


@pytest.fixture
def student_id():
    with session_factory()() as db:
        found = db.scalar(select(StudentProfile.user_id).order_by(StudentProfile.user_id).limit(1))
    assert found is not None, "У seed немає профілю студента"
    return found


@pytest.fixture
def other_user_id(student_id):
    with session_factory()() as db:
        found = db.scalar(select(User.id).where(User.id != student_id).order_by(User.id).limit(1))
    if found is None:
        pytest.skip("У seed немає другого користувача")
    return found


@pytest.fixture
def plan_id():
    with session_factory()() as db:
        found = db.scalar(select(IndividualPlan.id).order_by(IndividualPlan.id).limit(1))
    if found is None:
        pytest.skip("У seed немає жодного плану")
    return found


@pytest.fixture
def client(student_id):
    """TestClient від імені студента із seed; перевизначення залежностей знімаються після тесту."""
    app.dependency_overrides[get_current_student_id] = lambda: student_id
    app.dependency_overrides[get_onboarded_student] = lambda: SimpleNamespace(user_id=student_id)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_current_student_id, None)
        app.dependency_overrides.pop(get_onboarded_student, None)


# --- POST /plan-generations ---


def test_start_generation_returns_202_and_pending_task(client, student_id):
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["plan_id"] is None
    assert body["notices"] == []
    assert body["finished_at"] is None
    assert response.headers["Location"] == f"{URL}/{body['id']}"

    with session_factory()() as db:
        saved = db.get(PlanGeneration, body["id"])
        assert saved.student_id == student_id
        assert saved.academic_year == 2027
        assert saved.status == Status.PENDING


def test_start_generation_conflict_when_one_is_active(client, student_id):
    add_generation(student_id, status=Status.PENDING)
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 409
    assert response.json()["code"] == "GENERATION_IN_PROGRESS"


def test_start_generation_rate_limited_after_20_per_day(client, student_id):
    for _ in range(20):
        add_generation(student_id, status=Status.SUCCEEDED, finished_at=utcnow())
    response = client.post(URL, json=PAYLOAD)
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"


def test_old_generations_do_not_count_towards_daily_limit(client, student_id):
    old = utcnow() - timedelta(hours=48)
    for _ in range(20):
        add_generation(student_id, status=Status.SUCCEEDED, created_at=old, finished_at=old)
    assert client.post(URL, json=PAYLOAD).status_code == 202


def test_other_students_generations_do_not_block(client, other_user_id):
    add_generation(other_user_id, status=Status.PENDING)
    assert client.post(URL, json=PAYLOAD).status_code == 202


def test_start_generation_invalid_body_returns_422(client):
    response = client.post(URL, json={"academic_year": "not-a-year"})
    assert response.status_code == 422


def test_start_generation_requires_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).post(URL, json=PAYLOAD).status_code == 401


# --- GET /plan-generations/{id} ---


def test_get_pending_generation(client, student_id):
    generation_id = add_generation(student_id, status=Status.PENDING)
    response = client.get(f"{URL}/{generation_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == generation_id
    assert body["status"] == "pending"
    assert body["error"] is None
    assert body["finished_at"] is None


def test_get_succeeded_generation_returns_plan_and_notices(client, student_id, plan_id):
    generation_id = add_generation(
        student_id,
        plan_id=plan_id,
        attempts=1,
        finished_at=utcnow(),
        notices=[
            PlanGenerationNotice(
                code="UNWANTED_INSTRUCTOR_UNAVOIDABLE",
                message="Дисципліну X викладає лише небажаний викладач",
            )
        ],
    )
    response = client.get(f"{URL}/{generation_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["plan_id"] == plan_id
    assert body["finished_at"] is not None
    assert len(body["notices"]) == 1
    assert body["notices"][0]["code"] == "UNWANTED_INSTRUCTOR_UNAVOIDABLE"
    assert body["notices"][0]["course_id"] is None


def test_get_failed_generation_returns_error(client, student_id):
    generation_id = add_generation(
        student_id,
        status=Status.FAILED,
        error_code="AI_UNAVAILABLE",
        error_message="AI-сервіс недоступний",
        finished_at=utcnow(),
    )
    response = client.get(f"{URL}/{generation_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "AI-сервіс недоступний" in str(body["error"])


def test_get_missing_generation_returns_404(client):
    response = client.get(f"{URL}/999999")
    assert response.status_code == 404
    assert response.json()["code"] == "GENERATION_NOT_FOUND"


def test_get_other_students_generation_returns_404(client, other_user_id):
    generation_id = add_generation(other_user_id)
    response = client.get(f"{URL}/{generation_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "GENERATION_NOT_FOUND"


def test_get_generation_rejects_non_positive_id(client):
    assert client.get(f"{URL}/0").status_code == 422


# --- Моделі і обмеження БД ---


def test_generation_defaults_to_pending_with_zero_attempts(student_id):
    with session_factory()() as db:
        generation = PlanGeneration(student_id=student_id, academic_year=2027)
        db.add(generation)
        db.commit()
        db.refresh(generation)
        assert generation.status == Status.PENDING
        assert generation.attempts == 0
        assert generation.created_at is not None
        assert generation.notices == []


def test_deleting_generation_deletes_its_notices(student_id):
    generation_id = add_generation(
        student_id,
        notices=[
            PlanGenerationNotice(code="A", message="перше"),
            PlanGenerationNotice(code="B", message="друге"),
        ],
    )
    with session_factory()() as db:
        db.delete(db.get(PlanGeneration, generation_id))
        db.commit()
        assert db.scalar(select(func.count()).select_from(PlanGenerationNotice)) == 0


def test_attempts_above_three_violates_check_constraint(student_id):
    with session_factory()() as db:
        db.add(PlanGeneration(student_id=student_id, academic_year=2027, attempts=4))
        with pytest.raises(IntegrityError):
            db.flush()


def test_only_one_pending_generation_per_student(student_id):
    add_generation(student_id, status=Status.PENDING)
    with session_factory()() as db:
        db.add(PlanGeneration(student_id=student_id, academic_year=2027))
        with pytest.raises(IntegrityError):
            db.flush()


def test_new_pending_generation_allowed_after_previous_finished(student_id):
    add_generation(student_id, status=Status.FAILED, finished_at=utcnow())
    add_generation(student_id, status=Status.PENDING)
    with session_factory()() as db:
        assert db.scalar(select(func.count()).select_from(PlanGeneration)) == 2
