"""
Ресурс «Сертифікатні програми» (Certificate programs): перелік і звірка з каталогом (contract.md §3.8).

GET /certificate-programs, GET /certificate-programs/{program_id}.

Дані надходять через синхронізацію (SyncJob з source=faculty_certificates). Адмінські кінцеві точки —
у admin/catalog.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import enums as db_enums
from ...db.models.catalog import CertificateProgram, CertificateProgramCourse
from ...db.session import get_db
from ..common import ApiError, error_responses, get_current_student_id

router = APIRouter(prefix="/api/v1", tags=["Certificate programs"])


class CertificateProgramResponse(BaseModel):
    id: int = Field(..., examples=[3])
    title: str = Field(..., examples=["Data Engineering"])
    source_url: str = Field(..., description="Посилання на сторінку програми")
    availability: db_enums.CertificateAvailability = Field(..., description="Доступність програми в цьому році")
    direction_ids: List[int] = Field(..., description="ID напрямків, до яких прив'язано програму")
    course_count: int = Field(..., description="Кількість дисциплін у програмі")


class CertificateProgramDetail(CertificateProgramResponse):
    courses: List[dict] = Field(
        ...,
        description="Дисципліни програми зі статусом звірки з каталогом",
        examples=[
            {"raw_title": "Бази даних", "course_id": 120, "match_status": "matched"},
            {"raw_title": "Хмарні обчислення", "course_id": None, "match_status": "not_found"},
        ],
    )


@router.get(
    "/certificate-programs",
    response_model=List[CertificateProgramResponse],
    summary="Сертифікатні програми",
    description="Програми, які адмін не приховав (hidden=false). Фільтр за direction_id.",
    responses={200: {"description": "Список отримано"}, **error_responses(401, 422)},
)
def list_certificate_programs(
    direction_id: Optional[int] = Query(None, gt=0, description="Фільтр за ID напрямку"),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    query = select(CertificateProgram).where(CertificateProgram.hidden == False)
    if direction_id:
        query = query.where(CertificateProgram.direction_ids.any(direction_id))
    programs = db.scalars(query.order_by(CertificateProgram.title)).all()
    return [
        CertificateProgramResponse(
            id=p.id,
            title=p.title,
            source_url=p.source_url,
            availability=p.availability,
            direction_ids=p.direction_ids,
            course_count=len(p.courses),
        )
        for p in programs
    ]


@router.get(
    "/certificate-programs/{program_id}",
    response_model=CertificateProgramDetail,
    summary="Деталі сертифікатної програми",
    description="Програма зі списком дисциплін і статусом їх звірки з каталогом.",
    responses={
        200: {"description": "Програму знайдено"},
        **error_responses(401, 404, 422, overrides={404: ("CERTIFICATE_PROGRAM_NOT_FOUND", "Програми з ID 3 не знайдено")}),
    },
)
def get_certificate_program(
    program_id: int = Path(..., gt=0, examples=[3]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    program = db.get(CertificateProgram, program_id)
    if not program or program.hidden:
        raise ApiError(404, "CERTIFICATE_PROGRAM_NOT_FOUND", f"Програми з ID {program_id} не знайдено")
    return CertificateProgramDetail(
        id=program.id,
        title=program.title,
        source_url=program.source_url,
        availability=program.availability,
        direction_ids=program.direction_ids,
        course_count=len(program.courses),
        courses=[
            {
                "raw_title": c.raw_title,
                "course_id": c.course_id,
                "match_status": "matched" if c.course_id else "not_found",
            }
            for c in program.courses
        ],
    )
