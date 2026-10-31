"""
Завантаження сторінок каталогу САЗ через Playwright з сесією, збереженою після ручного входу.

Playwright імпортується лише всередині `PlaywrightFetcher`, тому тести й CI його не потребують. Запити йдуть
через `context.request` (cookies сесії, без рендеру JS). Логіка повторів винесена в `fetch_with_retry`.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_fetcher.py
(на підставних відповідях, без мережі).
"""

import os
import time
from typing import Callable, Optional, Protocol, Tuple
from urllib.parse import urlencode

from .config import SazSettings

# (HTTP-статус, фінальний URL після редиректів, текст відповіді)
RawResponse = Tuple[int, str, str]


class SessionExpired(Exception):
    """Сесія САЗ відсутня або протухла: потрібен новий ручний вхід (scripts/saz_login.py)."""


class FetchError(Exception):
    """Сторінку не вдалося завантажити після всіх повторів."""


class PageFetcher(Protocol):
    def fetch(self, page: int) -> str: ...


def catalog_url(settings: SazSettings, page: int) -> str:
    query = urlencode(
        [
            ("filter[academic_year][]", settings.academic_year),
            ("filter[level][]", settings.level),
            ("page", page),
        ]
    )
    return f"{settings.base_url}/course/catalog?{query}"


def looks_like_login(url: str) -> bool:
    return "/auth/login" in url or "login.microsoftonline" in url


def fetch_with_retry(
    get: Callable[[], RawResponse],
    *,
    retries: int,
    delay_s: float,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """429 і 5xx повторюємо з наростаючою паузою; редирект на логін означає протухлу сесію."""
    last_error = "невідома помилка"
    for attempt in range(retries + 1):
        status, url, body = get()
        if looks_like_login(url):
            raise SessionExpired("SAZ_SESSION_EXPIRED: виконайте scripts/saz_login.py")
        if status == 200:
            return body
        last_error = f"HTTP {status}"
        if status != 429 and status < 500:
            break
        if attempt < retries:
            sleep(delay_s * (2**attempt))
    raise FetchError(f"Не вдалося завантажити сторінку: {last_error}")


class PlaywrightFetcher:
    def __init__(self, settings: SazSettings):
        self._settings = settings
        self._playwright = None
        self._browser = None
        self._context = None
        self._last_request_at: Optional[float] = None

    def __enter__(self) -> "PlaywrightFetcher":
        if not self._settings.state_path.exists():
            raise SessionExpired("SAZ_SESSION_EXPIRED: файл сесії не знайдено, виконайте scripts/saz_login.py")
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(storage_state=str(self._settings.state_path))
        return self

    def _refresh_session(self) -> None:
        """Зберігає оновлені cookies після успішного обходу: сесія САЗ продовжується, адмінам не треба входити знову."""
        state_path = self._settings.state_path
        tmp = state_path.with_name(state_path.name + ".tmp")
        self._context.storage_state(path=str(tmp))
        os.replace(tmp, state_path)
        try:
            os.chmod(state_path, 0o600)  # на Windows діє лише частково
        except OSError:
            pass

    def __exit__(self, exc_type, *_exc) -> None:
        try:
            if exc_type is None and self._context is not None:
                self._refresh_session()
        finally:
            for resource in (self._context, self._browser):
                if resource is not None:
                    resource.close()
            if self._playwright is not None:
                self._playwright.stop()

    def _pause(self) -> None:
        if self._last_request_at is not None:
            wait = self._settings.delay_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
        self._last_request_at = time.monotonic()

    def fetch(self, page: int) -> str:
        url = catalog_url(self._settings, page)

        def get() -> RawResponse:
            self._pause()
            response = self._context.request.get(url)
            return response.status, response.url, response.text()

        return fetch_with_retry(get, retries=self._settings.max_retries, delay_s=self._settings.delay_s)
