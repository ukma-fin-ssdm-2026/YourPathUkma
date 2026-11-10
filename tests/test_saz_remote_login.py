"""Використання ШІ: тести віддаленого входу та зберігання сесії додано Codex. Перевірка: pytest."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from src.api.routes.admin import saz_session
from src.parser.config import load_settings
from src.parser.fetcher import PlaywrightFetcher, clear_session_state, persist_session_cookies
from src.parser.remote_login import Login, LoginNotFound, LoginPending, RemoteLogin, login_host

ROOT = "/api/v1/admin/saz-session"
SAZ_HOST = "my.ukma.edu.ua"
COOKIE = {"name": "saz-test", "value": "synthetic-cookie-value", "domain": SAZ_HOST}


@pytest.fixture
def settings(monkeypatch, tmp_path):
    monkeypatch.setenv("SAZ_AUTORUN", "1")
    monkeypatch.setenv("SAZ_REMOTE_LOGIN", "1")
    monkeypatch.setenv("SAZ_STATE_PATH", str(tmp_path / "saz.enc"))
    monkeypatch.setenv("SAZ_SESSION_KEY", Fernet.generate_key().decode("ascii"))
    return load_settings()


def test_session_is_encrypted_and_stale_refresh_preserves_new_login(settings, monkeypatch):
    persist_session_cookies([COOKIE, {**COOKIE, "domain": "login.microsoftonline.com"}], settings)
    previous = settings.state_path.read_bytes()
    assert b"synthetic-cookie-value" not in previous
    assert b"microsoftonline" not in Fernet(settings.session_key).decrypt(previous)

    monkeypatch.setattr(PlaywrightFetcher, "_start", lambda _: None)
    fetcher = PlaywrightFetcher(settings)
    assert fetcher.__enter__()._state["cookies"] == [COOKIE]

    updated = {**COOKIE, "value": "new-session"}
    persist_session_cookies([updated], settings)
    current = settings.state_path.read_bytes()
    persist_session_cookies([COOKIE], settings, previous)
    assert settings.state_path.read_bytes() == current
    clear_session_state(settings)
    persist_session_cookies([COOKIE], settings, current)
    assert not settings.state_path.exists()


def test_admin_starts_and_completes_remote_login(admin_client, settings, monkeypatch):
    start = AsyncMock(return_value="test-login-id")

    async def complete(owner, login_id):
        assert (owner, login_id) == (1, "test-login-id")
        persist_session_cookies([COOKIE], settings)

    monkeypatch.setattr(saz_session.remote_login, "start", start)
    monkeypatch.setattr(saz_session.remote_login, "complete", complete)
    assert admin_client.get(ROOT).json() == {"connected": False}
    blocked = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "SAZ_SESSION_REQUIRED"

    created = admin_client.post(ROOT + "/login")
    assert created.status_code == 201 and created.json() == {"id": "test-login-id"}
    start.assert_awaited_once_with(1, settings)
    assert admin_client.post(ROOT + "/login/test-login-id/complete").status_code == 204
    assert admin_client.get(ROOT).json() == {"connected": True}
    assert admin_client.delete(ROOT).status_code == 204
    assert admin_client.get(ROOT).json() == {"connected": False}


def test_remote_input_cannot_leak_invalid_text_in_errors(admin_client, settings, monkeypatch):
    command = AsyncMock()
    monkeypatch.setattr(saz_session.remote_login, "input", command)
    path = ROOT + "/login/test-id/input"
    response = admin_client.post(path, json={"host": SAZ_HOST, "action": {"kind": "key", "key": "secret-text"}})
    assert response.status_code == 422
    assert "secret-text" not in response.text
    command.assert_not_called()


def test_only_the_owner_can_view_or_control_the_approved_origin(settings):
    async def check():
        manager = RemoteLogin()
        page = SimpleNamespace(
            url="https://login.microsoftonline.com/example",
            is_closed=lambda: False,
            screenshot=AsyncMock(return_value=b"frame"),
            keyboard=SimpleNamespace(insert_text=AsyncMock()),
        )
        manager._login = Login("id", 1, settings, None, None, SimpleNamespace(pages=[page]))
        with pytest.raises(LoginNotFound):
            await manager.frame(2, "id")
        assert await manager.frame(1, "id") == (b"frame", "login.microsoftonline.com")

        with pytest.raises(LoginPending):
            await manager.input(1, "id", SAZ_HOST, SimpleNamespace(kind="text", text="example"))
        page.keyboard.insert_text.assert_not_called()
        assert not login_host("https://login.microsoftonline.com.evil.example")

    asyncio.run(check())


def test_browser_saves_only_a_verified_catalog(settings):
    async def check():
        manager = RemoteLogin()
        response = SimpleNamespace(
            status=302,
            url="https://my.ukma.edu.ua/course/catalog",
            text=AsyncMock(return_value='<div class="summary">1–20 із <b>100</b></div>'),
            dispose=AsyncMock(),
        )
        context = SimpleNamespace(
            request=SimpleNamespace(get=AsyncMock(return_value=response)),
            storage_state=AsyncMock(return_value={"cookies": [COOKIE]}),
        )
        driver = SimpleNamespace(stop=AsyncMock())
        browser = SimpleNamespace(close=AsyncMock())
        manager._login = Login("id", 1, settings, driver, browser, context)

        with pytest.raises(LoginPending):
            await manager.complete(1, "id")
        assert not settings.state_path.exists()
        context.storage_state.assert_not_called()

        response.status = 200
        response.text.return_value = '<div class="summary"><b>1–20</b> із <b>100</b></div>'
        await manager.complete(1, "id")
        assert settings.state_path.is_file()
        browser.close.assert_awaited_once()
        driver.stop.assert_awaited_once()
        with pytest.raises(LoginNotFound):
            await manager.frame(1, "id")

    asyncio.run(check())
