"""Тести системних кінцевих точок: GET /api/v1/config."""

import pytest
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


@pytest.mark.parametrize(
    "configured, expected",
    [
        (None, None),
        ("   ", None),
        ("https://example.ukma.edu.ua/reviews", None),
        ("http://reviews.ukma.edu.ua/reviews", None),
        ("https://", None),
        ("https://user@reviews.ukma.edu.ua/reviews", None),
        (" https://reviews.ukma.edu.ua/reviews ", "https://reviews.ukma.edu.ua/reviews"),
    ],
)
def test_config_reviews_url(monkeypatch, configured, expected):
    if configured is None:
        monkeypatch.delenv("REVIEWS_URL", raising=False)
    else:
        monkeypatch.setenv("REVIEWS_URL", configured)
    assert client.get("/api/v1/config").json()["reviews_url"] == expected
