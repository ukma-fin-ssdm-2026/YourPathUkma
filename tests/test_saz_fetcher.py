"""
Тести завантажувача САЗ: повтори на 429/5xx, протухла сесія, URL каталогу. Без мережі й без Playwright.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from pathlib import Path

import pytest

from src.parser.config import SazSettings
from src.parser.fetcher import (
    FetchError,
    SessionExpired,
    catalog_url,
    fetch_with_retry,
    looks_like_login,
    start_with_retry,
)

OK_URL = "https://my.ukma.edu.ua/course/catalog"


def _responses(*items):
    queue = list(items)
    calls = []

    def get():
        calls.append(1)
        return queue.pop(0)

    return get, calls


def test_success_returns_body():
    get, calls = _responses((200, OK_URL, "<html/>"))
    assert fetch_with_retry(get, retries=3, delay_s=1, sleep=lambda _s: None) == "<html/>"
    assert len(calls) == 1


def test_retries_429_with_growing_pause():
    pauses = []
    get, calls = _responses((429, OK_URL, ""), (503, OK_URL, ""), (200, OK_URL, "ok"))
    assert fetch_with_retry(get, retries=3, delay_s=2, sleep=pauses.append) == "ok"
    assert pauses == [2, 4]
    assert len(calls) == 3


def test_gives_up_after_retries():
    get, calls = _responses(*[(429, OK_URL, "")] * 3)
    with pytest.raises(FetchError):
        fetch_with_retry(get, retries=2, delay_s=1, sleep=lambda _s: None)
    assert len(calls) == 3


def test_client_error_is_not_retried():
    get, calls = _responses((404, OK_URL, ""))
    with pytest.raises(FetchError):
        fetch_with_retry(get, retries=3, delay_s=1, sleep=lambda _s: None)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url",
    ["https://my.ukma.edu.ua/auth/login", "https://login.microsoftonline.com/common/oauth2/authorize"],
)
def test_redirect_to_login_means_expired_session(url):
    get, _ = _responses((200, url, "<html>login</html>"))
    with pytest.raises(SessionExpired):
        fetch_with_retry(get, retries=3, delay_s=1, sleep=lambda _s: None)


def test_looks_like_login():
    assert looks_like_login("https://my.ukma.edu.ua/auth/login?x=1")
    assert not looks_like_login(OK_URL)


def test_catalog_url_has_filters_and_page():
    settings = SazSettings("https://my.ukma.edu.ua", Path("s.json"), 2026, 1, 1.0, 3)
    url = catalog_url(settings, 5)
    assert url.startswith("https://my.ukma.edu.ua/course/catalog?")
    assert "filter%5Bacademic_year%5D%5B%5D=2026" in url
    assert "filter%5Blevel%5D%5B%5D=1" in url
    assert url.endswith("page=5")


def test_start_retries_driver_crash_then_succeeds():
    attempts, pauses, cleaned = [], [], []

    def start():
        attempts.append(1)
        if len(attempts) < 3:
            raise Exception("Connection.init: Connection closed while reading from the driver")

    start_with_retry(start, retries=2, delay_s=2, sleep=pauses.append, cleanup=lambda: cleaned.append(1))
    assert len(attempts) == 3
    assert pauses == [2, 4]
    assert len(cleaned) == 2


def test_start_gives_clear_message_after_retries():
    def start():
        raise Exception("Connection closed while reading from the driver")

    with pytest.raises(FetchError) as info:
        start_with_retry(start, retries=1, delay_s=1, sleep=lambda _s: None)
    assert "Не вдалося запустити браузер Playwright" in str(info.value)
    assert "Connection closed while reading from the driver" in str(info.value)
