"""Тести збереження побажань (Preferences)."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}

def test_get_preferences_not_found():
    response = client.get("/api/v1/preferences/2030", headers=AUTH)
    assert response.status_code == 404
    assert response.json()["code"] == "PREFERENCES_NOT_FOUND"

def test_put_preferences_creates_or_updates():
    payload = {
        "academic_year": 2027,
        "load_levels": {"autumn": "low", "spring": "medium", "summer": "high"},
        "direction_ids": [],
        "include_free_electives": True,
        "preferred_instructor_ids": [],
        "unwanted_instructor_ids": [],
        "wants_certificate": False,
        "certificate_program_id": None
    }
    response = client.put("/api/v1/preferences/2027", json=payload, headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["academic_year"] == 2027
    assert data["load_levels"]["autumn"] == "low"

    # Перевіряємо, що GET тепер повертає ці побажання
    get_response = client.get("/api/v1/preferences/2027", headers=AUTH)
    assert get_response.status_code == 200
