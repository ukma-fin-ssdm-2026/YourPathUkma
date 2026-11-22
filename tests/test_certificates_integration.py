"""
Інтеграційні тести сертифікатних програм: preferences, каталог дисциплін та AI промпт (FR-013, AGENTS.md §4).

Використання ШІ: тести створено за допомогою Antigravity (Gemini 2.5 Pro).
Перевірка: pytest, ruff.
"""

from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.ai.prompt_builder import build_context, build_prompt
from src.api.main import app
from src.db import enums as db_enums
from src.db.models.catalog import CertificateProgram, CertificateProgramCourse, Course
from src.db.models.preferences import PlanPreferences
from src.db.session import session_factory

client = TestClient(app)
AUTH_STUDENT_42 = {"Authorization": "Bearer test"}


def test_preferences_rejects_unavailable_certificate_program():
    """Студент не може обрати недоступну сертифікатну програму в побажаннях (FR-013)."""
    with session_factory()() as db:
        unavail_prog = CertificateProgram(
            title="Недоступний сертифікат",
            source_url="https://vstup.ukma.edu.ua/unavail",
            availability=db_enums.CertificateAvailability.UNAVAILABLE,
        )
        db.add(unavail_prog)
        db.commit()
        prog_id = unavail_prog.id

    try:
        payload = {
            "academic_year": 2026,
            "wants_certificate": True,
            "certificate_program_id": prog_id,
        }
        res = client.put("/api/v1/preferences/2026", json=payload, headers=AUTH_STUDENT_42)
        assert res.status_code == 422, res.text
        details = res.json()["details"]
        assert any("CERTIFICATE_PROGRAM_UNAVAILABLE" in d["message"] for d in details)
    finally:
        with session_factory()() as db:
            db.execute(delete(CertificateProgram).where(CertificateProgram.id == prog_id))
            db.commit()


def test_preferences_accepts_available_certificate_program():
    """Студент успішно обирає доступну сертифікатну програму в побажаннях."""
    with session_factory()() as db:
        avail_prog = CertificateProgram(
            title="Доступний сертифікат",
            source_url="https://vstup.ukma.edu.ua/avail",
            availability=db_enums.CertificateAvailability.AVAILABLE,
        )
        db.add(avail_prog)
        db.commit()
        prog_id = avail_prog.id

    try:
        payload = {
            "academic_year": 2026,
            "wants_certificate": True,
            "certificate_program_id": prog_id,
        }
        res = client.put("/api/v1/preferences/2026", json=payload, headers=AUTH_STUDENT_42)
        assert res.status_code == 200, res.text
        assert res.json()["certificate_program_id"] == prog_id
        assert res.json()["wants_certificate"] is True
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanPreferences).where(PlanPreferences.student_id == 42))
            db.execute(delete(CertificateProgram).where(CertificateProgram.id == prog_id))
            db.commit()


def test_disciplines_expose_certificate_programs():
    """Каталог дисциплін показує назви сертифікатних програм, до яких входить дисципліна."""
    with session_factory()() as db:
        course = Course(
            saz_code="TEST-CERT-DISC-1",
            title="Дисципліна Сертифіката",
            title_normalized="дисципліна сертифіката",
            credits=4.0,
            trimester=db_enums.Trimester.AUTUMN,
            recommended_year=2,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        prog = CertificateProgram(
            title="Програма Мережевої Безпеки",
            source_url="https://vstup.ukma.edu.ua/netsec",
            availability=db_enums.CertificateAvailability.AVAILABLE,
            hidden=False,
        )
        db.add_all([course, prog])
        db.flush()

        link = CertificateProgramCourse(program_id=prog.id, course_id=course.id, raw_title="Дисципліна Сертифіката")
        db.add(link)
        db.commit()

        course_id = course.id
        prog_id = prog.id

    try:
        # GET /disciplines/{id}
        res = client.get(f"/api/v1/disciplines/{course_id}", headers=AUTH_STUDENT_42)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "Програма Мережевої Безпеки" in data["certificate_programs"]

        # GET /disciplines (list)
        list_res = client.get("/api/v1/disciplines", headers=AUTH_STUDENT_42)
        assert list_res.status_code == 200
        disc_items = [d for d in list_res.json()["disciplines"] if d["id"] == course_id]
        assert len(disc_items) == 1
        assert "Програма Мережевої Безпеки" in disc_items[0]["certificate_programs"]
    finally:
        with session_factory()() as db:
            db.execute(delete(CertificateProgramCourse).where(CertificateProgramCourse.program_id == prog_id))
            db.execute(delete(CertificateProgram).where(CertificateProgram.id == prog_id))
            db.execute(delete(Course).where(Course.id == course_id))
            db.commit()


def test_ai_prompt_builder_includes_available_certificate_program():
    """AI промпт містить назву та обов'язкові дисципліни доступної сертифікатної програми."""
    with session_factory()() as db:
        course = Course(
            saz_code="TEST-CERT-AI-1",
            title="ШІ для Інженерії",
            title_normalized="ші для інженерії",
            credits=5.0,
            trimester=db_enums.Trimester.AUTUMN,
            recommended_year=2,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        prog = CertificateProgram(
            title="Програма ШІ-Інженерії",
            source_url="https://vstup.ukma.edu.ua/ai-eng",
            availability=db_enums.CertificateAvailability.AVAILABLE,
            hidden=False,
        )
        db.add_all([course, prog])
        db.flush()

        link = CertificateProgramCourse(program_id=prog.id, course_id=course.id, raw_title="ШІ для Інженерії")
        pref = PlanPreferences(
            student_id=42,
            academic_year=2026,
            wants_certificate=True,
            certificate_program_id=prog.id,
        )
        db.add_all([link, pref])
        db.commit()

        course_id = course.id
        prog_id = prog.id

    try:
        with session_factory()() as db:
            ctx = build_context(db, student_id=42, academic_year=2026)
            assert ctx.wants_certificate is True
            assert ctx.certificate_program_name == "Програма ШІ-Інженерії"
            assert course_id in ctx.certificate_course_ids

            prompt_text, _ = build_prompt(ctx)
            assert "Програма ШІ-Інженерії" in prompt_text
            assert str(course_id) in prompt_text
    finally:
        with session_factory()() as db:
            db.execute(delete(PlanPreferences).where(PlanPreferences.student_id == 42))
            db.execute(delete(CertificateProgramCourse).where(CertificateProgramCourse.program_id == prog_id))
            db.execute(delete(CertificateProgram).where(CertificateProgram.id == prog_id))
            db.execute(delete(Course).where(Course.id == course_id))
            db.commit()
