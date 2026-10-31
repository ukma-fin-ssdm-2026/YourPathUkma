"""
Життєвий цикл SyncJob для джерела `saz_catalog`: queued -> running -> succeeded | failed.

Парсер нічого не пише в `courses` напряму (ADR-002): результат — елементи `moderation_items` (add/update/remove),
які схвалює адміністратор. REMOVE створюються лише після повного й безпомилкового обходу каталогу.
Попередження (картки, що не розібрались; неповний обхід) потрапляють у `error_message` задачі, але не валять її.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: tests/test_saz_sync.py
(SQLite, підставний fetcher без мережі).
"""

import hashlib
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.base import utcnow
from ..db.models.admin import AuditLog, ModerationItem, SyncJob
from ..db.models.catalog import Course
from ..db.session import session_factory
from .config import load_settings
from .diff import ExistingCourse, build_changes, item_key
from .fetcher import FetchError, PageFetcher, PlaywrightFetcher, SessionExpired
from .mapper import MappingError, course_to_payload
from .models import CatalogPage
from .parsers.catalog import CatalogParser

ERROR_MAX = 2000
STALE_AFTER = timedelta(minutes=35)  # PERF-002: повне оновлення до 30 хв
FetcherFactory = Callable[[], AbstractContextManager[PageFetcher]]


class SyncFailure(Exception):
    """Задачу треба завершити зі статусом failed; `snapshot` — сирий HTML для розбору збою (R13)."""

    def __init__(self, message: str, snapshot: Optional[str] = None):
        super().__init__(message)
        self.snapshot = snapshot


def _default_fetcher() -> AbstractContextManager[PageFetcher]:
    return PlaywrightFetcher(load_settings())


def fail_stale_jobs(db: Session, max_age: timedelta = STALE_AFTER) -> int:
    """
    Задача, яка висить у queued/running довше за `max_age` (сервер перезапустили посеред обходу), блокувала б
    нові запуски через 409 SYNC_JOB_ALREADY_RUNNING. Позначаємо такі задачі failed. Повертає їх кількість.
    """
    active = (db_enums.SyncJobStatus.QUEUED, db_enums.SyncJobStatus.RUNNING)
    stale = db.execute(
        update(SyncJob)
        .where(SyncJob.status.in_(active), SyncJob.started_at < utcnow() - max_age)
        .values(
            status=db_enums.SyncJobStatus.FAILED,
            finished_at=utcnow(),
            error_message="Перервано: задача не завершилась вчасно (імовірно, сервер було перезапущено)",
        )
    )
    db.commit()
    return stale.rowcount


def _claim(db: Session, job_id: int) -> bool:
    claimed = db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id, SyncJob.status == db_enums.SyncJobStatus.QUEUED)
        .values(status=db_enums.SyncJobStatus.RUNNING, started_at=utcnow())
    )
    db.commit()
    return claimed.rowcount == 1


def _fail(db: Session, job_id: int, message: str, snapshot: Optional[str] = None) -> None:
    db.rollback()
    values: Dict[str, Any] = {
        "status": db_enums.SyncJobStatus.FAILED,
        "finished_at": utcnow(),
        "error_message": message[:ERROR_MAX],
    }
    if snapshot is not None:
        values["raw_snapshot"] = snapshot
        values["raw_snapshot_sha256"] = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    db.execute(update(SyncJob).where(SyncJob.id == job_id).values(**values))
    db.commit()


def _scan(fetcher: PageFetcher, parser: CatalogParser) -> Tuple[List[CatalogPage], int, str]:
    """Усі сторінки каталогу. Повертає сторінки, `total` із першої й HTML першої сторінки."""
    first_html = fetcher.fetch(1)
    first = parser.parse(first_html)
    if first.total is None:
        raise SyncFailure("Не знайдено загальної кількості записів: імовірно, змінилась розмітка САЗ", first_html)
    pages = [first]
    for number in range(2, (first.last_page or 1) + 1):
        pages.append(parser.parse(fetcher.fetch(number)))
    return pages, first.total, first_html


