"""
Вивантаження каталогу САЗ у CSV для перегляду: що саме побачив парсер. БД не використовується, САЗ лише читається.

Потрібна збережена сесія (scripts/saz_login.py). Запуск: python scripts/saz_export.py [ім'я.csv]
Файли пишуться лише в saz_raw/ (папка в .gitignore); з аргументу береться тільки ім'я файлу, без каталогів.
За замовчуванням: saz_raw/saz_export.csv і saz_raw/saz_export_skipped.csv.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: запуск на живому каталозі.
"""

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "saz_raw"
sys.path.insert(0, str(ROOT))

from src.parser.config import load_settings  # noqa: E402
from src.parser.fetcher import PlaywrightFetcher  # noqa: E402
from src.parser.mapper import MappingError, course_to_payload  # noqa: E402
from src.parser.parsers.catalog import CatalogParser  # noqa: E402

COLUMNS = [
    "saz_code",
    "title",
    "credits",
    "trimester",
    "season",
    "semesters",
    "recommended_year",
    "kind",
    "happened",
    "faculty",
    "department",
    "specialties",
    "instructors",
]


def main(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    skipped_path = out.with_name(out.stem + "_skipped.csv")
    parser = CatalogParser()
    rows, skipped = [], []
    with PlaywrightFetcher(load_settings()) as fetcher:
        first = parser.parse(fetcher.fetch(1))
        pages = [first] + [parser.parse(fetcher.fetch(n)) for n in range(2, (first.last_page or 1) + 1)]
    for page in pages:
        for error in page.errors:
            skipped.append([error.internal_id, error.title, error.message])
        for course in page.courses:
            try:
                payload = course_to_payload(course)
            except MappingError as exc:
                skipped.append([course.saz_code, course.title, str(exc)])
                continue
            rows.append(
                [
                    course.saz_code,
                    course.title,
                    payload["credits"],
                    payload["trimester"],
                    course.semesters[0].season,
                    "; ".join(f"{s.season} {s.credits}" for s in course.semesters),
                    payload["recommended_year"],
                    payload["kind"],
                    payload["happened"],
                    course.faculty,
                    course.department,
                    "; ".join(f"{s.name} ({s.type})" for s in course.specialties),
                    "; ".join(course.instructors),
                ]
            )
    with out.open("w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: Excel відкриває кирилицю правильно
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    with skipped_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["saz_code", "title", "reason"])
        writer.writerows(skipped)
    print(f"total in catalog: {first.total}; exported: {len(rows)}; skipped: {len(skipped)}")
    print(f"{out}\n{skipped_path}")


if __name__ == "__main__":
    # `os.path.basename` відсікає каталоги: куди завгодно за межі saz_raw записати неможливо.
    file_name = os.path.basename(sys.argv[1]) if len(sys.argv) > 1 else "saz_export.csv"
    if not file_name.endswith(".csv"):
        sys.exit("Ім'я файлу має закінчуватись на .csv")
    main(OUT_DIR / file_name)
