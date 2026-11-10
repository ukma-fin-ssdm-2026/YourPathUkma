"""
Експорт каталогу САЗ без БД. За замовчуванням CSV, з --bundle — JSON для адмінки.

Використання ШІ: спільний обхід, оновлення сесії та експорт JSON додано Codex.
Перевірка: pytest із підставним завантажувачем.
"""

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "saz_raw"
sys.path.insert(0, str(ROOT))

from src.parser.auth import login_interactive  # noqa: E402
from src.parser.bundle import MAX_BUNDLE_BYTES, CatalogBundle  # noqa: E402
from src.parser.catalog_scan import SyncFailure, scan_catalog  # noqa: E402
from src.parser.config import SazSettings, load_settings  # noqa: E402
from src.parser.fetcher import FetchError, PlaywrightFetcher, SessionExpired  # noqa: E402

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


def collect_catalog(settings: SazSettings, skipped_rows: list[list[str | None]]) -> CatalogBundle:
    def scan() -> CatalogBundle:
        with PlaywrightFetcher(settings) as fetcher:
            return scan_catalog(fetcher, settings, skipped_rows)

    try:
        return scan()
    except SessionExpired:
        login_interactive(settings)
        skipped_rows.clear()
        return scan()


def _write_csv(out: Path, bundle: CatalogBundle, skipped_rows: list[list[str | None]]) -> None:
    with out.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for course in bundle.courses:
            writer.writerow(
                [
                    course.saz_code,
                    course.title,
                    course.credits,
                    course.trimester,
                    course.semesters[0].season,
                    "; ".join(f"{s.season} {s.credits}" for s in course.semesters),
                    course.recommended_year,
                    course.kind.value,
                    course.happened,
                    course.faculty,
                    course.department,
                    "; ".join(f"{s.name} ({s.type})" for s in course.specialties),
                    "; ".join(course.instructors),
                ]
            )
    skipped_path = out.with_name(out.stem + "_skipped.csv")
    with skipped_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["saz_code", "title", "reason"])
        writer.writerows(skipped_rows)
    print(skipped_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Експорт дисциплін САЗ")
    parser.add_argument("--bundle", action="store_true", help="JSON для імпорту в YourPathUkma")
    parser.add_argument("filename", nargs="?", help="Ім’я файлу в saz_raw/")
    args = parser.parse_args()
    suffix = ".json" if args.bundle else ".csv"
    filename = Path(args.filename).name if args.filename else f"saz_export{suffix}"
    if not filename.endswith(suffix):
        parser.error(f"Ім’я файлу має закінчуватися на {suffix}")
    out = OUT_DIR / filename
    skipped_rows: list[list[str | None]] = []
    try:
        bundle = collect_catalog(load_settings(), skipped_rows)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        if args.bundle:
            content = bundle.model_dump_json(exclude_unset=True).encode("utf-8")
            if len(content) > MAX_BUNDLE_BYTES:
                raise FetchError("Файл каталогу перевищує 25 МіБ")
            out.write_bytes(content)
        else:
            _write_csv(out, bundle, skipped_rows)
    except (FetchError, SessionExpired, SyncFailure) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, ImportError):
        print("Перевірте налаштування САЗ, Playwright і доступ до локальних файлів", file=sys.stderr)
        return 1

    print(f"total in catalog: {bundle.expected}; exported: {len(bundle.courses)}; skipped: {bundle.skipped}")
    if bundle.pagination_changed or bundle.expected != bundle.seen:
        print(f"Увага: зібрано {bundle.seen} записів, можливий неповний обхід каталогу")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
