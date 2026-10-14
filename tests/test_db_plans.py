"""
Тести планів і каталогу, що працюють з БД: збереження між запитами, звірка з каталогом, права доступу.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}

FP = {"course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0}
PRODUCT = {"course_id": 205, "title": "Управління цифровим продуктом", "trimester": 2, "credits": 3.0}
SECURITY = {"course_id": 102, "title": "Основи кібербезпеки", "trimester": 2, "credits": 4.0}


def _create(items, **extra):
    body = {"academic_year": 2027, "course": 3, "items": items, **extra}
    return client.post("/api/v1/plans", json=body, headers=AUTH)


def test_create_plan_is_persisted():
    response = _create([FP, {**PRODUCT, "is_free_elective": True}], load_levels={"autumn": "low"})
    assert response.status_code == 201
    plan = response.json()
    assert response.headers["location"] == f"/api/v1/plans/{plan['id']}"
    assert plan["status"] == "draft"
    assert plan["total_credits"] == 8.0
    assert plan["free_elective_credits"] == 3.0
    assert plan["load_levels"] == {"autumn": "low", "spring": "medium", "summer": "medium"}

    stored = client.get(f"/api/v1/plans/{plan['id']}", headers=AUTH).json()
    assert stored == plan

    listed = client.get("/api/v1/plans", params={"academic_year": 2027, "status": "draft"}, headers=AUTH).json()
    assert plan["id"] in [p["id"] for p in listed["plans"]]


def test_update_replaces_items_and_recalculates_credits():
    plan_id = _create([FP]).json()["id"]
    body = {"academic_year": 2027, "course": 3, "items": [FP, SECURITY]}
    response = client.put(f"/api/v1/plans/{plan_id}", json=body, headers=AUTH)
    assert response.status_code == 200
    assert [i["course_id"] for i in response.json()["items"]] == [101, 102]
    assert client.get(f"/api/v1/plans/{plan_id}", headers=AUTH).json()["total_credits"] == 9.0


def test_delete_draft_removes_plan():
    plan_id = _create([FP]).json()["id"]
    assert client.delete(f"/api/v1/plans/{plan_id}", headers=AUTH).status_code == 204
    assert client.get(f"/api/v1/plans/{plan_id}", headers=AUTH).status_code == 404


def test_submitted_plan_is_read_only():
    body = {"academic_year": 2026, "course": 2, "items": [FP]}
    put = client.put("/api/v1/plans/2", json=body, headers=AUTH)
    assert put.status_code == 409 and put.json()["code"] == "PLAN_NOT_EDITABLE"
    delete = client.delete("/api/v1/plans/2", headers=AUTH)
    assert delete.status_code == 409 and delete.json()["code"] == "PLAN_NOT_DELETABLE"


def test_foreign_plan_is_forbidden():
    assert client.get("/api/v1/plans/3", headers=AUTH).json()["code"] == "PLAN_FORBIDDEN"


def test_plans_listed_newest_first():
    first = _create([FP]).json()["id"]
    second = _create([FP]).json()["id"]
    ids = [p["id"] for p in client.get("/api/v1/plans", params={"limit": 100}, headers=AUTH).json()["plans"]]
    assert ids.index(second) < ids.index(first)


def test_unknown_course_is_rejected():
    response = _create([{**FP, "course_id": 999}])
    assert response.status_code == 422
    detail = response.json()["details"][0]
    assert detail["field"] == "items.0.course_id"
    assert detail["message"].startswith("COURSE_NOT_FOUND")


def test_normative_course_is_rejected():
    normative = {"course_id": 301, "title": "Алгоритми та структури даних", "trimester": 1, "credits": 6.0}
    response = _create([FP, normative])
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "items.1.course_id"
    assert response.json()["details"][0]["message"].startswith("NORMATIVE_NOT_ALLOWED")


def test_credits_mismatch_is_rejected():
    response = _create([{**FP, "credits": 6.0}])
    assert response.status_code == 422
    assert response.json()["details"][0]["message"].startswith("COURSE_DATA_MISMATCH")


def test_disciplines_filter_by_cyrillic_instructor_and_direction_case():
    response = client.get(
        "/api/v1/disciplines", params={"instructor": "ПЕТР", "direction": "data science"}, headers=AUTH
    )
    body = response.json()
    assert [d["id"] for d in body["disciplines"]] == [101]
    assert body["disciplines"][0]["instructor"] == "Петренко І. М."
    assert body["pagination"]["total"] == 1


def test_disciplines_pagination():
    body = client.get("/api/v1/disciplines", params={"limit": 2, "offset": 1}, headers=AUTH).json()
    assert [d["id"] for d in body["disciplines"]] == [102, 205]
    assert body["pagination"] == {"limit": 2, "offset": 1, "total": 4, "has_more": True}


def test_discipline_by_id():
    body = client.get("/api/v1/disciplines/301", headers=AUTH).json()
    assert body["discipline_type"] == "normative"
    assert body["trimester"] == 1
    assert client.get("/api/v1/disciplines/999", headers=AUTH).json()["code"] == "DISCIPLINE_NOT_FOUND"
