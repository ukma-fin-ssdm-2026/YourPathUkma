"""Тести POST /api/v1/plans/validate і регресія POST /api/v1/plans після винесення правил."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


def _plan(items):
    return {"academic_year": 2026, "course": 2, "items": items}


def _item(course_id, credits, trimester=1, free=False):
    return {
        "course_id": course_id,
        "title": f"Дисципліна {course_id}",
        "trimester": trimester,
        "credits": credits,
        "is_free_elective": free,
    }


def test_validate_requires_token():
    app.dependency_overrides.clear()
    response = client.post("/api/v1/plans/validate", json=_plan([_item(101, 5.0)]))
    assert response.status_code == 401


def test_validate_valid_plan():
    body = _plan([_item(101, 5.0, trimester=1), _item(205, 3.0, trimester=2, free=True)])
    response = client.post("/api/v1/plans/validate", json=body, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["summary"]["total_credits"] == 8.0
    assert data["summary"]["free_elective_remaining"] == 22.0
    assert data["summary"]["credits_by_trimester"] == {"1": 5.0, "2": 3.0, "3": 0.0}


def test_validate_returns_200_with_errors_for_business_rule_violation():
    body = _plan([_item(101, 5.0), _item(205, 28.0, trimester=2, free=True)])
    response = client.post("/api/v1/plans/validate", json=body, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert [e["code"] for e in data["errors"]] == ["FREE_ELECTIVE_LIMIT_EXCEEDED"]


def test_validate_reports_duplicates_and_only_free_electives():
    body = _plan([_item(205, 3.0, free=True), _item(205, 3.0, free=True)])
    response = client.post("/api/v1/plans/validate", json=body, headers=AUTH)
    codes = [e["code"] for e in response.json()["errors"]]
    assert codes == ["DUPLICATE_COURSE", "ONLY_FREE_ELECTIVES"]


def test_validate_schema_violation_is_422():
    body = _plan([_item(101, 5.0, trimester=5)])
    response = client.post("/api/v1/plans/validate", json=body, headers=AUTH)
    assert response.status_code == 422


def test_create_plan_still_rejects_business_rule_violation(monkeypatch):
    """Регресія: рефакторинг правил не змінив поведінку POST /plans (422 + текст про ліміт).

    Звірка з каталогом вимагає реальних кредитів (у демо-каталозі вільного вибору лише 3 кредити),
    тому ліміт вільного вибору тимчасово знижено до 2.
    """
    monkeypatch.setattr("src.services.plan_rules.FREE_ELECTIVE_LIMIT", 2.0)
    body = _plan([_item(101, 5.0), _item(205, 3.0, trimester=2, free=True)])
    response = client.post("/api/v1/plans", json=body, headers=AUTH)
    assert response.status_code == 422
    messages = [detail["message"] for detail in response.json()["details"]]
    assert any(m.startswith("FREE_ELECTIVE_LIMIT_EXCEEDED") and "3 > 2" in m for m in messages)
