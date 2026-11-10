"""
Ручний вхід до САЗ через Microsoft у видимому браузері.

Використання ШІ: перевірку каталогу та атомарне збереження сесії додано Codex.
Перевірка: pytest із підставним браузером, живий вхід описано в README.
"""

from pathlib import Path
from urllib.parse import urlsplit

from .config import SazSettings
from .fetcher import FetchError, catalog_url, looks_like_login, read_catalog_response, save_session_state
from .parsers.catalog import CatalogParser

LOGIN_TIMEOUT_MS = 5 * 60 * 1000


def login_interactive(settings: SazSettings) -> Path:
    from playwright.sync_api import Error, sync_playwright

    origin = urlsplit(settings.base_url)

    def is_saz_page(url: str) -> bool:
        parsed = urlsplit(url)
        return (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc) and not looks_like_login(url)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            try:
                context = browser.new_context()
                page = context.new_page()
                page.goto(f"{settings.base_url}/auth/login")
                print("Увійдіть у САЗ через Microsoft у вікні браузера (до 5 хвилин)...")
                page.wait_for_url(is_saz_page, timeout=LOGIN_TIMEOUT_MS)
                status, url, html = read_catalog_response(
                    context.request, catalog_url(settings, 1), settings.timeout_s * 1000
                )
                if status != 200 or not is_saz_page(url) or CatalogParser().parse(html).total is None:
                    raise FetchError("Не вдалося підтвердити доступ до каталогу САЗ після входу")
                save_session_state(context, settings)
            finally:
                browser.close()
    except Error:
        raise FetchError("Не вдалося завершити вхід у САЗ. Перевірте Chromium і повторіть спробу") from None
    except OSError:
        raise FetchError("Не вдалося зберегти файл сесії САЗ") from None

    return settings.state_path
