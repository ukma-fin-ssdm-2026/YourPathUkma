"""
Адмінка: сертифікатні програми (contract.md §3.9).

PATCH /admin/certificate-programs/{program_id}, 
PUT /admin/certificate-programs/{program_id}/courses/{entry_id}.

Інші кінцеві точки для сертифікатних програм — у certificates.py.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db import enums as db_enums
from ....db.models.catalog import CertificateProgram, CertificateProgramCourse, Direction
from ....db.session import get_db
from ...common import ApiError, error_responses
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
    direction_ids: Optional[List[int]] = Field(None, min_length=1, description="Повна заміна переліку напрямків")
    hidden: Optional[bool] = Field(None, description="Приховати програму від студентів")


class CertificateEntryUpdate(BaseModel):
    course_id: Optional[int] = Field(None, gt=0, description="ID дисципліни з каталогу; null скасовує звірку")


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
    program_id: int = Path(..., gt=0, examples=[3]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    program = db.get(CertificateProgram, program_id)
    if not program:
        raise ApiError(404, *_PROGRAM_NOT_FOUND)

    old, new = {}, {}
    if payload.direction_ids is not None:
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
    program_id: int = Path(..., gt=0, examples=[3]),
    entry_id: int = Path(..., gt=0, examples=[501]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    program = db.get(CertificateProgram, program_id)
    if not program:
        raise ApiError(404, *_PROGRAM_NOT_FOUND)
    entry = db.get(CertificateProgramCourse, entry_id)
    if not entry or entry.program_id != program_id:
        raise ApiError(404, *_ENTRY_NOT_FOUND)

    old_course_id = entry.course_id
    entry.course_id = payload.course_id
    program.availability = db_enums.CertificateAvailability.AVAILABLE

    write_audit(
        db,
        actor_id=admin.id,
        action="certificate_program.match",
        object_type="CertificateProgramCourse",
        object_id=entry.id,
        old_value={"course_id": old_course_id},
        new_value={"course_id": payload.course_id},
        ip=client_ip(request),
    )
    db.commit()
    return {"status": "ok"}
