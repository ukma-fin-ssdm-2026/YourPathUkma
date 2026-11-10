"""Регресійні перевірки issue #217: стан сервісу, конфігурація, помилки та MCP.

Використання ШІ: тести створено Codex; перевірка: pytest, Ruff і Bandit.
"""

import asyncio
import importlib.util
import logging
from unittest.mock import Mock

import httpx
import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from src.api import microsoft
from src.api.common import ApiError, RequestIdMiddleware, register_error_handlers
from src.api.main import app
from src.api.tokens import get_auth_settings, issue_access_token
from src.db.config import ROOT_DIR


@pytest.fixture
def fresh_auth_settings():
    get_auth_settings.cache_clear()
    yield
    get_auth_settings.cache_clear()


def test_health_returns_503_when_database_is_unavailable(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'missing.sqlite'}")
    with caplog.at_level(logging.ERROR, logger="yourpath.api"):
        response = TestClient(app).get("/health")
    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "DATABASE_UNAVAILABLE" in caplog.text


def test_config_uses_microsoft_client_id(monkeypatch, fresh_auth_settings):
    monkeypatch.setenv("MS_CLIENT_ID", "real-microsoft-client")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "obsolete-client")
    response = TestClient(app).get("/api/v1/config")
    assert response.status_code == 200
    assert response.json()["google_client_id"] == "real-microsoft-client"


@pytest.mark.parametrize("environment, status", [("development", 200), ("production", 503)])
def test_config_without_client_id_has_no_fake_default(monkeypatch, fresh_auth_settings, environment, status):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("MS_CLIENT_ID", "")
    response = TestClient(app).get("/api/v1/config")
    assert response.status_code == status
    if status == 200:
        assert response.json()["google_client_id"] == ""
    else:
        assert response.json()["code"] == "AUTH_NOT_CONFIGURED"


@pytest.fixture
def error_app():
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["https://frontend.example"],
        allow_credentials=True,
        expose_headers=["X-Request-ID"],
    )
    register_error_handlers(application)

    @application.get("/error/{kind}")
    def error(kind: str):
        if kind == "api":
            raise ApiError(503, "DEPENDENCY_UNAVAILABLE", "Try later")
        if kind == "http":
            raise HTTPException(502, "Bad gateway")
        raise RuntimeError("private exception details")

    return application


@pytest.mark.parametrize("kind, status", [("api", 503), ("http", 502), ("unhandled", 500)])
def test_server_errors_are_logged_and_readable_with_cors(error_app, caplog, kind, status):
    with caplog.at_level(logging.ERROR, logger="yourpath.api"):
        response = TestClient(error_app, raise_server_exceptions=False).get(
            f"/error/{kind}", headers={"Origin": "https://frontend.example", "X-Request-ID": "issue-217"}
        )
    assert response.status_code == status
    assert response.headers["Access-Control-Allow-Origin"] == "https://frontend.example"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "X-Request-ID" in response.headers["Access-Control-Expose-Headers"]
    assert response.json()["request_id"] == response.headers["X-Request-ID"] == "issue-217"
    assert any(record.levelno >= logging.ERROR and "issue-217" in record.message for record in caplog.records)
    assert "private exception details" not in response.text


@pytest.mark.parametrize("origin", [None, "https://untrusted.example"])
def test_unhandled_error_does_not_allow_untrusted_origin(error_app, origin):
    headers = {"Origin": origin} if origin else {}
    response = TestClient(error_app, raise_server_exceptions=False).get("/error/unhandled", headers=headers)
    assert response.status_code == 500
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.parametrize(
    "exception, status, code",
    [
        (jwt.PyJWKClientConnectionError("offline"), 503, "AUTH_PROVIDER_UNAVAILABLE"),
        (jwt.InvalidTokenError("invalid"), 401, "INVALID_ID_TOKEN"),
    ],
)
def test_jwks_outage_is_distinct_from_invalid_token(monkeypatch, exception, status, code):
    client = Mock()
    client.get_signing_key_from_jwt.side_effect = exception
    monkeypatch.setattr(microsoft, "_jwks_client", lambda tenant: client)
    with pytest.raises(ApiError) as error:
        microsoft._verify_id_token("test-token", "nonce")
    assert (error.value.status_code, error.value.code) == (status, code)


@pytest.fixture
def mcp_server():
    spec = importlib.util.spec_from_file_location("yourpath_mcp_server", ROOT_DIR / "mcp" / "mcp_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("token", ["", "invalid-token"])
def test_mcp_refuses_missing_or_invalid_token(mcp_server, monkeypatch, token):
    monkeypatch.setenv("MCP_API_TOKEN", token)
    with pytest.raises(RuntimeError, match="MCP_API_TOKEN"):
        mcp_server.api_client_kwargs()


def test_mcp_client_authenticates_without_bypassing_api(mcp_server, monkeypatch):
    app.dependency_overrides.clear()
    monkeypatch.setenv("MCP_API_TOKEN", issue_access_token(42, "student"))

    async def call_api():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), **mcp_server.api_client_kwargs()
        ) as client:
            response = await client.get("/api/v1/plans")
            forbidden = await client.get("/api/v1/admin/users")
            return response, forbidden

    response, forbidden = asyncio.run(call_api())
    assert response.status_code == 200
    assert forbidden.status_code == 403


def test_mcp_generated_tool_authenticates(mcp_server, monkeypatch):
    fastmcp = pytest.importorskip("fastmcp", reason="Optional MCP dependencies are not installed")
    app.dependency_overrides.clear()
    monkeypatch.setenv("MCP_API_TOKEN", issue_access_token(42, "student"))

    async def call_tool():
        async with fastmcp.Client(mcp_server.create_mcp()) as client:
            tools = await client.list_tools()
            name = next(tool.name for tool in tools if tool.name.startswith("list_plans"))
            return await client.call_tool(name, {})

    assert not asyncio.run(call_tool()).is_error
