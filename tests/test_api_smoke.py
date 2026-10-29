"""
Smoke-тести API для CI: перевіряють, що ключові кінцеві точки повертають очікувані статус-коди.

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: локальний запуск pytest,
виконання в GitHub Actions.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


def test_disciplines_requires_auth():
    app.dependency_overrides.clear()
    r = client.get("/api/v1/disciplines")
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHORIZED"


def test_plans_requires_auth():
    app.dependency_overrides.clear()
    assert client.get("/api/v1/plans").status_code == 401


def test_blank_token_rejected():
    app.dependency_overrides.clear()
    r = client.get("/api/v1/plans", headers={"Authorization": "Bearer  "})
    assert r.status_code == 401


def test_disciplines_list_ok():
    r = client.get("/api/v1/disciplines", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert "disciplines" in body and "pagination" in body


def test_unknown_plan_returns_404():
    assert client.get("/api/v1/plans/999999", headers=AUTH).status_code == 404


def test_health_ok():
    assert client.get("/health").status_code == 200


def test_openapi_has_all_endpoints():
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/v1/plans",
        "/api/v1/plans/{plan_id}",
        "/api/v1/disciplines",
        "/api/v1/disciplines/{discipline_id}",
    } <= set(paths)


def test_openapi_has_new_endpoints():
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/api/v1/config",
        "/api/v1/auth/microsoft",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/directions",
        "/api/v1/instructors",
        "/api/v1/plans/validate",
    } <= set(paths)
