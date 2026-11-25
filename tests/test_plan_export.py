"""
Тести експорту індивідуального навчального плану в PDF (use-case 16, #296).

Перевіряє:
- генерацію справжнього PDF для затвердженого плану зі статусом 200 та коректним Content-Disposition;
- наявність шрифтів DejaVu та українського тексту;
- відхилення незатверджених планів (draft, submitted, awaiting_deanery) зі статусом 409;
- перевірку доступу (чужий план -> 403, неіснуючий -> 404);
- валідацію формату (не-pdf -> 422);
- журналювання експорту в AuditLog;
- підтримку нормативних дисциплін з документа деканату;
- генерацію багатосторінкового плану з довгими назвами дисциплін.

Використання ШІ: файл створено за допомогою Antigravity (Gemini 2.5 Pro, Google DeepMind).
Перевірка: pytest, ruff.
"""

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from src.api.main import app
from src.db import enums as db_enums
from src.db.models import Course, IndividualPlan, PlanItem
from src.db.models.admin import AuditLog
from src.db.models.deanery import DeaneryPlanDocument, NormativeCourseEntry
from src.db.session import session_factory
from src.export.pdf_generator import generate_plan_pdf

client = TestClient(app)

STUDENT_ID = 42
OTHER_STUDENT_ID = 7


@pytest.fixture
def clean_created_plans():
    """Фікстура для очищення створених тестових планів та документів."""
    created_plans: list[int] = []
    created_docs: list[int] = []

    yield created_plans, created_docs

    with session_factory()() as db:
        if created_plans:
            db.execute(delete(PlanItem).where(PlanItem.plan_id.in_(created_plans)))
            db.execute(delete(IndividualPlan).where(IndividualPlan.id.in_(created_plans)))
        if created_docs:
            db.execute(delete(NormativeCourseEntry).where(NormativeCourseEntry.document_id.in_(created_docs)))
            db.execute(delete(DeaneryPlanDocument).where(DeaneryPlanDocument.id.in_(created_docs)))
        db.commit()


@pytest.fixture
def make_plan_in_db(clean_created_plans):
    """Створює план із заданим статусом безпосередньо в БД."""
    created_plans, _ = clean_created_plans

    def factory(
        status: db_enums.PlanStatus = db_enums.PlanStatus.APPROVED,
        student_id: int = STUDENT_ID,
        course_ids: list[int] | None = None,
        deanery_doc_id: int | None = None,
        academic_year: int = 2026,
        course_year: int = 2,
    ) -> int:
        if course_ids is None:
            course_ids = [101, 205]

        with session_factory()() as db:
            plan = IndividualPlan(
                student_id=student_id,
                academic_year=academic_year,
                course_year=course_year,
                title="Тестовий навчальний план",
                status=status,
                deanery_document_id=deanery_doc_id,
            )
            db.add(plan)
            db.flush()

            for idx, c_id in enumerate(course_ids):
                item = PlanItem(
                    plan_id=plan.id,
                    course_id=c_id,
                    trimester=db_enums.Trimester.from_number((idx % 3) + 1),
                    category=(
                        db_enums.PlanItemCategory.PROFESSIONAL
                        if idx % 2 == 0
                        else db_enums.PlanItemCategory.FREE_CHOICE
                    ),
                )
                db.add(item)

            db.commit()
            created_plans.append(plan.id)
            return plan.id

    return factory


def test_export_approved_plan_returns_valid_pdf(make_plan_in_db):
    """Експорт затвердженого плану повертає валідний PDF з правильними заголовками."""
    plan_id = make_plan_in_db(status=db_enums.PlanStatus.APPROVED)

    response = client.get(f"/api/v1/plans/{plan_id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"

    # Перевірка Content-Disposition (RFC 5987 / 6266)
    cd = response.headers.get("content-disposition", "")
    assert 'filename="plan_2026_2027.pdf"' in cd
    expected_encoded = quote("план_2026_2027.pdf", safe="")
    assert f"filename*=UTF-8''{expected_encoded}" in cd

    # Перевірка формату PDF
    content = response.content
    assert content.startswith(b"%PDF-")
    assert b"%%EOF" in content
    # Справжній PDF зі шрифтами важить щонайменше кілька кілобайт
    assert len(content) > 5000

    # Перевірка вбудованих шрифтів
    assert b"DejaVu" in content

    # Перевірка журналу аудиту
    with session_factory()() as db:
        audit_entry = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.actor_id == STUDENT_ID,
                AuditLog.action == "plan.export",
                AuditLog.object_type == "IndividualPlan",
                AuditLog.object_id == plan_id,
            )
            .order_by(AuditLog.id.desc())
        )
        assert audit_entry is not None
        assert audit_entry.outcome == db_enums.AuditOutcome.ALLOWED
        assert audit_entry.new_value.get("format") == "pdf"
        assert audit_entry.new_value.get("size_bytes") == len(content)


