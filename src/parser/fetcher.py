"""
Завантаження сторінок каталогу САЗ через Playwright з сесією, збереженою після ручного входу.

Playwright імпортується лише всередині `PlaywrightFetcher`, тому тести й CI його не потребують. Запити йдуть
через `context.request` (cookies сесії, без рендеру JS). Логіка повторів винесена в `fetch_with_retry`.

Використання ШІ: атомарне збереження сесії та бюджет часу додано Codex. Перевірка: pytest.
Файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_fetcher.py
(на підставних відповідях, без мережі).
"""

import contextlib
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional, Protocol, Tuple
from urllib.parse import urlencode, urljoin, urlsplit

from .config import SazSettings

logger = logging.getLogger(__name__)

# (HTTP-статус, фінальний URL після редиректів, текст відповіді)
RawResponse = Tuple[int, str, str]


class SessionExpired(Exception):
    """Сесія САЗ відсутня або протухла: потрібен новий ручний вхід (scripts/saz_login.py)."""


class FetchError(Exception):
    """Сторінку не вдалося завантажити після всіх повторів."""


class TransientFetchError(Exception):
    """Тимчасовий збій одного запиту (тайм-аут, обрив з'єднання): його можна повторити."""


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
    parsed = urlsplit(url)
    return parsed.path.rstrip("/") == "/auth/login" or parsed.hostname == "login.microsoftonline.com"


