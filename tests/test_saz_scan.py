"""Використання ШІ: тести спільного обходу та локального експорту створено Codex. Перевірка: pytest."""

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import saz_export
from src.parser.bundle import CatalogBundle
from src.parser.catalog_scan import SyncFailure, scan_catalog
from src.parser.config import SazSettings
from src.parser.fetcher import FetchError, PlaywrightFetcher, SessionExpired, fetch_with_retry
from src.parser.models import CatalogPage
from src.parser.parsers.catalog import CatalogParser

FIXTURE = Path(__file__).parent / "fixtures" / "saz" / "catalog_filtered_26.html"
SETTINGS = SazSettings("https://my.ukma.edu.ua", Path("saz_state.json"), 2026, 1, 1, 3)


def test_scan_warns_about_drift_and_drops_conflicting_codes(monkeypatch):
    cards = CatalogParser().parse(FIXTURE.read_text(encoding="utf-8")).courses[:2]
    pages = [
        CatalogPage(total=3, last_page=2, courses=cards),
        CatalogPage(total=4, last_page=2, courses=[replace(cards[0], title="Conflicting title")]),
    ]
    monkeypatch.setattr(CatalogParser, "parse", lambda self, html: pages[int(html) - 1])

    class Fetcher:
        def fetch(self, page):
            return str(page)

    bundle = scan_catalog(Fetcher(), SETTINGS)
    assert bundle.pagination_changed
    assert bundle.seen == 3 and bundle.skipped == 2
    assert [course.saz_code for course in bundle.courses] == [cards[1].saz_code]
    encoded = bundle.model_dump_json()
    assert CatalogBundle.model_validate_json(encoded) == bundle
    assert all(secret not in encoded for secret in ("cookies", "origins", "raw_snapshot"))


def test_scan_with_no_mappable_courses_fails(monkeypatch):
    card = CatalogParser().parse(FIXTURE.read_text(encoding="utf-8")).courses[0]
    page = CatalogPage(total=1, last_page=1, courses=[replace(card, credits=0)])
    monkeypatch.setattr(CatalogParser, "parse", lambda self, html: page)

    class Fetcher:
        def fetch(self, page):
            return "catalog"

    with pytest.raises(SyncFailure, match="Жодної придатної"):
        scan_catalog(Fetcher(), SETTINGS)


@pytest.mark.parametrize("first_expired", [True, False])
def test_export_reuses_session_or_renews_once(monkeypatch, first_expired):
    fixture = FIXTURE.read_text(encoding="utf-8")
    calls = []
    authenticated = not first_expired

    class Fetcher:
        def fetch(self, page):
            calls.append(page)
            if not authenticated:
                raise SessionExpired("sign in")
            return fixture

    def login(settings):
        nonlocal authenticated
        calls.append("login")
        authenticated = True

    monkeypatch.setattr(saz_export, "PlaywrightFetcher", lambda settings: nullcontext(Fetcher()))
    monkeypatch.setattr(saz_export, "login_interactive", login)
    result = saz_export.collect_catalog(SETTINGS, [])
    assert result.courses
    assert calls == ([1, "login", 1, 2] if first_expired else [1, 2])


def test_backoff_cannot_overrun_scan_budget(monkeypatch):
    fetcher = PlaywrightFetcher(SETTINGS)
    fetcher.set_deadline(10)
    monkeypatch.setattr("src.parser.fetcher.time.monotonic", lambda: 9.5)
    calls = []

    def get():
        calls.append(1)
        return 429, "https://my.ukma.edu.ua/course/catalog", ""

    with pytest.raises(FetchError, match="ліміт часу"):
        fetch_with_retry(get, retries=3, delay_s=1, sleep=fetcher._sleep)
    assert calls == [1]


def test_login_form_served_at_catalog_url_expires_the_session():
    def get():
        return 200, "https://my.ukma.edu.ua/course/catalog", '<form action="/auth/login"><input type="password">'

    with pytest.raises(SessionExpired):
        fetch_with_retry(get, retries=3, delay_s=1)


@pytest.mark.parametrize("status", [200, 302])
def test_interactive_login_saves_only_after_catalog_probe(monkeypatch, tmp_path, status):
    import sys
    from types import ModuleType, SimpleNamespace

    from src.parser.auth import login_interactive

    class PlaywrightError(Exception):
        pass

    def wait_for_url(predicate, **kwargs):
        assert not predicate("https://my.ukma.edu.ua/auth/login")
        assert not predicate("https://my.ukma.edu.ua.example.org/profile")
        assert predicate("https://my.ukma.edu.ua/profile")

    page = SimpleNamespace(goto=lambda url: None, wait_for_url=wait_for_url)
    context = SimpleNamespace(new_page=lambda: page, request=object())
    browser = SimpleNamespace(new_context=lambda: context, close=lambda: None)
    playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda headless: browser))
    sync_api = ModuleType("playwright.sync_api")
    sync_api.Error = PlaywrightError
    sync_api.sync_playwright = lambda: nullcontext(playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    html = FIXTURE.read_text(encoding="utf-8")
    url = SETTINGS.base_url + ("/course/catalog" if status == 200 else "/auth/login")
    monkeypatch.setattr("src.parser.auth.read_catalog_response", lambda *args: (status, url, html))
    saves = []
    monkeypatch.setattr(
        "src.parser.auth.save_session_state", lambda context, settings: saves.append(settings.state_path)
    )
    settings = replace(SETTINGS, state_path=tmp_path / "saz_state.json")

    if status == 302:
        with pytest.raises(FetchError, match="підтвердити доступ"):
            login_interactive(settings)
        assert saves == []
    else:
        assert login_interactive(settings) == settings.state_path
        assert saves == [settings.state_path]


@pytest.mark.parametrize("expire_again", [False, True])
def test_export_restarts_at_page_one_and_never_signs_in_twice(monkeypatch, expire_again):
    fixture = FIXTURE.read_text(encoding="utf-8")
    calls = []
    attempts = iter([False, expire_again])

    class Fetcher:
        def __init__(self, restart_expires):
            self.restart_expires = restart_expires

        def fetch(self, page):
            calls.append(page)
            if ("login" not in calls and page == 2) or self.restart_expires:
                raise SessionExpired("sign in")
            return fixture

    monkeypatch.setattr(saz_export, "PlaywrightFetcher", lambda settings: nullcontext(Fetcher(next(attempts))))
    monkeypatch.setattr(saz_export, "login_interactive", lambda settings: calls.append("login"))
    if expire_again:
        with pytest.raises(SessionExpired):
            saz_export.collect_catalog(SETTINGS, [])
        assert calls == [1, 2, "login", 1]
    else:
        assert saz_export.collect_catalog(SETTINGS, []).courses
        assert calls == [1, 2, "login", 1, 2]