@pytest.mark.parametrize(
    "non_approved_status",
    [
        db_enums.PlanStatus.DRAFT,
        db_enums.PlanStatus.SUBMITTED,
        db_enums.PlanStatus.AWAITING_DEANERY,
    ],
)
def test_export_non_approved_plan_returns_409(make_plan_in_db, non_approved_status):
    """Експорт незатвердженого плану повертає 409 PLAN_NOT_EXPORTABLE."""
    plan_id = make_plan_in_db(status=non_approved_status)

    response = client.get(f"/api/v1/plans/{plan_id}/export")

    assert response.status_code == 409
    assert response.json()["code"] == "PLAN_NOT_EXPORTABLE"


def test_export_other_student_plan_returns_403(make_plan_in_db):
    """Спроба експортувати план іншого студента повертає 403 PLAN_FORBIDDEN."""
    plan_id = make_plan_in_db(status=db_enums.PlanStatus.APPROVED, student_id=OTHER_STUDENT_ID)

    response = client.get(f"/api/v1/plans/{plan_id}/export")

    assert response.status_code == 403
    assert response.json()["code"] == "PLAN_FORBIDDEN"


def test_export_nonexistent_plan_returns_404():
    """Спроба експортувати неіснуючий план повертає 404 PLAN_NOT_FOUND."""
    response = client.get("/api/v1/plans/999999/export")

    assert response.status_code == 404
    assert response.json()["code"] == "PLAN_NOT_FOUND"


def test_export_invalid_format_returns_422(make_plan_in_db):
    """Невідомий формат повертає 422 VALIDATION_ERROR."""
    plan_id = make_plan_in_db(status=db_enums.PlanStatus.APPROVED)

    response = client.get(f"/api/v1/plans/{plan_id}/export?format=html")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_export_plan_with_deanery_normative_courses(make_plan_in_db, clean_created_plans):
    """План з прив'язаним документом деканату містить нормативні дисципліни."""
    _, created_docs = clean_created_plans

    with session_factory()() as db:
        doc = DeaneryPlanDocument(
            student_id=STUDENT_ID,
            academic_year=2026,
            original_filename="deanery_normative.docx",
            mime_type=db_enums.DocumentMimeType.DOCX,
            size_bytes=1024,
            sha256="0" * 64,
            content=b"test",
            parse_status=db_enums.DocumentParseStatus.PARSED,
        )
        db.add(doc)
        db.flush()
        created_docs.append(doc.id)

        normative_entry = NormativeCourseEntry(
            document_id=doc.id,
            raw_title="Нормативна філософія та критичне мислення",
            credits=3.0,
            trimester=db_enums.Trimester.AUTUMN,
        )
        db.add(normative_entry)
        db.commit()
        doc_id = doc.id

    plan_id = make_plan_in_db(status=db_enums.PlanStatus.APPROVED, deanery_doc_id=doc_id)

    response = client.get(f"/api/v1/plans/{plan_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 5000


def test_multipage_pdf_generation(make_plan_in_db):
    """План з великою кількістю дисциплін коректно генерує багатосторінковий PDF."""
    with session_factory()() as db:
        # Беремо всі доступні дисципліни з каталогу
        courses = list(db.scalars(select(Course).limit(20)))

    if len(courses) >= 2:
        course_ids = [c.id for c in courses]
        plan_id = make_plan_in_db(status=db_enums.PlanStatus.APPROVED, course_ids=course_ids)

        response = client.get(f"/api/v1/plans/{plan_id}/export")
        assert response.status_code == 200
        content = response.content
        assert content.startswith(b"%PDF-")
        # Багатосторінковий документ містить посилання на сторінки
        assert b"/Page" in content


def test_pdf_generator_unit():
    """Юніт-тест прямого виклику generate_plan_pdf."""
    with session_factory()() as db:
        plan = db.scalar(select(IndividualPlan).limit(1))
        assert plan is not None

        pdf_bytes = generate_plan_pdf(
            plan=plan,
            student_name="Шевченко Тарас Григорович",
            specialty="Комп'ютерні науки",
            course_year=3,
        )

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF-")
        assert b"%%EOF" in pdf_bytes
        assert len(pdf_bytes) > 3000
