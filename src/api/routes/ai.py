"""
Ресурс «AI-генерація» (AI generation): створення плану за побажаннями (contract.md §3.7).

POST /plan-generations, GET /plan-generations/{generation_id}.

Генерація асинхронна (R10): запит повертає 202, фронтенд опитує статус. Ліміт: 1 активна генерація
на студента, 20 на добу (R10).
"""

import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db import enums as db_enums
from ...db.models.ai import PlanGeneration
from ...db.models.users import StudentProfile
from ...db.session import get_db
from ..common import ApiError, error_responses, get_current_student_id
from ..onboarding import get_onboarded_student
from .preferences import PreferencesRequest

router = APIRouter(prefix="/api/v1", tags=["AI generation"])

_GENERATION_NOT_FOUND = ("GENERATION_NOT_FOUND", "Генерації з ID 77 не знайдено")
_GENERATION_IN_PROGRESS = ("GENERATION_IN_PROGRESS", "Вже виконується генерація плану")
_RATE_LIMITED = ("RATE_LIMITED", "Досягнуто ліміт генерацій (20 за добу)")


class GenerationNotice(BaseModel):
    code: str = Field(..., examples=["UNWANTED_INSTRUCTOR_UNAVOIDABLE"])
    message: str = Field(..., examples=["Дисципліну X викладає лише обраний вами небажаний викладач"])
    course_id: Optional[int] = Field(None, examples=[140])


class PlanGenerationResponse(BaseModel):
    id: int = Field(..., examples=[77])
    status: db_enums.GenerationStatus = Field(..., examples=["pending"])
    plan_id: Optional[int] = Field(None, examples=[9])
    notices: List[GenerationNotice] = Field(default_factory=list)
    error: Optional[str] = Field(None, description="Помилка, якщо status=failed")
    created_at: datetime = Field(..., examples=["2026-10-08T10:00:00Z"])
    finished_at: Optional[datetime] = Field(None, examples=["2026-10-08T10:01:12Z"])


@router.post(
    "/plan-generations",
    response_model=PlanGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустити AI-генерацію плану",
    description="Створює задачу зі статусом `pending`. Фронтенд опитує GET /plan-generations/{id}.",
    responses={
        202: {"description": "Генерацію запущено"},
        **error_responses(
            401,
            409,
            422,
            429,
            overrides={
                409: _GENERATION_IN_PROGRESS,
                429: _RATE_LIMITED,
            },
        ),
    },
)
def start_generation(
    payload: PreferencesRequest,
    response: Response,
    profile: StudentProfile = Depends(get_onboarded_student),
    db: Session = Depends(get_db),
):
    # Перевірка активних генерацій
    active = db.scalar(
        select(PlanGeneration.id).where(
            PlanGeneration.student_id == profile.user_id,
            PlanGeneration.status == db_enums.GenerationStatus.PENDING,
        )
    )
    if active:
        raise ApiError(409, *_GENERATION_IN_PROGRESS)

    # Перевірка ліміту 20/добу
    since = int(time.time()) - 24 * 3600
    recent = db.scalar(
        select(func.count()).where(
            PlanGeneration.student_id == profile.user_id,
            PlanGeneration.created_at >= datetime.fromtimestamp(since),
        )
    )
    if recent >= 20:
        raise ApiError(429, *_RATE_LIMITED)

    # Створення задачі генерації
    generation = PlanGeneration(
        student_id=profile.user_id,
        academic_year=payload.academic_year,
        status=db_enums.GenerationStatus.PENDING,
    )
    db.add(generation)
    db.commit()
    db.refresh(generation)

    response.headers["Location"] = f"/api/v1/plan-generations/{generation.id}"
    return PlanGenerationResponse(
        id=generation.id,
        status=generation.status,
        plan_id=generation.plan_id,
        notices=[],
        created_at=generation.created_at,
    )


@router.get(
    "/plan-generations/{generation_id}",
    response_model=PlanGenerationResponse,
    summary="Статус AI-генерації",
    description="Фронтенд опитує, доки статус `pending`. При `succeeded` є `plan_id` нового плану.",
    responses={
        200: {"description": "Статус отримано"},
        **error_responses(401, 404, 422, overrides={404: _GENERATION_NOT_FOUND}),
    },
)
def get_generation_status(
    generation_id: int = Path(..., gt=0, examples=[77]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    generation = db.get(PlanGeneration, generation_id)
    if not generation or generation.student_id != student_id:
        raise ApiError(404, *_GENERATION_NOT_FOUND)

    notices = [GenerationNotice(code=n.code, message=n.message, course_id=n.course_id) for n in generation.notices]
    return PlanGenerationResponse(
        id=generation.id,
        status=generation.status,
        plan_id=generation.plan_id,
        notices=notices,
        error=generation.error_message,
        created_at=generation.created_at,
        finished_at=generation.finished_at,
    )
