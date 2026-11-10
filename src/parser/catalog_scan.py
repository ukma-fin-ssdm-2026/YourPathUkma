"""Read and validate one filtered SAZ catalog scan.

Використання ШІ: спільний обхід і перевірку карток створено Codex. Перевірка: pytest.
"""

import time
from typing import Callable

from pydantic import ValidationError

from .bundle import MAX_COURSES, BundleCourse, CatalogBundle
from .config import SazSettings
from .fetcher import PageFetcher, PlaywrightFetcher
from .mapper import MappingError, course_to_payload
from .models import CatalogPage
from .parsers.catalog import CatalogParser

MAX_PAGES = 200
SCAN_DEADLINE_S = 30 * 60


class SyncFailure(Exception):
    def __init__(self, message: str, snapshot: str | None = None):
        super().__init__(message)
        self.snapshot = snapshot


def _scan(
    fetcher: PageFetcher,
    parser: CatalogParser,
    deadline_s: float = SCAN_DEADLINE_S,
    clock: Callable[[], float] = time.monotonic,
) -> tuple[list[CatalogPage], int, str]:
    deadline = clock() + deadline_s
    if isinstance(fetcher, PlaywrightFetcher):
        fetcher.set_deadline(deadline)

    first_html = fetcher.fetch(1)
    first = parser.parse(first_html)
    if first.total is None:
        raise SyncFailure("Не знайдено загальної кількості записів: імовірно, змінилась розмітка САЗ", first_html)
    last_page = 1 if first.last_page is None else first.last_page
    if not 1 <= last_page <= MAX_PAGES:
        raise SyncFailure(f"Некоректна кількість сторінок каталогу ({last_page}, ліміт {MAX_PAGES})", first_html)

    pages = [first]
    for number in range(2, last_page + 1):
        if clock() >= deadline:
            raise SyncFailure("Перевищено ліміт часу обходу каталогу", first_html)
        html = fetcher.fetch(number)
        page = parser.parse(html)
        if page.total is None or (not page.courses and not page.errors and page.total != 0):
            raise SyncFailure(f"Не розпізнано сторінку каталогу {number}", html)
        pages.append(page)
    if clock() >= deadline:
        raise SyncFailure("Перевищено ліміт часу обходу каталогу", first_html)
    return pages, first.total, first_html


def scan_catalog(
    fetcher: PageFetcher, settings: SazSettings, skipped_rows: list[list[str | None]] | None = None
) -> CatalogBundle:
    pages, expected, first_html = _scan(fetcher, CatalogParser())
    seen = sum(len(page.courses) + len(page.errors) for page in pages)
    courses: dict[str, BundleCourse] = {}
    conflicts: set[str] = set()

    for page in pages:
        if skipped_rows is not None:
            skipped_rows.extend([error.internal_id, error.title, error.message] for error in page.errors)
        for card in page.courses:
            try:
                course = BundleCourse.model_validate(course_to_payload(card))
            except (MappingError, ValidationError):
                if skipped_rows is not None:
                    skipped_rows.append([card.saz_code, card.title, "Некоректні поля дисципліни"])
                continue
            code = course.saz_code
            if code in courses:
                if courses[code] != course:
                    conflicts.add(code)
                if skipped_rows is not None:
                    skipped_rows.append([code, card.title, "Повтор коду дисципліни"])
            courses[code] = course

    if skipped_rows is not None:
        skipped_rows.extend([code, courses[code].title, "Несумісні записи для коду"] for code in sorted(conflicts))
    valid = [course for code, course in courses.items() if code not in conflicts]
    if not valid:
        raise SyncFailure("Жодної придатної картки каталогу не знайдено", first_html)
    if len(valid) > MAX_COURSES:
        raise SyncFailure(f"Перевищено ліміт дисциплін ({MAX_COURSES})", first_html)

    return CatalogBundle(
        version=1,
        academic_year=settings.academic_year,
        level=settings.level,
        expected=expected,
        seen=seen,
        skipped=seen - len(valid),
        pagination_changed=any(page.total != expected or (page.last_page or 1) != len(pages) for page in pages),
        courses=valid,
    )
