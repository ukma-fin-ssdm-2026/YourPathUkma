"""
Фоновий процес синхронізації сертифікатних програм НаУКМА (FR-013, AGENTS.md §4).

Життєвий цикл SyncJob:
1. Атомарний перехід з queued у running.
2. Парсинг сайту сертифікатних програм vstup.ukma.edu.ua.
3. Оновлення переліку програм та їх дисциплін.
4. Автоматична звірка дисциплін із каталогом САЗ (reconcile_certificate_course).
5. Каскадний перерахунок доступності (recalculate_certificate_programs_availability).
6. Завершення у статус succeeded або failed без блокування наступних запусків.

Використання ШІ: модуль створено за допомогою Antigravity (Gemini 2.5 Pro).
Перевірка: tests/test_certificates_sync_job.py, pytest, ruff.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import enums as db_enums
from ..db.base import utcnow
from ..db.models.admin import AuditLog, SyncJob
from ..db.models.catalog import CertificateProgram, CertificateProgramCourse
from ..db.session import session_factory
from ..services.certificates import (
    recalculate_certificate_programs_availability,
    reconcile_certificate_course,
)
from .parsers.certificates import (
    DEFAULT_CERTIFICATES_URL,
    ParsedCertificateProgram,
    parse_catalog_page_html,
    parse_program_page_html,
)

logger = logging.getLogger(__name__)

ProgramLoader = Callable[[], List[ParsedCertificateProgram]]


def default_load_programs(base_url: str = DEFAULT_CERTIFICATES_URL) -> List[ParsedCertificateProgram]:
    """Завантажує та парсить сертифікатні програми через HTTP."""
    programs: List[ParsedCertificateProgram] = []
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        res = client.get(base_url)
        res.raise_for_status()
        catalog = parse_catalog_page_html(res.text, base_url=base_url)
        for entry in catalog:
            try:
                page_res = client.get(entry["url"])
                page_res.raise_for_status()
                parsed = parse_program_page_html(page_res.text, source_url=entry["url"], title=entry["title"])
                programs.append(parsed)
            except Exception as exc:
                logger.warning("Не вдалося завантажити програму %s (%s): %s", entry["title"], entry["url"], exc)
    return programs


def _claim_job(db: Session, job_id: int) -> bool:
    claimed = db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id, SyncJob.status == db_enums.SyncJobStatus.QUEUED)
        .values(status=db_enums.SyncJobStatus.RUNNING, started_at=utcnow())
    )
    db.commit()
    return claimed.rowcount == 1


def _fail_job(db: Session, job_id: int, message: str) -> None:
    db.rollback()
    db.execute(
        update(SyncJob)
        .where(SyncJob.id == job_id, SyncJob.status == db_enums.SyncJobStatus.RUNNING)
        .values(
            status=db_enums.SyncJobStatus.FAILED,
            finished_at=utcnow(),
            error_message=message[:2000],
        )
    )
    db.commit()


def run_certificates_sync_job(
    job_id: int,
    program_loader: Optional[ProgramLoader] = None,
) -> None:
    """Виконує фонову синхронізацію сертифікатних програм."""
    with session_factory()() as db:
        job = db.get(SyncJob, job_id)
        if not job or not _claim_job(db, job_id):
            return

        loader = program_loader or default_load_programs
        try:
            parsed_programs = loader()
            added_count = 0
            updated_count = 0

            for p_data in parsed_programs:
                program = db.scalar(select(CertificateProgram).where(CertificateProgram.title == p_data.title))
                if program is None:
                    program = CertificateProgram(
                        title=p_data.title,
                        source_url=p_data.source_url,
                        description=p_data.description,
                        availability=db_enums.CertificateAvailability.UNAVAILABLE,
                    )
                    db.add(program)
                    db.flush()
                    added_count += 1
                else:
                    program.source_url = p_data.source_url
                    if p_data.description:
                        program.description = p_data.description
                    program.updated_at = utcnow()
                    updated_count += 1

                # Оновлення переліку дисциплін
                existing_courses = {c.raw_title: c for c in program.courses}
                for c_data in p_data.courses:
                    course_entry = existing_courses.get(c_data.raw_title)
                    if course_entry is None:
                        # Нова дисципліна сертифіката
                        course_id, _ = reconcile_certificate_course(db, c_data.raw_title)
                        course_entry = CertificateProgramCourse(
                            program=program,
                            raw_title=c_data.raw_title,
                            course_id=course_id,
                        )
                        db.add(course_entry)
                    else:
                        # Перевіряємо актуальність звірки, якщо ще не звірено
                        if course_entry.course_id is None:
                            course_id, _ = reconcile_certificate_course(db, c_data.raw_title)
                            course_entry.course_id = course_id

            db.flush()
            db.expire_all()
            # Каскадний розрахунок доступності всіх програм
            recalculate_certificate_programs_availability(db)

            # Фіналізація задачі
            db.execute(
                update(SyncJob)
                .where(SyncJob.id == job_id, SyncJob.status == db_enums.SyncJobStatus.RUNNING)
                .values(
                    status=db_enums.SyncJobStatus.SUCCEEDED,
                    finished_at=utcnow(),
                    added_count=added_count,
                    updated_count=updated_count,
                    error_message=None,
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
                        "added": added_count,
                        "updated": updated_count,
                        "programs_total": len(parsed_programs),
                    },
                )
            )
            db.commit()
        except Exception as exc:
            logger.exception("Збій під час синхронізації сертифікатних програм: %s", exc)
            _fail_job(db, job_id, f"Помилка парсингу або звірки: {exc}")
