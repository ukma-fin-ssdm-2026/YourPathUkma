"""Тести захисту адміністративної панелі (SEC-001)."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}  # Заглушка видає роль 'student'


def test_admin_users_forbidden_for_student():
    response = client.get("/api/v1/admin/users", headers=AUTH)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN_ROLE"


def test_admin_sync_jobs_forbidden_for_student():
    response = client.get("/api/v1/admin/sync-jobs", headers=AUTH)
    assert response.status_code == 403


def test_admin_directions_forbidden_for_student():
    response = client.post("/api/v1/admin/directions", json={"name": "Test"}, headers=AUTH)
    assert response.status_code == 403


def test_admin_audit_log_forbidden_for_student():
    response = client.get("/api/v1/admin/audit-log", headers=AUTH)
    assert response.status_code == 403
