"""
Ручний вхід у САЗ для парсера: відкриває вікно браузера, ви входите через Microsoft (з MFA), сесія зберігається
у SAZ_STATE_PATH (за замовчуванням ~/.ukma/saz_state.json). Пароль скрипт не бачить і не зберігає (R14).

Потрібно: pip install -r requirements-parser.txt && playwright install chromium
Запуск: python scripts/saz_login.py

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: вручну (потрібен живий акаунт).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser.auth import login_interactive  # noqa: E402
from src.parser.config import load_settings  # noqa: E402

if __name__ == "__main__":
    path = login_interactive(load_settings())
    print(f"Сесію збережено: {path}. Не додавайте цей файл у репозиторій.")
