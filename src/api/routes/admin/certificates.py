"""
Адмінка: сертифікатні програми (contract.md §3.9).

PATCH /admin/certificate-programs/{program_id},
PUT /admin/certificate-programs/{program_id}/courses/{entry_id}.

Інші кінцеві точки для сертифікатних програм — у certificates.py.

Використання ШІ: додано каскадний перерахунок доступності сертифікатних програм через
recalculate_certificate_programs_availability за допомогою Antigravity (Gemini 2.5 Pro). Перевірка: pytest, ruff.
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db import enums as db_enums
from ....db.models.catalog import CertificateProgram, CertificateProgramCourse, Course, Direction
from ....db.models.users import User
from ....db.session import get_db
from ....services.certificates import recalculate_certificate_programs_availability
from ...common import MAX_DATABASE_ID, ApiError, error_responses
from .common import client_ip, require_admin, write_audit

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

_FORBIDDEN = ("FORBIDDEN_ROLE", "Потрібна роль адміністратора")
_PROGRAM_NOT_FOUND = ("CERTIFICATE_PROGRAM_NOT_FOUND", "Сертифікатної програми з ID 3 не знайдено")
_ENTRY_NOT_FOUND = ("CERTIFICATE_ENTRY_NOT_FOUND", "Запису програми з ID 501 не знайдено")


class CertificateProgramPatch(BaseModel):
    direction_ids: Optional[List[Annotated[int, Field(gt=0, le=MAX_DATABASE_ID)]]] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Повна заміна переліку унікальних напрямків",
        json_schema_extra={"uniqueItems": True},
    )
    hidden: Optional[bool] = Field(None, description="Приховати програму від студентів")

    @field_validator("direction_ids")
    @classmethod
    def validate_unique_directions(cls, ids: Optional[List[int]]) -> Optional[List[int]]:
        if ids is not None and len(set(ids)) != len(ids):
            raise ValueError("ID напрямків мають бути унікальними")
        return ids


class CertificateEntryUpdate(BaseModel):
    course_id: Optional[int] = Field(
        None, gt=0, le=MAX_DATABASE_ID, description="ID дисципліни з каталогу; null скасовує звірку"
    )


@router.patch(
    "/certificate-programs/{program_id}",
    summary="Змінити сертифікатну програму",
    description="Прив'язка до напрямків і прапорець hidden. Усі поля необов'язкові.",
    responses={
        200: {"description": "Програму оновлено"},
        **error_responses(
            401,
            403,
            404,
            422,
            overrides={403: _FORBIDDEN, 404: _PROGRAM_NOT_FOUND},
        ),
    },
)
def patch_certificate_program(
    payload: CertificateProgramPatch,
    request: Request,
    program_id: int = Path(..., gt=0, le=MAX_DATABASE_ID, examples=[3]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    program = db.get(CertificateProgram, program_id)
    if not program:
        raise ApiError(404, *_PROGRAM_NOT_FOUND)

    old, new = {}, {}
    if payload.direction_ids is not None:
        found = set(db.scalars(select(Direction.id).where(Direction.id.in_(payload.direction_ids))))
        if found != set(payload.direction_ids):
            raise ApiError(422, "DIRECTION_NOT_FOUND", "Один або кілька напрямків не існують")
        old["direction_ids"], new["direction_ids"] = program.direction_ids, payload.direction_ids
        program.direction_ids = payload.direction_ids
    if payload.hidden is not None:
        old["hidden"], new["hidden"] = program.hidden, payload.hidden
        program.hidden = payload.hidden

    if new:
        write_audit(
            db,
            actor_id=admin.id,
            action="certificate_program.update",
            object_type="CertificateProgram",
            object_id=program.id,
            old_value=old,
            new_value=new,
            ip=client_ip(request),
        )
        db.commit()
    return {"status": "ok"}


@router.put(
    "/certificate-programs/{program_id}/courses/{entry_id}",
    summary="Вручну звірити запис програми з каталогом",
    description="Якщо автоматична звірка не знайшла дисципліну, адмін може вказати її вручну.",
    responses={
        200: {"description": "Звірку оновлено"},
        **error_responses(
            401,
            403,
            404,
            422,
            overrides={403: _FORBIDDEN, 404: (_PROGRAM_NOT_FOUND, _ENTRY_NOT_FOUND)},
        ),
    },
)
def update_certificate_entry(
    payload: CertificateEntryUpdate,
    request: Request,
    program_id: int = Path(..., gt=0, le=MAX_DATABASE_ID, examples=[3]),
    entry_id: int = Path(..., gt=0, le=MAX_DATABASE_ID, examples=[501]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    # Використання ШІ: Codex серіалізував звірку записів однієї програми.
    # Перевірка: сценарії звірки на PostgreSQL.
    program = db.get(CertificateProgram, program_id, with_for_update=True)
    if not program:
        raise ApiError(404, *_PROGRAM_NOT_FOUND)
    entry = db.get(CertificateProgramCourse, entry_id)
    if not entry or entry.program_id != program_id:
        raise ApiError(404, *_ENTRY_NOT_FOUND)

    if payload.course_id is not None:
        course = db.get(Course, payload.course_id, with_for_update={"read": True})
        if course is None or course.publication_status != db_enums.PublicationStatus.PUBLISHED:
            raise ApiError(422, "COURSE_NOT_PUBLISHED", "Дисципліна має існувати й бути опублікованою")

    old_course_id = entry.course_id
    old_availability = program.availability
    entry.course_id = payload.course_id
    db.flush()
    # Доступність виводимо з усіх записів програми та актуального каталогу
    recalculate_certificate_programs_availability(db)

    write_audit(
        db,
        actor_id=admin.id,
        action="certificate_program.match",
        object_type="CertificateProgramCourse",
        object_id=entry.id,
        old_value={"course_id": old_course_id, "availability": old_availability.value},
        new_value={"course_id": payload.course_id, "availability": program.availability.value},
        ip=client_ip(request),
    )
    db.commit()
    return {"status": "ok"}
