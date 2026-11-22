"""
Тести для звірки дисциплін сертифікатних програм та розрахунку доступності (FR-013, AGENTS.md §4).

Використання ШІ: тести створено за допомогою Antigravity (Gemini 2.5 Pro).
Перевірка: pytest, ruff.
"""

from sqlalchemy import delete, select

from src.db import enums as db_enums
from src.db.models.catalog import CertificateProgram, CertificateProgramCourse, Course
from src.db.session import session_factory
from src.services.certificates import (
    recalculate_certificate_programs_availability,
    reconcile_certificate_course,
)


def test_reconcile_exact_and_normalized_match():
    """Точний збіг назв з урахуванням регістру та апострофів."""
    with session_factory()() as db:
        course = Course(
            saz_code="TEST-REC-101",
            title="Комп'ютерні мережі",
            title_normalized="комп'ютерні мережі",
            credits=5.0,
            trimester=db_enums.Trimester.AUTUMN,
            recommended_year=2,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        db.add(course)
        db.commit()
        course_id = course.id

        try:
            # Різний регістр і апостроф
            cid, status = reconcile_certificate_course(db, "Компʼютерні Мережі")
            assert status == "matched"
            assert cid == course_id

            # Збіг із зайвими пробілами
            cid2, status2 = reconcile_certificate_course(db, "  комп'ютерні   мережі  ")
            assert status2 == "matched"
            assert cid2 == course_id
        finally:
            db.execute(delete(Course).where(Course.id == course_id))
            db.commit()


def test_reconcile_fuzzy_match_is_ambiguous_not_matched():
    """Неоднозначні та схожі (fuzzy) збіги не приймаються автоматично."""
    with session_factory()() as db:
        course = Course(
            saz_code="TEST-REC-102",
            title="Основи машинного навчання",
            title_normalized="основи машинного навчання",
            credits=4.0,
            trimester=db_enums.Trimester.SPRING,
            recommended_year=3,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        db.add(course)
        db.commit()
        course_id = course.id

        try:
            # Схожа назва, але не точний нормалізований збіг
            cid, status = reconcile_certificate_course(db, "Машинне навчання")
            assert status == "ambiguous"
            assert cid is None
        finally:
            db.execute(delete(Course).where(Course.id == course_id))
            db.commit()


def test_reconcile_unpublished_course_not_found():
    """Неопубліковані або архівовані дисципліни САЗ не доступні для звірки."""
    with session_factory()() as db:
        course = Course(
            saz_code="TEST-REC-103",
            title="Стара архітектура",
            title_normalized="стара архітектура",
            credits=3.0,
            trimester=db_enums.Trimester.AUTUMN,
            recommended_year=4,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.ARCHIVED,
        )
        db.add(course)
        db.commit()
        course_id = course.id

        try:
            cid, status = reconcile_certificate_course(db, "Стара архітектура")
            assert status == "not_found"
            assert cid is None
        finally:
            db.execute(delete(Course).where(Course.id == course_id))
            db.commit()


def test_program_availability_calculation():
    """
    Програма доступна (AVAILABLE) лише тоді, коли ВСІ її дисципліни звірені з опублікованими курсами.
    Якщо хоча б 1 дисципліна відсутня -> UNAVAILABLE.
    """
    with session_factory()() as db:
        c1 = Course(
            saz_code="TEST-PROG-1",
            title="Дисципліна А",
            title_normalized="дисципліна а",
            credits=4.0,
            trimester=db_enums.Trimester.AUTUMN,
            recommended_year=2,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        c2 = Course(
            saz_code="TEST-PROG-2",
            title="Дисципліна Б",
            title_normalized="дисципліна б",
            credits=4.0,
            trimester=db_enums.Trimester.SPRING,
            recommended_year=2,
            kind=db_enums.CourseKind.ELECTIVE,
            publication_status=db_enums.PublicationStatus.PUBLISHED,
        )
        db.add_all([c1, c2])
        db.flush()

        program = CertificateProgram(
            title="Тестова сертифікатна програма",
            source_url="https://vstup.ukma.edu.ua/test-prog",
            availability=db_enums.CertificateAvailability.UNAVAILABLE,
        )
        db.add(program)
        db.flush()

        item1 = CertificateProgramCourse(program_id=program.id, course_id=c1.id, raw_title="Дисципліна А")
        # Другий елемент без прив'язки
        item2 = CertificateProgramCourse(program_id=program.id, course_id=None, raw_title="Дисципліна Б")
        db.add_all([item1, item2])
        db.commit()

        prog_id = program.id
        c1_id = c1.id
        c2_id = c2.id

        try:
            # 1. Поки item2 не звірено -> UNAVAILABLE
            recalculate_certificate_programs_availability(db)
            db.commit()
            p = db.get(CertificateProgram, prog_id)
            assert p.availability == db_enums.CertificateAvailability.UNAVAILABLE

            # 2. Звіряємо item2 -> стає AVAILABLE
            item2 = db.scalars(
                select(CertificateProgramCourse).where(
                    CertificateProgramCourse.program_id == prog_id,
                    CertificateProgramCourse.course_id.is_(None),
                )
            ).first()
            item2.course_id = c2_id
            db.flush()

            recalculate_certificate_programs_availability(db)
            db.commit()
            p = db.get(CertificateProgram, prog_id)
            assert p.availability == db_enums.CertificateAvailability.AVAILABLE

            # 3. Депублікуємо (архівуємо) c1 -> програма знову автоматично стає UNAVAILABLE!
            c1_db = db.get(Course, c1_id)
            c1_db.publication_status = db_enums.PublicationStatus.ARCHIVED
            db.flush()

            recalculate_certificate_programs_availability(db)
            db.commit()
            p = db.get(CertificateProgram, prog_id)
            assert p.availability == db_enums.CertificateAvailability.UNAVAILABLE
        finally:
            db.execute(delete(CertificateProgramCourse).where(CertificateProgramCourse.program_id == prog_id))
            db.execute(delete(CertificateProgram).where(CertificateProgram.id == prog_id))
            db.execute(delete(Course).where(Course.id.in_([c1_id, c2_id])))
            db.commit()