def fetch_with_retry(
    get: Callable[[], RawResponse],
    *,
    retries: int,
    delay_s: float,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """
    429, 5xx і тимчасові збої (тайм-аут, обрив) повторюємо з наростаючою паузою; кількість спроб обмежена
    (`retries + 1`), після останньої — `FetchError`. Редирект на логін означає протухлу сесію.
    """
    last_error = "невідома помилка"
    for attempt in range(retries + 1):
        try:
            status, url, body = get()
        except TransientFetchError as exc:
            last_error = str(exc)
            if attempt < retries:
                sleep(delay_s * (2**attempt))
            continue
        if status in (401, 403) or looks_like_login(url):
            raise SessionExpired("SAZ_SESSION_EXPIRED: виконайте scripts/saz_login.py")
        if status == 200:
            if "/auth/login" in body and re.search(r"<input\b[^>]*\btype\s*=\s*['\"]?password\b", body, re.I):
                raise SessionExpired("SAZ_SESSION_EXPIRED: виконайте scripts/saz_login.py")
            return body
        last_error = f"HTTP {status}"
        if status != 429 and status < 500:
            break
        if attempt < retries:
            sleep(delay_s * (2**attempt))
    raise FetchError(f"Не вдалося завантажити сторінку: {last_error}")


def start_with_retry(
    start: Callable[[], None],
    *,
    retries: int = 2,
    delay_s: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    cleanup: Callable[[], None] = lambda: None,
) -> None:
    """
    Запуск драйвера Playwright і браузера іноді падає («Connection closed while reading from the driver»),
    найчастіше коли системі не вистачає пам'яті. Повторюємо з паузою, а після невдачі даємо зрозуміле повідомлення.
    """
    last = "невідома помилка"
    for attempt in range(retries + 1):
        try:
            return start()
        except Exception as exc:  # Playwright кидає різні типи винятків
            last = type(exc).__name__
            cleanup()
            if attempt < retries:
                sleep(delay_s * (attempt + 1))
    raise FetchError(
        f"Не вдалося запустити браузер Playwright ({last}). Перевірте вільну пам'ять і виконайте "
        "`playwright install chromium`, потім повторіть запуск."
    )


def save_session_state(context, settings: SazSettings) -> None:
    """Persist only cookies usable by SAZ, via a private temporary file."""
    path = settings.state_path
    path.parent.mkdir(parents=True, exist_ok=True)
    host = urlsplit(settings.base_url).hostname or ""
    cookies = []
    for cookie in context.storage_state()["cookies"]:
        domain = cookie["domain"].lstrip(".").lower()
        if domain and (domain == host or ("." in domain and host.endswith("." + domain))):
            cookies.append(cookie)
    if not cookies:
        raise FetchError("САЗ не надав cookies для повторного входу")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
            temporary = Path(temp.name)
            json.dump({"cookies": cookies, "origins": []}, temp)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_catalog_response(request, url: str, timeout_ms: float) -> RawResponse:
    response = request.get(url, timeout=timeout_ms, max_redirects=0)
    try:
        status = response.status
        if 300 <= status < 400:
            target = response.headers.get("location", "")
            return status, urljoin(url, target), ""
        return status, response.url, response.text() if status == 200 else ""
    finally:
        response.dispose()


class PlaywrightFetcher:
    def __init__(self, settings: SazSettings):
        self._settings = settings
        self._playwright = None
        self._browser = None
        self._context = None
        self._last_request_at: Optional[float] = None
        self._deadline: Optional[float] = None
        self._state = None

    def __enter__(self) -> "PlaywrightFetcher":
        try:
            self._state = json.loads(self._settings.state_path.read_text(encoding="utf-8"))
            cookies = self._state["cookies"]
            if not isinstance(cookies, list) or not cookies:
                raise ValueError
        except (FileNotFoundError, ValueError, TypeError, KeyError) as exc:
            raise SessionExpired("SAZ_SESSION_EXPIRED: оновіть сесію через scripts/saz_login.py") from exc
        except OSError:
            raise FetchError("Не вдалося прочитати файл сесії САЗ") from None
        start_with_retry(self._start, delay_s=self._settings.delay_s * 2, cleanup=self._stop)
        return self

    def _start(self) -> None:
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._context = self._browser.new_context(storage_state=self._state)
        # Глобальний тайм-аут контексту (на випадок викликів без явного `timeout`)
        self._context.set_default_timeout(self._settings.timeout_s * 1000)

    def _stop(self) -> None:
        """Закриває те, що встигло запуститись; помилки закриття ігноруємо."""
        for resource in (self._context, self._browser):
            if resource is not None:
                with contextlib.suppress(Exception):
                    resource.close()
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                self._playwright.stop()
        self._context = self._browser = self._playwright = None

    def set_deadline(self, deadline: float) -> None:
        self._deadline = deadline

    def _remaining(self) -> float:
        if self._deadline is None:
            return self._settings.timeout_s
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise FetchError("Перевищено ліміт часу обходу каталогу")
        return remaining

    def _sleep(self, seconds: float) -> None:
        if self._deadline is not None and seconds >= self._remaining():
            raise FetchError("Перевищено ліміт часу обходу каталогу")
        time.sleep(seconds)

    def __exit__(self, exc_type, *_exc) -> None:
        try:
            if exc_type is None and self._context is not None:
                try:
                    save_session_state(self._context, self._settings)
                except Exception as exc:
                    logger.warning("Не вдалося оновити файл сесії САЗ: %s", type(exc).__name__)
        finally:
            self._stop()

    def _pause(self) -> None:
        if self._last_request_at is not None:
            wait = self._settings.delay_s - (time.monotonic() - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = time.monotonic()

    def fetch(self, page: int) -> str:
        url = catalog_url(self._settings, page)

        def get() -> RawResponse:
            self._pause()
            timeout_ms = min(self._settings.timeout_s, self._remaining()) * 1000
            try:
                return read_catalog_response(self._context.request, url, timeout_ms)
            except Exception as exc:
                logger.warning("Запит до САЗ не вдався (сторінка %s): %s", page, type(exc).__name__)
                raise TransientFetchError(f"Тимчасовий збій запиту сторінки {page}") from exc

        return fetch_with_retry(
            get, retries=self._settings.max_retries, delay_s=self._settings.delay_s, sleep=self._sleep
        )