def _existing_courses(db: Session) -> List[ExistingCourse]:
    return [
        ExistingCourse(
            id=c.id,
            saz_code=c.saz_code,
            title=c.title,
            description=c.description or "",
            credits=float(c.credits),
            trimester=c.trimester.number,
            recommended_year=c.recommended_year,
            kind=c.kind.value,
            published=c.publication_status == db_enums.PublicationStatus.PUBLISHED,
            synced=c.last_sync_job_id is not None,
        )
        for c in db.scalars(select(Course))
    ]


def _pending_keys(db: Session, code_by_id: Dict[int, str]) -> set:
    keys = set()
    pending = select(ModerationItem).where(ModerationItem.status == db_enums.ModerationStatus.PENDING)
    for item in db.scalars(pending):
        payload = item.payload or {}
        code = payload.get("saz_code") or code_by_id.get(item.course_id or -1)
        if code:
            keys.add(item_key(item.change_type, code, payload))
    return keys


def _execute(db: Session, job: SyncJob, fetcher_factory: FetcherFactory) -> None:
    parser = CatalogParser()
    try:
        with fetcher_factory() as fetcher:
            pages, total, first_html = _scan(fetcher, parser)
    except (SessionExpired, FetchError) as exc:
        raise SyncFailure(str(exc)) from exc

    cards = [course for page in pages for course in page.courses]
    card_errors = [error for page in pages for error in page.errors]
    if not cards:
        raise SyncFailure("Жодної картки не розібрано: імовірно, змінилась розмітка САЗ", first_html)

    scanned: Dict[str, Dict[str, Any]] = {}
    mapping_errors: List[str] = []
    for course in cards:
        try:
            scanned[course.saz_code] = course_to_payload(course)
        except MappingError as exc:
            mapping_errors.append(str(exc))

    seen = len(cards) + len(card_errors)
    warnings: List[str] = []
    if seen != total:
        warnings.append(f"неповний обхід: зібрано {seen} із {total} записів, REMOVE не створено")
    skipped = len(card_errors) + len(mapping_errors)
    if skipped:
        first_error = card_errors[0].message if card_errors else mapping_errors[0]
        warnings.append(f"пропущено {skipped} карток (перша: {first_error}), REMOVE не створено")
    complete = not warnings

    existing = _existing_courses(db)
    result = build_changes(
        scanned,
        existing,
        complete=complete,
        pending_keys=_pending_keys(db, {c.id: c.saz_code for c in existing}),
    )
    if result.held_removals:
        warnings.append(f"{result.held_removals} дисциплін зникло з САЗ, REMOVE утримано: перевірте фільтри й розмітку")

    for change in result.changes:
        db.add(
            ModerationItem(
                sync_job_id=job.id,
                course_id=change.course_id,
                change_type=change.change_type,
                payload=change.payload,
                diff=change.diff,
            )
        )
    added = result.count(db_enums.ModerationChangeType.ADD)
    updated = result.count(db_enums.ModerationChangeType.UPDATE)
    removed = result.count(db_enums.ModerationChangeType.REMOVE)
    db.add(
        AuditLog(
            actor_id=job.initiated_by,
            action="sync_job.finish",
            object_type="SyncJob",
            object_id=job.id,
            outcome=db_enums.AuditOutcome.ALLOWED,
            new_value={"added": added, "updated": updated, "removed": removed, "total": total},
        )
    )
    db.execute(
        update(SyncJob)
        .where(SyncJob.id == job.id)
        .values(
            status=db_enums.SyncJobStatus.SUCCEEDED,
            finished_at=utcnow(),
            added_count=added,
            updated_count=updated,
            error_message=("Попередження: " + "; ".join(warnings))[:ERROR_MAX] if warnings else None,
        )
    )
    db.commit()


def run_sync_job(job_id: int, fetcher_factory: Optional[FetcherFactory] = None) -> None:
    """Виконує задачу `queued`. Викликається у фоні (BackgroundTasks); не кидає винятків назовні."""
    with session_factory()() as db:
        if not _claim(db, job_id):
            return
        job = db.get(SyncJob, job_id)
        try:
            _execute(db, job, fetcher_factory or _default_fetcher)
        except SyncFailure as exc:
            _fail(db, job_id, str(exc), exc.snapshot)
        except Exception as exc:  # фонова задача не має залишити SyncJob у статусі running
            _fail(db, job_id, f"{type(exc).__name__}: {exc}")
