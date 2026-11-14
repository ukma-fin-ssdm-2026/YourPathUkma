"""
Тести надійності: ін'єкція збоїв у зовнішні залежності (Лаб 9, знахідка №4).

Тестові дублери імітують тайм-аут і обрив з'єднання. Перевіряємо обрану реакцію: тайм-аут передається у виклик,
повтори обмежені, після останньої спроби — швидка відмова `FetchError`; Microsoft недоступний — 503.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск `pytest tests/reliability`
(без мережі, `sleep` підмінено).
"""

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src.api import microsoft
from src.api.common import ApiError
from src.parser.config import SazSettings
from src.parser.fetcher import FetchError, PlaywrightFetcher, TransientFetchError, fetch_with_retry


def test_retries_are_bounded_then_fail_fast_with_fetch_error():
    calls = []
    sleeps = []

    def always_timeout():
        calls.append(1)
        raise TransientFetchError("TimeoutError")

    with pytest.raises(FetchError):
        fetch_with_retry(always_timeout, retries=2, delay_s=1.0, sleep=sleeps.append)

    assert len(calls) == 3  # 1 спроба + 2 повтори, не більше
    assert sleeps == [1.0, 2.0]  # наростаюча пауза, без паузи після останньої спроби


def test_transient_failure_recovers_on_next_attempt():
    attempts = iter([TransientFetchError("обрив"), (200, "https://my.ukma.edu.ua/course/catalog", "<html>ok</html>")])

    def flaky():
        value = next(attempts)
        if isinstance(value, Exception):
            raise value
        return value

    assert fetch_with_retry(flaky, retries=2, delay_s=0.0, sleep=lambda _s: None) == "<html>ok</html>"


def _fetcher_with_context(request_get, *, timeout_s=5.0, max_retries=1, delay_s=0.0):
    settings = SazSettings("https://my.ukma.edu.ua", Path("state.json"), 2026, 1, delay_s, max_retries, timeout_s)
    fetcher = PlaywrightFetcher(settings)
    fetcher._context = SimpleNamespace(request=SimpleNamespace(get=request_get))
    return fetcher


def test_request_timeout_is_passed_to_playwright_in_milliseconds():
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(status=200, url=url, text=lambda: "<html></html>")

    body = _fetcher_with_context(fake_get, timeout_s=5.0).fetch(1)

    assert body == "<html></html>"
    assert seen["timeout"] == 5000.0


def test_network_timeout_is_retried_then_raises_fetch_error():
    calls = []

    def hanging_get(url, **kwargs):
        calls.append(kwargs.get("timeout"))
        raise TimeoutError("Timeout 5000ms exceeded")

    with pytest.raises(FetchError):
        _fetcher_with_context(hanging_get, max_retries=1).fetch(1)

    assert calls == [5000.0, 5000.0]  # max_retries=1 → дві спроби, кожна з тайм-аутом


# Використання ШІ: Codex додав сценарії класифікації помилок САЗ. Перевірка: pytest.
@pytest.mark.parametrize(
    ("error", "expected_attempts"),
    [(ConnectionResetError("reset"), 3), (RuntimeError("target closed"), 1)],
)
def test_fetch_retries_only_transient_request_errors(error, expected_attempts, monkeypatch):
    calls, sleeps = [], []

    def request(*args, **kwargs):
        calls.append(1)
        raise error

    from src.parser import fetcher as module

    retry = module.fetch_with_retry
    monkeypatch.setattr(module, "fetch_with_retry", lambda get, **kw: retry(get, sleep=sleeps.append, **kw))
    with pytest.raises(FetchError, match=type(error).__name__):
        fetcher = _fetcher_with_context(request, max_retries=2, delay_s=1.0)
        monkeypatch.setattr(fetcher, "_pause", lambda: None)
        fetcher.fetch(1)
    assert len(calls) == expected_attempts
    assert sleeps == ([1.0, 2.0] if expected_attempts == 3 else [])


@pytest.mark.parametrize("status", [429, 503, 200])
def test_fetch_checks_http_status_and_login_before_reading_body(status):
    from src.parser.fetcher import SessionExpired

    calls = []

    def request(url, **kwargs):
        calls.append(1)
        final_url = "https://my.ukma.edu.ua/auth/login" if status == 200 else url
        return SimpleNamespace(status=status, url=final_url, text=lambda: pytest.fail("Unexpected body read"))

    error = SessionExpired if status == 200 else FetchError
    with pytest.raises(error):
        _fetcher_with_context(request).fetch(1)
    assert len(calls) == (1 if status == 200 else 2)


def test_fetch_does_not_retry_body_read_failure():
    calls = []

    def read():
        raise TimeoutError("internal response detail")

    def request(url, **kwargs):
        calls.append(1)
        return SimpleNamespace(status=200, url=url, text=read)

    with pytest.raises(FetchError, match="TimeoutError") as caught:
        _fetcher_with_context(request).fetch(1)
    assert len(calls) == 1
    assert "internal response detail" not in str(caught.value)


def test_microsoft_unavailable_returns_503_not_a_crash(monkeypatch):
    def connection_lost(*_args, **_kwargs):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(
        microsoft,
        "_configured_settings",
        lambda: SimpleNamespace(tenant_id="t", client_id="c", client_secret=None),
    )
    monkeypatch.setattr(microsoft.httpx, "post", connection_lost)

    with pytest.raises(ApiError) as caught:
        microsoft._exchange_code("code", "v" * 43, "http://localhost/callback")

    assert caught.value.status_code == 503
    assert caught.value.code == "AUTH_PROVIDER_UNAVAILABLE"
