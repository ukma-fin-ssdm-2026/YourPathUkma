"""Тести профілю, онбордингу та академічної історії."""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}

def test_get_me_returns_profile():
    response = client.get("/api/v1/me", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert "student" in data
    assert "credits" in data["student"]

def test_onboarding_already_completed_returns_409():
    # Демо-студент (42) з seed.py вже має заповнений курс і спеціальність
    payload = {"course_year": 3, "specialty": "Комп'ютерні науки"}
    response = client.post("/api/v1/me/onboarding", json=payload, headers=AUTH)
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_ONBOARDED"

def test_get_academic_history():
    response = client.get("/api/v1/me/academic-history", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert "years" in data
    assert isinstance(data["years"], list)

def test_add_academic_history_record():
    payload = {
        "records": [
            {
                "academic_year": 2025,
                "course_year": 2,
                "course_id": 101, 
                "trimester": 1,
                "category": "professional"
            }
        ]
    }
    response = client.post("/api/v1/me/academic-history", json=payload, headers=AUTH)
    # Якщо дисципліна вже є в історії, повернеться 422 DUPLICATE_COURSE
    assert response.status_code in (201, 422)

def test_delete_foreign_or_unknown_academic_record_returns_404():
    response = client.delete("/api/v1/me/academic-history/99999", headers=AUTH)
    assert response.status_code == 404