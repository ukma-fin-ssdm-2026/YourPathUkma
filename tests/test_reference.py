"""Тести довідників: GET /api/v1/directions і GET /api/v1/instructors."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer test"}


def test_directions_require_token():
    assert client.get("/api/v1/directions").status_code == 401


def test_directions_list():
    response = client.get("/api/v1/directions", headers=AUTH)
    assert response.status_code == 200
    names = [d["name"] for d in response.json()["directions"]]
    assert "Data Science" in names


def test_instructors_search_by_q():
    response = client.get("/api/v1/instructors", params={"q": "петр"}, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert [i["full_name"] for i in body["instructors"]] == ["Петренко І. М."]
    assert body["pagination"]["total"] == 1


def test_instructors_q_too_short_is_422():
    response = client.get("/api/v1/instructors", params={"q": "п"}, headers=AUTH)
    assert response.status_code == 422
