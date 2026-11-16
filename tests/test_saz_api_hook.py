"""
Підключення парсера до POST /admin/sync-jobs: фоновий запуск для saz_catalog, очищення завислих задач,
оновлення файлу сесії після успішного обходу.

Використання ШІ: тести очищення стану сесії оновлено Codex. Перевірка: pytest.
 файл створено за допомогою Claude (Claude Code). Перевірка: pytest.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from src.api.routes.admin import sync as sync_routes
from src.db import enums as db_enums
from src.db.base import utcnow
from src.db.models.admin import SyncJob
from src.db.session import session_factory
from src.parser.config import SazSettings
from src.parser.fetcher import PlaywrightFetcher
from src.parser.sync import fail_stale_jobs


@pytest.fixture(autouse=True)
def _finish_active_jobs():
    yield
    with session_factory()() as db:
        for job in db.scalars(select(SyncJob)):
            if job.status in (db_enums.SyncJobStatus.QUEUED, db_enums.SyncJobStatus.RUNNING):
                job.status = db_enums.SyncJobStatus.FAILED
        db.commit()


@pytest.fixture
def started(monkeypatch):
    """Підставляє run_sync_job і вмикає автозапуск; повертає список id задач, які пішли у фон."""
    calls = []
    monkeypatch.setattr(sync_routes, "run_sync_job", lambda job_id: calls.append(job_id))
    monkeypatch.setenv("SAZ_AUTORUN", "1")
    return calls


def test_saz_job_is_started_in_background(admin_client, started):
    response = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"})
    assert response.status_code == 202
    assert started == [response.json()["id"]]


def test_certificates_job_is_not_started(admin_client, started):
    response = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "faculty_certificates"})
    assert response.status_code == 202
    assert started == []


def test_disabled_autorun_does_not_queue_jobs(admin_client, started, monkeypatch):
    monkeypatch.setenv("SAZ_AUTORUN", "0")
    response = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"})
    assert response.status_code == 503
    assert response.json()["code"] == "SAZ_LIVE_SYNC_DISABLED"
    assert started == []


def test_second_start_while_running_is_conflict(admin_client, started):
    assert admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"}).status_code == 202
    again = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"})
    assert again.status_code == 409
    assert again.json()["code"] == "SYNC_JOB_ALREADY_RUNNING"


def test_stale_job_no_longer_blocks_new_start(admin_client, started):
    first = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"}).json()["id"]
    with session_factory()() as db:
        db.get(SyncJob, first).started_at = utcnow() - timedelta(hours=2)
        db.commit()

    again = admin_client.post("/api/v1/admin/sync-jobs", json={"source": "saz_catalog"})
    assert again.status_code == 202
    with session_factory()() as db:
        old = db.get(SyncJob, first)
        assert old.status == db_enums.SyncJobStatus.FAILED
        assert "Перервано" in old.error_message


def test_fresh_job_is_not_touched_by_cleanup():
    with session_factory()() as db:
        job = SyncJob(
            source=db_enums.SyncSource.SAZ_CATALOG,
            initiator=db_enums.SyncInitiator.ADMIN,
            status=db_enums.SyncJobStatus.RUNNING,
        )
        db.add(job)
        db.commit()
        assert fail_stale_jobs(db) == 0
        assert db.get(SyncJob, job.id).status == db_enums.SyncJobStatus.RUNNING


class _FakeContext:
    def __init__(self):
        self.closed = False

    def storage_state(self):
        return {
            "cookies": [
                {"domain": "my.ukma.edu.ua", "value": "new"},
                {"domain": "login.microsoftonline.com", "value": "identity-provider-secret"},
            ],
            "origins": [{"origin": "https://my.ukma.edu.ua", "localStorage": ["private"]}],
        }

    def close(self):
        self.closed = True


def _fetcher(tmp_path) -> PlaywrightFetcher:
    settings = SazSettings("https://my.ukma.edu.ua", tmp_path / "saz_state.json", 2026, 1, 0.0, 0)
    fetcher = PlaywrightFetcher(settings)
    fetcher._context = _FakeContext()
    return fetcher


def test_session_file_is_refreshed_after_successful_run(tmp_path):
    state = tmp_path / "saz_state.json"
    state.write_text('{"cookies": ["old"]}', encoding="utf-8")
    fetcher = _fetcher(tmp_path)
    fetcher.__exit__(None, None, None)
    content = state.read_text(encoding="utf-8")
    assert "new" in content
    assert "identity-provider-secret" not in content
    assert "private" not in content
    assert not (tmp_path / "saz_state.json.tmp").exists()
    assert fetcher._context is None


def test_session_file_is_kept_when_run_failed(tmp_path):
    state = tmp_path / "saz_state.json"
    state.write_text('{"cookies": ["old"]}', encoding="utf-8")
    fetcher = _fetcher(tmp_path)
    fetcher.__exit__(RuntimeError, RuntimeError("boom"), None)
    assert "old" in state.read_text(encoding="utf-8")
    assert fetcher._context is None
