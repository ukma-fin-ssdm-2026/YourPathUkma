"""Використання ШІ: тести імпорту САЗ створено Codex. Перевірка: pytest."""

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.api.main import app
from src.db.models.admin import ModerationItem, SyncJob
from src.db.session import session_factory

URL = "/api/v1/admin/sync-jobs/saz-import"


def bundle():
    return {
        "version": 1,
        "academic_year": 2026,
        "level": 1,
        "expected": 1,
        "seen": 1,
        "skipped": 0,
        "pagination_changed": False,
        "courses": [
            {
                "saz_code": "SAZ-IMPORT-TEST",
                "title": "Imported elective",
                "description": "",
                "credits": 3,
                "trimester": 1,
                "recommended_year": 2,
                "kind": "elective",
                "instructors": [],
            }
        ],
    }


def upload(client, data):
    return client.post(URL, content=json.dumps(data), headers={"Content-Type": "application/json"})


def test_import_queues_and_deduplicates(admin_client):
    first = upload(admin_client, bundle())
    assert first.status_code == 201
    assert first.json()["added_count"] == 1
    second = upload(admin_client, bundle())
    assert second.status_code == 201
    assert second.json()["added_count"] == 0
    with session_factory()() as db:
        item = db.scalar(select(ModerationItem).where(ModerationItem.sync_job_id == first.json()["id"]))
        assert item.change_type.value == "add"
        assert item.course_id is None
        item_id = item.id
    assert admin_client.post(f"/api/v1/admin/moderation-items/{item_id}/approve").status_code == 200


def test_import_rejects_extra_fields_without_creating_job(admin_client):
    data = bundle()
    data["cookies"] = []
    with session_factory()() as db:
        before = len(db.scalars(select(SyncJob.id)).all())
    assert upload(admin_client, data).status_code == 422
    with session_factory()() as db:
        assert len(db.scalars(select(SyncJob.id)).all()) == before


def test_student_cannot_import():
    assert upload(TestClient(app), bundle()).status_code == 403


def test_import_limits_and_duplicate_codes(admin_client, monkeypatch):
    data = bundle()
    data["courses"].append(data["courses"][0])
    data["seen"] = data["expected"] = 2
    assert upload(admin_client, data).status_code == 422
    monkeypatch.setattr("src.api.routes.admin.sync.MAX_BUNDLE_BYTES", 12)
    assert upload(admin_client, bundle()).status_code == 413


def test_import_cannot_overlap_running_saz_job(admin_client):
    from src.db import enums

    with session_factory()() as db:
        job = SyncJob(
            source=enums.SyncSource.SAZ_CATALOG,
            initiator=enums.SyncInitiator.ADMIN,
            status=enums.SyncJobStatus.RUNNING,
        )
        db.add(job)
        db.commit()
        job_id = job.id

    try:
        response = upload(admin_client, bundle())
        assert response.status_code == 409
        assert response.json()["code"] == "SYNC_JOB_ALREADY_RUNNING"
    finally:
        with session_factory()() as db:
            db.get(SyncJob, job_id).status = enums.SyncJobStatus.FAILED
            db.commit()


def test_concurrent_imports_stage_one_proposal(admin_client):
    from concurrent.futures import ThreadPoolExecutor

    data = bundle()
    data["courses"][0]["saz_code"] = "SAZ-CONCURRENT-TEST"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(admin_client, data), range(2)))
    assert [response.status_code for response in results] == [201, 201]
    assert sorted(response.json()["added_count"] for response in results) == [0, 1]


def test_import_rejects_non_json_and_nul_text(admin_client):
    assert admin_client.post(URL, content="plain").status_code == 415
    data = bundle()
    data["courses"][0]["title"] = "bad\x00title"
    assert upload(admin_client, data).status_code == 422
