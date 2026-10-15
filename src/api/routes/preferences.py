"""
Ресурс «Побажання» (Preferences): налаштування конструктора плану на навчальний рік (contract.md §3.2.3).

GET /preferences/{academic_year}, PUT /preferences/{academic_year} (створює або повністю замінює).
Список небажаних викладачів чутливий (R1): запити завжди фільтруються за власником, у LLM він не йде.
"""

from datetime import datetime
from typing import List, Optional, Type

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import enums as db_enums
from ...db.base import utcnow
from ...db.models.catalog import Direction, Instructor
from ...db.models.preferences import InstructorPreference, PlanPreferences, PreferenceDirection, TrimesterLoad
from ...db.models.users import StudentProfile
from ...db.session import get_db
from ..common import ApiError, ErrorDetail, error_responses
from ..onboarding import get_onboarded_student
from .plans import LoadLevels

router = APIRouter(prefix="/api/v1", tags=["Preferences"])

MAX_DIRECTIONS = 3  # FR-007
MAX_INSTRUCTOR_IDS = 50

_NOT_FOUND = ("PREFERENCES_NOT_FOUND", "Побажань на 2026 рік ще не збережено")
_ONBOARDING = ("ONBOARDING_REQUIRED", "Спершу вкажіть курс і спеціальність")


class PreferencesRequest(BaseModel):
    academic_year: Optional[int] = Field(
        None, ge=2024, le=2030, description="Необов'язково; якщо передано, має збігатися зі шляхом"
    )
    load_levels: LoadLevels = Field(
        default_factory=LoadLevels, description="Для 4 курсу ігнорується: рівні розраховує сервер (FR-003)"
    )
    direction_ids: List[int] = Field(default_factory=list, max_length=MAX_DIRECTIONS, description="0–3 напрямки")
    include_free_electives: bool = Field(True, description="false — лише профорієнтовні")
    preferred_instructor_ids: List[int] = Field(default_factory=list, max_length=MAX_INSTRUCTOR_IDS)
    unwanted_instructor_ids: List[int] = Field(default_factory=list, max_length=MAX_INSTRUCTOR_IDS)
    wants_certificate: bool = False
    certificate_program_id: Optional[int] = Field(None, gt=0, description="Етап 2: поки лише зберігається")


class PreferencesResponse(BaseModel):
    academic_year: int = Field(..., examples=[2026])
    load_levels: LoadLevels
    direction_ids: List[int]
    include_free_electives: bool
    preferred_instructor_ids: List[int]
    unwanted_instructor_ids: List[int]
    wants_certificate: bool
    certificate_program_id: Optional[int]
    updated_at: datetime


def _unique(ids: List[int]) -> List[int]:
    return list(dict.fromkeys(ids))


def _missing_ids(db: Session, model: Type, ids: List[int], field: str, code: str) -> List[ErrorDetail]:
    if not ids:
        return []
    found = set(db.scalars(select(model.id).where(model.id.in_(ids))))
    return [ErrorDetail(field=field, message=f"{code}: id {i} не існує") for i in ids if i not in found]


def _find(db: Session, student_id: int, academic_year: int) -> Optional[PlanPreferences]:
    return db.scalar(
        select(PlanPreferences).where(
            PlanPreferences.student_id == student_id, PlanPreferences.academic_year == academic_year
        )
    )


def _to_response(prefs: PlanPreferences) -> PreferencesResponse:
    loads = {row.trimester: row.load_level for row in prefs.trimester_loads}
    medium = db_enums.LoadLevel.MEDIUM
    return PreferencesResponse(
        academic_year=prefs.academic_year,
        load_levels=LoadLevels(
            autumn=loads.get(db_enums.Trimester.AUTUMN, medium).value,
            spring=loads.get(db_enums.Trimester.SPRING, medium).value,
            summer=loads.get(db_enums.Trimester.SUMMER, medium).value,
        ),
        direction_ids=sorted(d.direction_id for d in prefs.directions),
        include_free_electives=prefs.include_free_electives,
        preferred_instructor_ids=sorted(
            p.instructor_id
            for p in prefs.instructor_preferences
            if p.kind == db_enums.InstructorPreferenceKind.PREFERRED
        ),
        unwanted_instructor_ids=sorted(
            p.instructor_id
            for p in prefs.instructor_preferences
            if p.kind == db_enums.InstructorPreferenceKind.UNWANTED
        ),
        wants_certificate=prefs.wants_certificate,
        certificate_program_id=prefs.certificate_program_id,
        updated_at=prefs.updated_at,
    )


