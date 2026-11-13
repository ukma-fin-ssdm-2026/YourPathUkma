"""Тести надійності: readiness-ендпоінт з ін'єкцією збою залежностей."""

import time

from fastapi.testclient import TestClient

from src.api import health
from src.api.main import app

client = TestClient(app)


def _ok():
    return None


def _db_down():
    raise ConnectionError("connection refused: db.internal:5432")


def _slow():
    time.sleep(0.5)


def test_ready_healthy_when_all_dependencies_up(monkeypatch):
    monkeypatch.setitem(health.DEPENDENCIES, "database", _ok)
    monkeypatch.setitem(health.DEPENDENCIES, "microsoft", _ok)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ready_unhealthy_when_database_down(monkeypatch):
    """Ін'єкція збою: БД «падає» -> 503, статус unhealthy, внутрішні деталі не витікають."""
    monkeypatch.setitem(health.DEPENDENCIES, "database", _db_down)
    monkeypatch.setitem(health.DEPENDENCIES, "microsoft", _ok)

    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["checks"]["database"]["status"] == "down"
    assert body["checks"]["microsoft"]["status"] == "up"
    assert "5432" not in response.text and "refused" not in response.text


def test_ready_unhealthy_on_timeout(monkeypatch):
    """Залежність, що зависла, не підвішує ендпоінт: після тайм-ауту статус «down»."""
    monkeypatch.setattr(health, "CHECK_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setitem(health.DEPENDENCIES, "database", _ok)
    monkeypatch.setitem(health.DEPENDENCIES, "microsoft", _slow)

    started = time.monotonic()
    response = client.get("/health/ready")

    assert time.monotonic() - started < 0.4
    assert response.status_code == 503
    assert response.json()["checks"]["microsoft"]["status"] == "down"


def test_ready_not_configured_microsoft_is_not_failure(monkeypatch):
    monkeypatch.setitem(health.DEPENDENCIES, "database", _ok)
    monkeypatch.setitem(health.DEPENDENCIES, "microsoft", lambda: health.NOT_CONFIGURED)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["microsoft"]["status"] == "not_configured"


def test_ready_real_database_check_passes(monkeypatch):
    """Справжня перевірка БД на тестовій базі (Microsoft підмінено, щоб тест не ходив у мережу)."""
    monkeypatch.setitem(health.DEPENDENCIES, "microsoft", _ok)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"]["status"] == "up"
