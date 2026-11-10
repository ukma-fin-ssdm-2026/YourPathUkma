"""
Тести надійності: ін'єкція збоїв у зовнішні залежності (Лаб 9, знахідка №4).

Тестові дублери імітують тайм-аут і обрив з'єднання. Перевіряємо обрану реакцію: тайм-аут передається у виклик,
повтори обмежені, після останньої спроби — швидка відмова `FetchError`; Microsoft недоступний — 503.

Використання ШІ: підставну HTTP-відповідь оновлено Codex. Перевірка: pytest.
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


def _fetcher_with_context(request_get, *, timeout_s=5.0, max_retries=1):
    settings = SazSettings("https://my.ukma.edu.ua", Path("state.json"), 2026, 1, 0.0, max_retries, timeout_s)
    fetcher = PlaywrightFetcher(settings)
    fetcher._context = SimpleNamespace(request=SimpleNamespace(get=request_get))
    return fetcher


def test_request_timeout_is_passed_to_playwright_in_milliseconds():
    seen = {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(status=200, url=url, text=lambda: "<html></html>", dispose=lambda: None)

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
