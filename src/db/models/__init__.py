"""
Усі моделі БД. Імпорт цього пакета реєструє таблиці в Base.metadata (потрібно Alembic).

Використання ШІ: файл створено за допомогою Claude (Claude Code); оновлено за допомогою
Antigravity (Claude Sonnet 4.6, Google DeepMind) — додано PlanAlternative (FR-009).
Перевірка: `alembic check`, pytest.
"""

from . import ai  # noqa: F401
from .admin import AuditLog, ModerationItem, SyncJob
from .alternatives import PlanAlternative
from .catalog import Course, CourseDirection, CourseInstructor, Direction, Instructor
from .deanery import DeaneryPlanDocument, NormativeCourseEntry
from .history import AcademicRecord
from .plans import IndividualPlan, PlanItem
from .preferences import InstructorPreference, PlanPreferences, PreferenceDirection, TrimesterLoad
from .users import RefreshToken, StudentProfile, User

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
    "PlanAlternative",
    "PlanItem",
    "PlanPreferences",
    "PreferenceDirection",
    "RefreshToken",
    "StudentProfile",
    "SyncJob",
    "TrimesterLoad",
    "User",
]
