"""
Залежність для маршрутів, яким потрібен завершений онбординг (contract.md §3.2).

Поки студент не вказав курс і спеціальність, планові кінцеві точки, побажання та історія
повертають 409 ONBOARDING_REQUIRED.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from ..db.models.users import StudentProfile
from ..db.session import get_db
from .common import ApiError, get_current_student_id


def get_onboarded_student(
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
) -> StudentProfile:
    profile = db.get(StudentProfile, student_id)
    if profile is None or profile.course_year is None or not profile.specialty:
        raise ApiError(409, "ONBOARDING_REQUIRED", "Спершу вкажіть курс і спеціальність (POST /api/v1/me/onboarding)")
    return profile