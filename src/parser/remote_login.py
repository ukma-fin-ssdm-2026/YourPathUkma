"""Окремий Chromium для ручного входу адміністратора до САЗ.

Використання ШІ: керування віддаленим браузером додано Codex. Перевірка: pytest.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from secrets import token_urlsafe
from time import monotonic
from urllib.parse import urlsplit

from .config import SazSettings
from .fetcher import catalog_url, persist_session_cookies
from .parsers.catalog import CatalogParser

VIEWPORT = {"width": 960, "height": 680}
LOGIN_TIMEOUT = 300
LOGIN_HOSTS = frozenset({"my.ukma.edu.ua", "login.microsoftonline.com", "login.microsoft.com", "login.windows.net"})
STATIC_DOMAINS = ("msauth.net", "msftauth.net", "msauthimages.net", "msftauthimages.net")


class LoginNotFound(Exception):
    pass


class LoginBusy(Exception):
    pass


class LoginPending(Exception):
    pass


class LoginUnavailable(Exception):
    pass


def login_host(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme == "https" and parsed.netloc in LOGIN_HOSTS:
        return parsed.netloc
    return ""


async def restrict_request(route) -> None:
    url = urlsplit(route.request.url)
    static = url.scheme == "https" and any(url.netloc.endswith("." + domain) for domain in STATIC_DOMAINS)
    if login_host(route.request.url) or (static and not route.request.is_navigation_request()):
        await route.continue_()
    else:
        await route.abort()


@dataclass
class Login:
    id: str
    owner: int
    settings: SazSettings
    driver: object
    browser: object
    context: object
    expires_at: float = field(default_factory=lambda: monotonic() + LOGIN_TIMEOUT)

    def active_page(self):
        pages = [page for page in self.context.pages if not page.is_closed()]
        if not pages:
            raise LoginUnavailable
        page = pages[-1]
        if not login_host(page.url):
            raise LoginPending
        return page

    async def close(self):
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.browser.close(), timeout=5)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.driver.stop(), timeout=5)


class RemoteLogin:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._login: Login | None = None
        self._expiry: asyncio.Task | None = None

    async def start(self, owner: int, settings: SazSettings) -> str:
        async with self._lock:
            if self._login:
                if self._login.expires_at > monotonic():
                    raise LoginBusy
                await self._close()
            try:
                from playwright.async_api import async_playwright

                driver = await asyncio.wait_for(async_playwright().start(), timeout=15)
                browser = None
                try:
                    browser = await driver.chromium.launch(headless=True, chromium_sandbox=True, timeout=15000)
                    context = await browser.new_context(
                        viewport=VIEWPORT, accept_downloads=False, service_workers="block"
                    )
                    await context.route("**/*", restrict_request)
                    page = await context.new_page()
                    await page.goto(f"{settings.base_url}/auth/login", wait_until="commit", timeout=15000)
                except BaseException:
                    if browser is not None:
                        with contextlib.suppress(Exception):
                            await asyncio.wait_for(browser.close(), timeout=5)
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(driver.stop(), timeout=5)
                    raise
            except Exception:
                raise LoginUnavailable from None
            login = Login(token_urlsafe(24), owner, settings, driver, browser, context)
            self._login = login
            self._expiry = asyncio.create_task(self._expire(login))
            return login.id

    async def _expire(self, login: Login) -> None:
        await asyncio.sleep(LOGIN_TIMEOUT)
        async with self._lock:
            if self._login is login:
                await self._close()

    def _owned(self, owner: int, login_id: str) -> Login:
        login = self._login
        if login is None or login.owner != owner or login.id != login_id or login.expires_at <= monotonic():
            raise LoginNotFound
        return login

    async def _close(self) -> None:
        expiry, self._expiry = self._expiry, None
        login, self._login = self._login, None
        if expiry and expiry is not asyncio.current_task():
            expiry.cancel()
        if login:
            await login.close()

    async def shutdown(self) -> None:
        async with self._lock:
            await self._close()

    async def cancel(self, owner: int, login_id: str) -> None:
        async with self._lock:
            self._owned(owner, login_id)
            await self._close()

    async def frame(self, owner: int, login_id: str) -> tuple[bytes, str]:
        async with self._lock:
            page = self._owned(owner, login_id).active_page()
            host = login_host(page.url)
            if not host:
                raise LoginPending
            try:
                frame = await page.screenshot(type="jpeg", quality=72, timeout=4000)
            except Exception:
                raise LoginPending from None
            if login_host(page.url) != host:
                raise LoginPending
            return frame, host

    async def input(self, owner: int, login_id: str, host: str, action) -> None:
        async with self._lock:
            page = self._owned(owner, login_id).active_page()
            if login_host(page.url) != host:
                raise LoginPending
            try:
                if action.kind == "click":
                    await asyncio.wait_for(
                        page.mouse.click(action.x * VIEWPORT["width"], action.y * VIEWPORT["height"]), timeout=4
                    )
                elif action.kind == "key":
                    await asyncio.wait_for(page.keyboard.press(action.key), timeout=4)
                else:
                    await asyncio.wait_for(page.keyboard.insert_text(action.text), timeout=4)
            except Exception:
                raise LoginPending from None

    async def complete(self, owner: int, login_id: str) -> None:
        async with self._lock:
            login = self._owned(owner, login_id)
            try:
                response = await login.context.request.get(
                    catalog_url(login.settings, 1), max_redirects=0, timeout=8000
                )
                try:
                    if response.status != 200 or login_host(response.url) != "my.ukma.edu.ua":
                        raise LoginPending
                    html = await response.text()
                finally:
                    await response.dispose()
                if CatalogParser().parse(html).total is None:
                    raise LoginPending
                state = await login.context.storage_state()
                await asyncio.to_thread(persist_session_cookies, state["cookies"], login.settings)
            except LoginPending:
                raise
            except Exception:
                raise LoginUnavailable from None
            await self._close()


remote_login = RemoteLogin()
