"""
Усі моделі БД. Імпорт цього пакета реєструє таблиці в Base.metadata (потрібно Alembic).

Сутності етапу 2 (AI-генерація, альтернативи, сертифікатні програми) ще не додано: contract.md §3.7–3.8 (🔵).

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: `alembic check`, pytest.
"""

from .admin import AuditLog, ModerationItem, SyncJob
from .catalog import Course, CourseDirection, CourseInstructor, Direction, Instructor
from .deanery import DeaneryPlanDocument, NormativeCourseEntry
from .history import AcademicRecord
from .plans import IndividualPlan, PlanItem
from .preferences import InstructorPreference, PlanPreferences, PreferenceDirection, TrimesterLoad
from .users import RefreshToken, StudentProfile, User
from . import ai  # noqa: F401

__all__ = [
    "AcademicRecord",
    "AuditLog",
    "Course",
    "CourseDirection",
    "CourseInstructor",
    "DeaneryPlanDocument",
    "Direction",
    "IndividualPlan",
    "Instructor",
    "InstructorPreference",
    "ModerationItem",
    "NormativeCourseEntry",
    "PlanItem",
    "PlanPreferences",
    "PreferenceDirection",
    "RefreshToken",
    "StudentProfile",
    "SyncJob",
    "TrimesterLoad",
    "User",
]
