"""
Налаштування парсера САЗ з змінних середовища.

Сесія САЗ (cookies після ручного входу) зберігається у файлі `SAZ_STATE_PATH` поза репозиторієм. Логін і пароль
не зберігаються нікуди (R14): адмін входить сам, у тому числі з MFA (`scripts/saz_login.py`).

Використання ШІ: перевірку параметрів парсера додано Codex. Перевірка: pytest.
Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_fetcher.py.
"""

import math
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SazSettings:
    base_url: str
    state_path: Path
    academic_year: int  # значення фільтра `filter[academic_year][]`: початок навчального року (2026 = 2026–2027)
    level: int  # `filter[level][]`: 1 = Бакалавр, 2 = Магістр
    delay_s: float  # пауза між запитами, щоб САЗ не заблокував IP
    max_retries: int
    timeout_s: float = 30.0  # тайм-аут одного HTTP-запиту до САЗ (Лаб 9, знахідка №4)


def load_settings() -> SazSettings:
    settings = SazSettings(
        base_url=os.getenv("SAZ_BASE_URL", "https://my.ukma.edu.ua").rstrip("/"),
        state_path=Path(os.getenv("SAZ_STATE_PATH", str(Path.home() / ".ukma" / "saz_state.json"))),
        academic_year=int(os.getenv("SAZ_ACADEMIC_YEAR", "2026")),
        level=int(os.getenv("SAZ_LEVEL", "1")),
        delay_s=float(os.getenv("SAZ_DELAY_S", "1.0")),
        max_retries=int(os.getenv("SAZ_MAX_RETRIES", "3")),
        timeout_s=float(os.getenv("SAZ_TIMEOUT_S", "30")),
    )

    if not 2000 <= settings.academic_year <= 2100 or settings.level not in (1, 2):
        raise ValueError("Некоректний навчальний рік або рівень САЗ")
    if not math.isfinite(settings.timeout_s) or not 0 < settings.timeout_s <= 180:
        raise ValueError("SAZ_TIMEOUT_S має бути в межах (0, 180]")
    if not math.isfinite(settings.delay_s) or not 0 <= settings.delay_s <= 60 or not 0 <= settings.max_retries <= 10:
        raise ValueError("Некоректна пауза або кількість повторів САЗ")
    return settings


def autorun_enabled() -> bool:
    """Чи запускати парсер у фоні одразу після POST /admin/sync-jobs (у тестах вимкнено)."""
    return os.getenv("SAZ_AUTORUN", "1") != "0"
