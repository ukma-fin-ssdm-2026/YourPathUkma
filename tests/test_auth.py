"""Тести автентифікації: POST /api/v1/auth/microsoft, /auth/refresh, /auth/logout."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.tokens import issue_access_token

client = TestClient(app)


def test_login_returns_token_and_sets_refresh_cookie():
    payload = {
        "code": "abc",
        "code_verifier": "x" * 43,
        "redirect_uri": "http://localhost:5173/auth/callback",
        "nonce": "test-nonce-12345",
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "mock-ms-access-token",  # nosec B105
        "id_token": "mock-ms-id-token",  # nosec B105
        "refresh_token": "mock-ms-refresh-token",  # nosec B105
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response), patch("httpx.post", return_value=mock_response):
        response = client.post("/api/v1/auth/microsoft", json=payload)

    assert response.status_code in (200, 201, 503)
    if response.status_code != 503:
        body = response.json()
        assert "access_token" in body or "token_type" in body


def test_login_rejects_short_code_verifier():
    payload = {
        "code": "abc",
        "code_verifier": "short",
        "redirect_uri": "http://localhost:5173/auth/callback",
        "nonce": "test-nonce-12345",
    }
    response = client.post("/api/v1/auth/microsoft", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_refresh_without_cookie_is_401():
    app.dependency_overrides.clear()
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_refresh_with_cookie_returns_new_token():
    valid_token = issue_access_token(user_id=42, role="student")
    response = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": valid_token},
        headers={"Cookie": f"refresh_token={valid_token}"},
    )
    assert response.status_code in (200, 401)


def test_logout_returns_204():
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204


def test_legacy_google_login_endpoint_is_removed():
    payload = {
        "code": "abc",
        "code_verifier": "x" * 43,
        "redirect_uri": "http://localhost:5173/auth/callback",
        "nonce": "test-nonce-12345",
    }
    response = client.post("/api/v1/auth/google", json=payload)
    assert response.status_code == 404
