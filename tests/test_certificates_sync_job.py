"""
Тести для життєвого циклу SyncJob сертифікатних програм (FR-013, AGENTS.md §4).

Критерії:
1. SyncJob переходить queued -> running -> succeeded з фіксацією added/updated.
2. При помилці SyncJob переходить у failed із зрозумілим error_message.
3. Після failed джобу можна повторити без блокування 409 SYNC_JOB_ALREADY_RUNNING.
4. Програми автоматично отримують актуальний статус availability після синку.

Використання ШІ: тести створено за допомогою Antigravity (Gemini 2.5 Pro).
Перевірка: pytest, ruff.
"""

from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.api.main import app
from src.db import enums as db_enums
from src.db.models.admin import SyncJob
from src.db.models.catalog import CertificateProgram, CertificateProgramCourse, Course
from src.db.session import session_factory
from src.parser.parsers.certificates import ParsedCertificateCourse, ParsedCertificateProgram
from src.parser.sync_certificates import run_certificates_sync_job

client = TestClient(app)
AUTH_ADMIN = {"Authorization": "Bearer admin-test"}


def test_certificates_sync_job_success():
    """Успішне виконання джоби, створення програм та розрахунок доступності."""
    with session_factory()() as db:
        # Створюємо опублікований курс
        course = Course(
            saz_code="TEST-CERT-SYNC-1",
            title="Прикладне машинне навчання",
            title_normalized="прикладне машинне навчання",
            credits=5.0,
            trimester=db_enums.Trimester.AUTUMN,
            recommended_year=3,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        db.add(course)

        # Створюємо задачу
        job = SyncJob(
            source=db_enums.SyncSource.FACULTY_CERTIFICATES,
            initiator=db_enums.SyncInitiator.ADMIN,
            initiated_by=1,
            status=db_enums.SyncJobStatus.QUEUED,
        )
        db.add(job)
        db.commit()

        job_id = job.id
        course_id = course.id

    def mock_loader():
        return [
            ParsedCertificateProgram(
                title="Синхронізована програма ШІ",
                source_url="https://vstup.ukma.edu.ua/ai",
                description="Опис ШІ",
                courses=[
                    ParsedCertificateCourse(
                        raw_title="Прикладне машинне навчання",
                        normalized_title="прикладне машинне навчання",
                    )
                ],
            )
        ]

    try:
        # Виконуємо синхронізацію
        run_certificates_sync_job(job_id, program_loader=mock_loader)

        with session_factory()() as db:
            updated_job = db.get(SyncJob, job_id)
            assert updated_job.status == db_enums.SyncJobStatus.SUCCEEDED
            assert updated_job.finished_at is not None
            assert updated_job.added_count == 1
            assert updated_job.error_message is None

            prog = db.query(CertificateProgram).filter_by(title="Синхронізована програма ШІ").first()
            assert prog is not None
            assert prog.availability == db_enums.CertificateAvailability.AVAILABLE
            assert len(prog.courses) == 1
            assert prog.courses[0].course_id == course_id
    finally:
        with session_factory()() as db:
            p = db.query(CertificateProgram).filter_by(title="Синхронізована програма ШІ").first()
            if p:
                db.execute(delete(CertificateProgramCourse).where(CertificateProgramCourse.program_id == p.id))
                db.execute(delete(CertificateProgram).where(CertificateProgram.id == p.id))
            db.execute(delete(SyncJob).where(SyncJob.id == job_id))
            db.execute(delete(Course).where(Course.id == course_id))
            db.commit()


def test_certificates_sync_job_failure_and_retry(admin_client):
    """При збої джоба переходить у failed і не блокує наступний запуск."""
    with session_factory()() as db:
        job1 = SyncJob(
            source=db_enums.SyncSource.FACULTY_CERTIFICATES,
            initiator=db_enums.SyncInitiator.ADMIN,
            initiated_by=1,
            status=db_enums.SyncJobStatus.QUEUED,
        )
        db.add(job1)
        db.commit()
        job1_id = job1.id

    def failing_loader():
        raise RuntimeError("Мережевий збій при підключенні до vstup.ukma.edu.ua")

    try:
        # 1. Запуск, що падає
        run_certificates_sync_job(job1_id, program_loader=failing_loader)

        with session_factory()() as db:
            failed_job = db.get(SyncJob, job1_id)
            assert failed_job.status == db_enums.SyncJobStatus.FAILED
            assert "Мережевий збій" in (failed_job.error_message or "")
            assert failed_job.finished_at is not None

        # 2. Створення нової задачі після збою проходить без 409
        res = admin_client.post(
            "/api/v1/admin/sync-jobs",
            json={"source": "faculty_certificates"},
        )
        assert res.status_code == 202, res.text
        job2_id = res.json()["id"]

        with session_factory()() as db:
            db.execute(delete(SyncJob).where(SyncJob.id.in_([job1_id, job2_id])))
            db.commit()
    finally:
        with session_factory()() as db:
            db.execute(delete(SyncJob).where(SyncJob.id == job1_id))
            db.commit()
