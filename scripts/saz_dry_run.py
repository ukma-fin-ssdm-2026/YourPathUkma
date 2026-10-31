"""
Пробний розбір сторінок каталогу САЗ без БД і без мережі: показує, що побачить парсер.

Запуск: python scripts/saz_dry_run.py tests/fixtures/saz/catalog_page1.html [ще файли...]

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск на tests/fixtures/saz.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser.mapper import MappingError, course_to_payload  # noqa: E402
from src.parser.parsers.catalog import CatalogParser  # noqa: E402


def main(paths: list) -> int:
    if not paths:
        print(__doc__)
        return 2
    parser = CatalogParser()
    for path in paths:
        page = parser.parse(Path(path).read_text(encoding="utf-8"))
        print(
            f"{path}: записів у каталозі {page.total}, остання сторінка {page.last_page}, "
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
