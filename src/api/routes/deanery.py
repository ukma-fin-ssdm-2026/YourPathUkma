"""
Ресурс «Документи деканату» (Deanery documents): завантаження та перегляд (contract.md §3.6).

Запускається після відповіді 202 на POST /deanery-documents фоновий парсинг.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Path, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import enums as db_enums
from ...db.base import normalize_text, utcnow
from ...db.models import IndividualPlan
from ...db.models.catalog import Course
from ...db.models.deanery import DeaneryPlanDocument, NormativeCourseEntry
from ...db.models.history import AcademicRecord
from ...db.models.users import StudentProfile
from ...db.session import get_db, session_factory
from ..common import ApiError, error_responses, get_current_student_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/deanery-documents", tags=["Deanery documents"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class NormativeCourseResponse(BaseModel):
    course_id: Optional[int] = Field(None, description="null, якщо не знайдено в каталозі")
    raw_title: str
    trimester: int
    credits: float


class DeaneryDocumentResponse(BaseModel):
    id: int
    academic_year: int
    original_filename: str
    mime_type: str
    size_bytes: int
    parse_status: str
    parse_error: Optional[str] = None
    uploaded_at: datetime
    normative_courses: Optional[List[NormativeCourseResponse]] = None


class DeaneryDocumentsListResponse(BaseModel):
    deanery_documents: List[DeaneryDocumentResponse]


@dataclass(frozen=True)
class ParsedCourse:
    raw_title: str
    trimester: int  # 1–3
    credits: float  # > 0


def extract_courses(content: bytes, mime_type: db_enums.DocumentMimeType) -> List[ParsedCourse]:
    """Витягує нормативні дисципліни з PDF/DOCX. Повертає список; для нерозпізнаного файлу кидає виняток."""
    raise NotImplementedError("Розпізнавання документа деканату ще не реалізовано")


def current_academic_year(today: Optional[date] = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1


def _mark_failed(db: Session, document_id: int, message: str) -> None:
    document = db.get(DeaneryPlanDocument, document_id)
    if document is not None:
        document.parse_status = db_enums.DocumentParseStatus.FAILED
        document.parse_error = message[:1000]
        db.commit()


def _store_courses(db: Session, document: DeaneryPlanDocument, parsed: List[ParsedCourse]) -> None:
    valid = [p for p in parsed if p.raw_title.strip() and 1 <= p.trimester <= 3 and p.credits > 0]

    titles = {normalize_text(p.raw_title) for p in valid}
    catalog = {}
    if titles:
        for course in db.scalars(
            select(Course)
            .where(
                Course.title_normalized.in_(titles),
                Course.publication_status == db_enums.PublicationStatus.PUBLISHED,
            )
            .order_by(Course.id)
        ):
            catalog.setdefault(course.title_normalized, course)

    document.normative_courses = [
        NormativeCourseEntry(
            course_id=(catalog[normalize_text(p.raw_title)].id if normalize_text(p.raw_title) in catalog else None),
            raw_title=p.raw_title.strip()[:300],
            credits=p.credits,
            trimester=db_enums.Trimester.from_number(p.trimester),
        )
        for p in valid
    ]
    document.parse_status = db_enums.DocumentParseStatus.PARSED
    document.parse_error = None

    _add_history(db, document, valid, catalog)


def _add_history(db: Session, document: DeaneryPlanDocument, parsed: List[ParsedCourse], catalog: dict) -> None:
    this_year = current_academic_year()
    if document.academic_year >= this_year:
        return
    profile = db.get(StudentProfile, document.student_id)
    if profile is None or profile.course_year is None:
        return
    course_year = profile.course_year - (this_year - document.academic_year)
    if not 1 <= course_year <= 4:
        return

    taken = set(
        db.scalars(
            select(AcademicRecord.course_id).where(
                AcademicRecord.student_id == document.student_id, AcademicRecord.course_id.is_not(None)
            )
        )
    )
    for p in parsed:
        course = catalog.get(normalize_text(p.raw_title))
        if course is not None:
            if course.id in taken:
                continue
            taken.add(course.id)
        db.add(
            AcademicRecord(
                student_id=document.student_id,
                academic_year=document.academic_year,
                course_year=course_year,
                course_id=course.id if course is not None else None,
                title=(course.title if course is not None else p.raw_title.strip())[:300],
                credits=p.credits,
                trimester=db_enums.Trimester.from_number(p.trimester),
                category=db_enums.AcademicCategory.NORMATIVE,
                source=db_enums.RecordSource.DEANERY_DOCUMENT,
                verified=False,
                document_id=document.id,
            )
        )


def process_document(document_id: int) -> None:
    with session_factory()() as db:
        document = db.get(DeaneryPlanDocument, document_id)
        if document is None:
            return
        try:
            parsed = extract_courses(document.content, document.mime_type)
            _store_courses(db, document, parsed)
            db.commit()
        except NotImplementedError as exc:
            db.rollback()
            _mark_failed(db, document_id, str(exc))
        except Exception:
            logger.exception("Не вдалося опрацювати документ деканату %s", document_id)
            db.rollback()
            _mark_failed(db, document_id, "Не вдалося розпізнати документ")


def _to_response(doc: DeaneryPlanDocument) -> DeaneryDocumentResponse:
    courses = None
    if doc.normative_courses:
        courses = [
            NormativeCourseResponse(
                course_id=nc.course_id,
                raw_title=nc.raw_title,
                trimester=nc.trimester.number,
                credits=nc.credits,
            )
            for nc in doc.normative_courses
        ]
    return DeaneryDocumentResponse(
        id=doc.id,
        academic_year=doc.academic_year,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type.value,
        size_bytes=doc.size_bytes,
        parse_status=doc.parse_status.value,
        parse_error=doc.parse_error,
        uploaded_at=doc.uploaded_at,
        normative_courses=courses,
    )


@router.post(
    "",
    response_model=DeaneryDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Завантажити документ деканату",
    description="Приймає PDF або DOCX до 10 МБ. Відповідь 202, розпізнавання асинхронне.",
    responses={
        202: {"description": "Документ прийнято на обробку"},
        **error_responses(
            401,
            413,
            415,
            422,
            overrides={
                413: ("FILE_TOO_LARGE", "Файл більший за 10 МБ"),
                415: ("UNSUPPORTED_FILE_TYPE", "Не PDF і не DOCX"),
            },
        ),
    },
)
async def upload_document(
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    academic_year: int = Form(..., ge=2024, le=2030),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    content = await file.read()
    size = len(content)

    if size > MAX_UPLOAD_BYTES:
        raise ApiError(413, "FILE_TOO_LARGE", "Файл більший за 10 МБ")

    mime_map = {
        "application/pdf": db_enums.DocumentMimeType.PDF,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": db_enums.DocumentMimeType.DOCX,
        "application/msword": db_enums.DocumentMimeType.DOCX,
    }

    doc_mime = mime_map.get(file.content_type)
    if not doc_mime:
        if file.filename and file.filename.endswith(".pdf"):
            doc_mime = db_enums.DocumentMimeType.PDF
        elif file.filename and file.filename.endswith(".docx"):
            doc_mime = db_enums.DocumentMimeType.DOCX
        else:
            raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Дозволені лише файли PDF та DOCX")

    doc = DeaneryPlanDocument(
        student_id=student_id,
        academic_year=academic_year,
        original_filename=file.filename or "document",
        mime_type=doc_mime,
        size_bytes=size,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        parse_status=db_enums.DocumentParseStatus.PENDING,
        uploaded_at=utcnow(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(process_document, doc.id)

    response.headers["Location"] = f"/api/v1/deanery-documents/{doc.id}"
    return _to_response(doc)


@router.get(
    "",
    response_model=DeaneryDocumentsListResponse,
    summary="Отримати всі документи студента",
)
def list_documents(
    academic_year: Optional[int] = Query(None, description="Фільтр за навчальним роком"),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    query = select(DeaneryPlanDocument).where(DeaneryPlanDocument.student_id == student_id)
    if academic_year:
        query = query.where(DeaneryPlanDocument.academic_year == academic_year)

    docs = db.scalars(query.order_by(DeaneryPlanDocument.uploaded_at.desc())).all()
    return DeaneryDocumentsListResponse(deanery_documents=[_to_response(d) for d in docs])


@router.get(
    "/{document_id}",
    response_model=DeaneryDocumentResponse,
    summary="Отримати документ та розпізнані дисципліни",
    responses={200: {"description": "Документ знайдено"}, **error_responses(401, 404)},
)
def get_document(
    document_id: int = Path(...),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    doc = db.get(DeaneryPlanDocument, document_id)
    if not doc or doc.student_id != student_id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "Документ не знайдено")
    return _to_response(doc)


@router.get(
    "/{document_id}/file",
    summary="Завантажити оригінальний файл",
    responses={200: {"description": "Файл"}, **error_responses(401, 404)},
)
def download_document_file(
    document_id: int = Path(...),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    doc = db.get(DeaneryPlanDocument, document_id)
    if not doc or doc.student_id != student_id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "Документ не знайдено")

    media_type = (
        "application/pdf"
        if doc.mime_type == db_enums.DocumentMimeType.PDF
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    return Response(
        content=doc.content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}"'},
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити документ",
    responses={204: {"description": "Документ видалено"}, **error_responses(401, 404, 409)},
)
def delete_document(
    document_id: int = Path(...),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    doc = db.get(DeaneryPlanDocument, document_id)
    if not doc or doc.student_id != student_id:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "Документ не знайдено")

    # Перевіряємо, чи документ не прив'язаний до активних/використовуваних планів (DOCUMENT_IN_USE)
    used_in_plans = db.scalar(
        select(IndividualPlan.id).where(IndividualPlan.deanery_document_id == document_id).limit(1)
    )
    if used_in_plans is not None:
        raise ApiError(
            409, "DOCUMENT_IN_USE", "Неможливо видалити документ, оскільки він прив'язаний до навчального плану"
        )

    db.delete(doc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
