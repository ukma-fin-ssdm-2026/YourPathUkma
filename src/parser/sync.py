"""
Життєвий цикл синхронізації каталогу САЗ та формування пропозицій модерації.

Використання ШІ: початкову реалізацію створено Claude Code. Спільну обробку імпорту
та захист завершення задачі додано Codex. Перевірка: pytest.
"""

import hashlib
import logging
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.base import utcnow
from ..db.models.admin import AuditLog, ModerationItem, SyncJob
from ..db.models.catalog import Course
from ..db.session import session_factory
from .bundle import CatalogBundle
from .catalog_scan import SyncFailure, scan_catalog
from .config import load_settings, remote_login_enabled
from .diff import ExistingCourse, build_changes, item_key
from .fetcher import FetchError, PageFetcher, PlaywrightFetcher, SessionExpired

logger = logging.getLogger(__name__)

ERROR_MAX = 2000
STALE_AFTER = timedelta(minutes=35)  # PERF-002: повне оновлення до 30 хв
FetcherFactory = Callable[[], AbstractContextManager[PageFetcher]]


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
        values["raw_snapshot_sha256"] = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    db.execute(
        update(SyncJob).where(SyncJob.id == job_id, SyncJob.status == db_enums.SyncJobStatus.RUNNING).values(**values)
    )
    db.commit()


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
            instructors=tuple(ci.instructor.full_name for ci in c.course_instructors),
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


def stage_catalog(db: Session, job: SyncJob, bundle: CatalogBundle) -> bool:
    """Finalize a running job and stage proposals in the caller's transaction."""
    scanned = {course.saz_code: course.model_dump(mode="json", exclude_unset=True) for course in bundle.courses}
    existing = _existing_courses(db)
    result = build_changes(
        scanned,
        existing,
        complete=False,
        pending_keys=_pending_keys(db, {course.id: course.saz_code for course in existing}),
    )
    unverified = sum(course.published and course.synced and course.saz_code not in scanned for course in existing)
    warnings = []
    if bundle.seen != bundle.expected or bundle.pagination_changed:
        warnings.append(f"неповний обхід: зібрано {bundle.seen} із {bundle.expected} записів або змінилася пагінація")
    if bundle.skipped:
        warnings.append(f"пропущено {bundle.skipped} карток")
    if unverified:
        warnings.append(f"{unverified} наявних дисциплін не підтверджено цим обходом; архівація лише вручну")

    added = result.count(db_enums.ModerationChangeType.ADD)
    updated = result.count(db_enums.ModerationChangeType.UPDATE)
    finalized = db.execute(
        update(SyncJob)
        .where(SyncJob.id == job.id, SyncJob.status == db_enums.SyncJobStatus.RUNNING)
        .values(
            status=db_enums.SyncJobStatus.SUCCEEDED,
            finished_at=utcnow(),
            added_count=added,
            updated_count=updated,
            error_message=("Попередження: " + "; ".join(warnings))[:ERROR_MAX] if warnings else None,
        )
    )
    if finalized.rowcount != 1:
        return False

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
    db.add(
        AuditLog(
            actor_id=job.initiated_by,
            action="sync_job.finish",
            object_type="SyncJob",
            object_id=job.id,
            outcome=db_enums.AuditOutcome.ALLOWED,
            new_value={
                "added": added,
                "updated": updated,
                "removed": 0,
                "total": bundle.expected,
                "seen": bundle.seen,
                "skipped": bundle.skipped,
                "unverified": unverified,
                "academic_year": bundle.academic_year,
                "level": bundle.level,
                "pagination_changed": bundle.pagination_changed,
            },
        )
    )
    return True


def run_sync_job(job_id: int, fetcher_factory: Optional[FetcherFactory] = None) -> None:
    """Виконує задачу САЗ у фоні після атомарного переходу з queued до running."""
    with session_factory()() as db:
        if not _claim(db, job_id):
            return
        try:
            settings = load_settings()
            factory = fetcher_factory or (lambda: PlaywrightFetcher(settings))
            with factory() as fetcher:
                bundle = scan_catalog(fetcher, settings)
            job = db.get(SyncJob, job_id)
            if job is not None and stage_catalog(db, job, bundle):
                db.commit()
        except SessionExpired as exc:
            message = "SAZ_SESSION_EXPIRED: підключіть САЗ повторно в адмінці" if remote_login_enabled() else str(exc)
            _fail(db, job_id, message)
        except FetchError as exc:
            _fail(db, job_id, str(exc))
        except SyncFailure as exc:
            _fail(db, job_id, str(exc), exc.snapshot)
        except Exception as exc:
            logger.error("Помилка синхронізації САЗ %s: %s", job_id, type(exc).__name__)
            _fail(db, job_id, f"Внутрішня помилка синхронізації САЗ ({type(exc).__name__})")
