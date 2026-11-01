"""
Тести життєвого циклу SyncJob парсера САЗ на SQLite з підставним fetcher (без мережі).

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

import re
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import select

from src.db import enums as db_enums
from src.db.models.admin import ModerationItem, SyncJob
from src.db.session import session_factory
from src.parser.fetcher import FetchError, SessionExpired
from src.parser.sync import run_sync_job

FIXTURE = Path(__file__).parent / "fixtures" / "saz" / "catalog_filtered_26.html"


def _single_page_html(total: int = 20) -> str:
    """Фікстура каталогу, зведена до однієї сторінки з потрібним `total`."""
    html = FIXTURE.read_text(encoding="utf-8")
    html = re.sub(r"(із\s*<b>)[^<]*(</b>)", lambda m: f"{m.group(1)}{total}{m.group(2)}", html, count=1)
    return html.replace("page=2", "page=1")


class FakeFetcher:
    def __init__(self, pages=None, error=None):
        self.pages = pages or {}
        self.error = error

    def fetch(self, page):
        if self.error:
            raise self.error
        return self.pages[page]


def _factory(fetcher):
    @contextmanager
    def make():
        yield fetcher

    return make


def _new_job() -> int:
    with session_factory()() as db:
        job = SyncJob(
            source=db_enums.SyncSource.SAZ_CATALOG,
            initiator=db_enums.SyncInitiator.SCHEDULER,
            status=db_enums.SyncJobStatus.QUEUED,
        )
        db.add(job)
        db.commit()
        return job.id


def _job(job_id: int) -> SyncJob:
    with session_factory()() as db:
        return db.get(SyncJob, job_id)


def _items(job_id: int):
    with session_factory()() as db:
        return list(db.scalars(select(ModerationItem).where(ModerationItem.sync_job_id == job_id)))


@pytest.fixture(autouse=True)
def _clean_sync_state():
    """Один активний SyncJob на джерело: завершуємо залишки та чистимо чергу між тестами."""
    yield
    with session_factory()() as db:
        for job in db.scalars(select(SyncJob).where(SyncJob.source == db_enums.SyncSource.SAZ_CATALOG)):
            if job.status in (db_enums.SyncJobStatus.QUEUED, db_enums.SyncJobStatus.RUNNING):
                job.status = db_enums.SyncJobStatus.FAILED
        for item in db.scalars(
            select(ModerationItem).where(ModerationItem.status == db_enums.ModerationStatus.PENDING)
        ):
            item.status = db_enums.ModerationStatus.REJECTED
        db.commit()


def test_successful_run_creates_add_items():
    job_id = _new_job()
    run_sync_job(job_id, _factory(FakeFetcher({1: _single_page_html()})))

    job = _job(job_id)
    assert job.status == db_enums.SyncJobStatus.SUCCEEDED
    assert job.finished_at is not None
    assert job.error_message is None
    items = _items(job_id)
    assert job.added_count == len(items) == 20
    assert {i.change_type for i in items} == {db_enums.ModerationChangeType.ADD}
    assert all(i.status == db_enums.ModerationStatus.PENDING and i.course_id is None for i in items)
    assert all(i.payload["saz_code"] and i.payload["trimester"] in (1, 2, 3) for i in items)


def test_second_run_does_not_duplicate_pending_items():
    first = _new_job()
    run_sync_job(first, _factory(FakeFetcher({1: _single_page_html()})))
    second = _new_job()
    run_sync_job(second, _factory(FakeFetcher({1: _single_page_html()})))

    assert _job(second).status == db_enums.SyncJobStatus.SUCCEEDED
    assert _items(second) == []


def test_partial_scan_warns_and_still_succeeds():
    job_id = _new_job()
    run_sync_job(job_id, _factory(FakeFetcher({1: _single_page_html(total=26)})))

    job = _job(job_id)
    assert job.status == db_enums.SyncJobStatus.SUCCEEDED
    assert "неповний обхід" in job.error_message
    assert all(i.change_type != db_enums.ModerationChangeType.REMOVE for i in _items(job_id))


@pytest.mark.parametrize("error", [SessionExpired("SAZ_SESSION_EXPIRED: потрібен вхід"), FetchError("HTTP 503")])
def test_fetch_problems_fail_the_job(error):
    job_id = _new_job()
    run_sync_job(job_id, _factory(FakeFetcher(error=error)))

    job = _job(job_id)
    assert job.status == db_enums.SyncJobStatus.FAILED
    assert str(error) in job.error_message
    assert _items(job_id) == []


def test_changed_markup_fails_and_keeps_snapshot():
    job_id = _new_job()
    run_sync_job(job_id, _factory(FakeFetcher({1: "<html><body>нова верстка</body></html>"})))

    job = _job(job_id)
    assert job.status == db_enums.SyncJobStatus.FAILED
    assert job.raw_snapshot_sha256 and len(job.raw_snapshot_sha256) == 64


def test_unexpected_error_does_not_leave_job_running():
    job_id = _new_job()
    run_sync_job(job_id, _factory(FakeFetcher(error=RuntimeError("boom"))))

    job = _job(job_id)
    assert job.status == db_enums.SyncJobStatus.FAILED
    assert "RuntimeError: boom" in job.error_message


def test_job_not_in_queue_is_ignored():
    job_id = _new_job()
    run_sync_job(job_id, _factory(FakeFetcher({1: _single_page_html()})))
    before = _job(job_id).finished_at
    run_sync_job(job_id, _factory(FakeFetcher(error=RuntimeError("не має викликатись"))))
    assert _job(job_id).finished_at == before
