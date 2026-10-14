"""Тести системних кінцевих точок: GET /api/v1/config."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_config_is_public_and_has_limits():
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    body = response.json()
    assert body["limits"]["total_credits"] == 240
    assert body["limits"]["free_choice_credits"] == 25
    assert body["features"]["saz_sync"] is False
    assert response.headers["cache-control"] == "max-age=300"