@router.get(
    "/preferences/{academic_year}",
    response_model=PreferencesResponse,
    summary="Збережені побажання на рік",
    description="404 `PREFERENCES_NOT_FOUND`, якщо побажань ще не збережено (фронтенд показує порожню форму).",
    responses={
        200: {"description": "Побажання отримано"},
        **error_responses(401, 404, 409, 422, overrides={404: _NOT_FOUND, 409: _ONBOARDING}),
    },
)
def get_preferences(
    academic_year: int = Path(..., ge=2024, le=2030, description="Рік початку навчального року", examples=[2026]),
    profile: StudentProfile = Depends(get_onboarded_student),
    db: Session = Depends(get_db),
):
    prefs = _find(db, profile.user_id, academic_year)
    if prefs is None:
        raise ApiError(404, "PREFERENCES_NOT_FOUND", f"Побажань на {academic_year} рік ще не збережено")
    return _to_response(prefs)


@router.put(
    "/preferences/{academic_year}",
    response_model=PreferencesResponse,
    summary="Зберегти побажання на рік",
    description=(
        "Створює або повністю замінює побажання. Напрямків 0–3; бажані й небажані викладачі не перетинаються, "
        "усі id мають існувати. Для 4 курсу `load_levels` ігноруються."
    ),
    responses={
        200: {"description": "Побажання збережено"},
        **error_responses(401, 409, 422, overrides={409: _ONBOARDING}),
    },
)
def save_preferences(
    payload: PreferencesRequest,
    academic_year: int = Path(..., ge=2024, le=2030, description="Рік початку навчального року", examples=[2026]),
    profile: StudentProfile = Depends(get_onboarded_student),
    db: Session = Depends(get_db),
):
    details: List[ErrorDetail] = []
    if payload.academic_year is not None and payload.academic_year != academic_year:
        details.append(
            ErrorDetail(field="academic_year", message="Значення в тілі не збігається з роком у шляху запиту")
        )

    direction_ids = _unique(payload.direction_ids)
    preferred = _unique(payload.preferred_instructor_ids)
    unwanted = _unique(payload.unwanted_instructor_ids)

    both = sorted(set(preferred) & set(unwanted))
    if both:
        details.append(
            ErrorDetail(
                field="unwanted_instructor_ids",
                message=f"INSTRUCTOR_IN_BOTH_LISTS: викладачі {both} не можуть бути і бажаними, і небажаними",
            )
        )
    details += _missing_ids(db, Direction, direction_ids, "direction_ids", "DIRECTION_NOT_FOUND")
    details += _missing_ids(db, Instructor, preferred, "preferred_instructor_ids", "INSTRUCTOR_NOT_FOUND")
    details += _missing_ids(db, Instructor, unwanted, "unwanted_instructor_ids", "INSTRUCTOR_NOT_FOUND")
    if details:
        raise ApiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", details)

    is_auto = profile.course_year == 4
    if is_auto:
        # TODO(команда): правило розрахунку рівнів для 4 курсу з залишку до 240 кредитів у контракті не описане
        levels = LoadLevels()
    else:
        levels = payload.load_levels

    prefs = _find(db, profile.user_id, academic_year)
    if prefs is None:
        prefs = PlanPreferences(student_id=profile.user_id, academic_year=academic_year)
        db.add(prefs)
    else:
        prefs.directions.clear()
        prefs.trimester_loads.clear()
        prefs.instructor_preferences.clear()
        db.flush()

    prefs.include_free_electives = payload.include_free_electives
    prefs.wants_certificate = payload.wants_certificate
    prefs.certificate_program_id = payload.certificate_program_id
    prefs.updated_at = utcnow()  
    prefs.directions = [PreferenceDirection(direction_id=i) for i in direction_ids]
    prefs.trimester_loads = [
        TrimesterLoad(
            trimester=db_enums.Trimester.AUTUMN, load_level=db_enums.LoadLevel(levels.autumn.value), is_auto=is_auto
        ),
        TrimesterLoad(
            trimester=db_enums.Trimester.SPRING, load_level=db_enums.LoadLevel(levels.spring.value), is_auto=is_auto
        ),
        TrimesterLoad(
            trimester=db_enums.Trimester.SUMMER, load_level=db_enums.LoadLevel(levels.summer.value), is_auto=is_auto
        ),
    ]
    prefs.instructor_preferences = [
        InstructorPreference(instructor_id=i, kind=db_enums.InstructorPreferenceKind.PREFERRED) for i in preferred
    ] + [InstructorPreference(instructor_id=i, kind=db_enums.InstructorPreferenceKind.UNWANTED) for i in unwanted]

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "CONFLICT", "Побажання на цей рік уже змінює інший запит, повторіть спробу")
    return _to_response(prefs)