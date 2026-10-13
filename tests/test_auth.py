"""Тести автентифікації: POST /api/v1/auth/google, /auth/refresh, /auth/logout (заглушка)."""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_login_returns_token_and_sets_refresh_cookie():
    payload = {
        "code": "abc",
        "code_verifier": "x" * 43,
        "redirect_uri": "http://localhost:5173/auth/callback",
    }
    response = client.post("/api/v1/auth/google", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["user"]["role"] == "student"
    set_cookie = response.headers["set-cookie"].lower()
    assert "refresh_token=" in set_cookie
    assert "httponly" in set_cookie


def test_login_rejects_short_code_verifier():
    payload = {
        "code": "abc",
        "code_verifier": "short",
        "redirect_uri": "http://localhost:5173/auth/callback",
    }
    response = client.post("/api/v1/auth/google", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_refresh_without_cookie_is_401():
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_refresh_with_cookie_returns_new_token():
    # Cookie з прапорцем Secure не надсилається клієнтом по http, тому передаємо заголовок вручну
    response = client.post("/api/v1/auth/refresh", headers={"Cookie": "refresh_token=abc"})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_logout_returns_204():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
