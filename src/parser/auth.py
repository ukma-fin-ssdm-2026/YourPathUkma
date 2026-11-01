"""
Ручний вхід у САЗ через Microsoft: відкривається видиме вікно Chromium, користувач входить сам (з MFA),
після переходу на my.ukma.edu.ua cookies зберігаються у файл сесії. Пароль скрипт не бачить і не зберігає (R14).

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: вручну (потрібен живий акаунт);
логіка редиректів покрита tests/test_saz_fetcher.py.
"""

import os
from pathlib import Path

from .config import SazSettings
from .fetcher import looks_like_login

LOGIN_TIMEOUT_MS = 5 * 60 * 1000


def login_interactive(settings: SazSettings) -> Path:
    from playwright.sync_api import sync_playwright

    state_path = settings.state_path
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"{settings.base_url}/auth/login")
        print("Увійдіть у САЗ через Microsoft у вікні браузера (до 5 хвилин)...")
        page.wait_for_url(
            lambda url: url.startswith(settings.base_url) and not looks_like_login(url),
            timeout=LOGIN_TIMEOUT_MS,
        )
        context.storage_state(path=str(state_path))
        browser.close()
    try:
        os.chmod(state_path, 0o600)  # на Windows діє лише частково
    except OSError:
        pass
    return state_path
