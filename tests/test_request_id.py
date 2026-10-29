"""Тести request_id у помилках, заголовка X-Request-ID і обмеження MCP_DEV_MODE.

Використання ШІ: файл створено за допомогою Claude (Claude Code) за зауваженням зовнішнього рев'ю.
Перевірка: pytest, ruff check.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.common import assert_safe_environment
from src.api.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_error_body_contains_request_id_matching_header():
    app.dependency_overrides.clear()
    response = client.get("/api/v1/plans")  # без токена -> 401
    assert response.status_code == 401
    body = response.json()
    assert body["request_id"]
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_validation_error_contains_request_id():
    response = client.get("/api/v1/plans", params={"limit": 0}, headers={"Authorization": "Bearer t"})
    assert response.status_code == 422
    assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_client_request_id_is_echoed():
    response = client.get("/api/v1/plans", headers={"X-Request-ID": "my-trace-123"})
    assert response.headers["X-Request-ID"] == "my-trace-123"


def test_unsafe_client_request_id_is_replaced():
    response = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert response.headers["X-Request-ID"].startswith("req_")


def test_success_response_has_request_id_header():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Request-ID"].startswith("req_")


def test_unhandled_error_has_request_id():
    def boom():
        raise RuntimeError("boom")

    app.add_api_route("/__boom", boom)
    try:
        response = client.get("/__boom")
    finally:
        app.router.routes.pop()
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "boom" not in response.text


def test_dev_mode_without_token_allowed_outside_production(monkeypatch):
    monkeypatch.setenv("MCP_DEV_MODE", "1")
    monkeypatch.delenv("APP_ENV", raising=False)
    assert client.get("/api/v1/plans").status_code == 200


def test_dev_mode_ignored_in_production(monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setenv("MCP_DEV_MODE", "1")
    monkeypatch.setenv("APP_ENV", "production")
    assert client.get("/api/v1/plans").status_code == 401


def test_startup_refused_when_dev_mode_in_production(monkeypatch):
    monkeypatch.setenv("MCP_DEV_MODE", "1")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        assert_safe_environment()
