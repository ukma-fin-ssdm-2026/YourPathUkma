"""
Пробний розбір сторінок каталогу САЗ без БД і без мережі: показує, що побачить парсер.

Запуск: python scripts/saz_dry_run.py catalog_page1.html [ще файли...]
Ім'я файлу шукається в tests/fixtures/saz, а потім у saz_raw; шлях із командного рядка не приймається.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск на tests/fixtures/saz.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = (ROOT / "tests" / "fixtures" / "saz", ROOT / "saz_raw")
sys.path.insert(0, str(ROOT))

from src.parser.mapper import MappingError, course_to_payload  # noqa: E402
from src.parser.parsers.catalog import CatalogParser  # noqa: E402


def _find(name: str) -> "Path | None":
    """Лише ім'я файлу: `os.path.basename` відсікає каталоги, тож вийти за межі дозволених тек неможливо."""
    base = os.path.basename(name)
    for folder in SEARCH_DIRS:
        candidate = folder / base
        if candidate.is_file():
            return candidate
    return None


def main(paths: list) -> int:
    if not paths:
        print(__doc__)
        return 2
    parser = CatalogParser()
    for name in paths:
        path = _find(name)
        if path is None:
            print(f"{name}: файл не знайдено в tests/fixtures/saz або saz_raw")
            continue
        page = parser.parse(path.read_text(encoding="utf-8"))
        print(
            f"{name}: записів у каталозі {page.total}, остання сторінка {page.last_page}, "
            f"карток {len(page.courses)}, помилок розбору {len(page.errors)}"
        )
        for course in page.courses:
            try:
                payload = course_to_payload(course)
                note = f"триместр {payload['trimester']}, {payload['credits']} кред., {payload['kind']}"
            except MappingError as exc:
                note = f"ПРОПУСК: {exc}"
            print(f"  {course.saz_code}  {course.title[:60]:60}  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
