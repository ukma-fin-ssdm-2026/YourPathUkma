"""Використання ШІ: Codex додав API-регресії #291; перевірка: PostgreSQL pytest."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_weekly_workload import course, document

from src.api.main import app
from src.db.models.catalog import Course
from src.db.models.users import StudentProfile
from src.db.session import get_db, session_factory


@pytest.fixture
def api():
    engine = session_factory()().get_bind()
    with engine.connect() as connection:
        tx = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            db.get(StudentProfile, 42).course_year = 3
            app.dependency_overrides[get_db] = lambda: db
            yield TestClient(app), db
            app.dependency_overrides.pop(get_db, None)
        tx.rollback()


def payload(c):
    return {
        "academic_year": 2029,
        "course": 3,
        "load_levels": {"autumn": "low", "spring": "medium", "summer": "medium"},
        "items": [
            {
                "course_id": c.id,
                "title": c.title,
                "trimester": 1,
                "credits": float(c.credits),
                "is_free_elective": False,
            }
        ],
    }


@pytest.mark.parametrize("annual", [56.9, 57, 60, 65])
def test_validate_annual_api(api, annual):
    client, db = api
    c = course(db, "api-annual", hours=20)
    n = course(db, "api-norm", hours=0)
    document(db, [(n, annual - 5)])
    response = client.post("/api/v1/plans/validate", json=payload(c))
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["year_total_credits"] == annual
    assert data["summary"]["workload_by_trimester"]["1"]["level"] == "medium"
    assert ("YEAR_CREDITS_BELOW_MIN" in {v["code"] for v in data["warnings"]}) == (annual < 57)


@pytest.mark.parametrize("hours,submit_code", [(25, 200), (25.1, 422), (None, 200)])
def test_validate_draft_submit_share_workload(api, hours, submit_code):
    client, db = api
    c = course(db, "api-submit", hours=hours)
    c.directions = list(db.get(Course, 101).directions)
    document(db)
    db.flush()
    body = payload(c)
    validation = client.post("/api/v1/plans/validate", json=body).json()
    assert validation["valid"] == (hours == 25)
    if hours is None:
        assert "WORKLOAD_DATA_INCOMPLETE" in {v["code"] for v in validation["warnings"]}
    draft = client.post("/api/v1/plans", json=body)
    assert draft.status_code == 201, draft.text
    response = client.post(f'/api/v1/plans/{draft.json()["id"]}/submit')
    assert response.status_code == submit_code, response.text
    if hours == 25.1:
        assert "WEEKLY_LOAD_EXCEEDED" in response.text


def test_missing_document_is_not_valid(api):
    client, db = api
    c = course(db, "no-document", hours=1)
    data = client.post("/api/v1/plans/validate", json=payload(c)).json()
    assert not data["valid"]
    assert not data["summary"]["workload_complete"]


@pytest.mark.parametrize("hours", [26, None, 24])
def test_ai_uses_same_hour_rules(api, hours):
    from types import SimpleNamespace

    from src.ai.adapter import _validate_and_save
    from src.ai.response_parser import LLMResponse
    from src.db import enums
    from src.db.models.ai import PlanGeneration

    client, db = api
    c = course(db, "ai-hours", hours=hours)
    document(db)
    gen = PlanGeneration(student_id=42, academic_year=2029)
    db.add(gen)
    db.flush()
    response = LLMResponse.model_validate(
        {
            "plan": [{"course_id": c.id, "trimester": "autumn", "category": "professional", "explanation": "test"}],
            "alternatives": [],
            "notices": [],
        }
    )
    ctx = SimpleNamespace(
        normative_course_ids=[], excluded_course_ids=[], load_levels={"autumn": "medium"}, student_course_year=4
    )
    if hours == 26:
        with pytest.raises(ValueError, match="25"):
            _validate_and_save(db, gen, response, ctx, 1)
        assert gen.status == enums.GenerationStatus.PENDING
    else:
        plan = _validate_and_save(db, gen, response, ctx, 1)
        if hours is None:
            assert "WORKLOAD_DATA_INCOMPLETE" in {n.code for n in gen.notices}
        else:
            assert plan.load_autumn == enums.LoadLevel.HIGH


def test_moderation_preserves_hours_for_all_semesters(api):
    from types import SimpleNamespace

    from src.api.routes.admin.sync import CoursePayload, _apply_change
    from src.db import enums

    _, db = api
    semesters = [
        {"number": 5, "season": "Осінь", "credits": 3, "weekly_hours": 2.5},
        {"number": 6, "season": "Весна", "credits": 4, "weekly_hours": 4},
    ]
    data = CoursePayload(
        saz_code="moderated-hours",
        title="Години після модерації",
        credits=3,
        trimester=1,
        recommended_year=3,
        kind=enums.CourseKind.ELECTIVE,
        semesters=semesters,
    )
    pending = SimpleNamespace(change_type=enums.ModerationChangeType.ADD, sync_job_id=None, course_id=None)
    _apply_change(db, pending, None, data)
    c = db.get(Course, pending.course_id)
    assert c.semesters == semesters
    _apply_change(
        db,
        SimpleNamespace(change_type=enums.ModerationChangeType.UPDATE, sync_job_id=None),
        c,
        CoursePayload(semesters=[{**semesters[0], "weekly_hours": 0}]),
    )
    db.flush()
    db.expire(c)
    assert c.semesters[0]["weekly_hours"] == 0
