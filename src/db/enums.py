"""
Перелічення, що зберігаються в БД. Значення збігаються з API (contract.md §2.1); винятки описано біля типу.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: звірка з contract.md §2.1
і data-model.md, pytest.
"""

from enum import Enum


class UserRole(str, Enum):
    STUDENT = "student"
    ADMIN = "admin"


class CourseYearSource(str, Enum):
    SELF_DECLARED = "self_declared"
    ADMIN = "admin"
    SAZ_SYNC = "saz_sync"


class Trimester(str, Enum):
    """У БД — назва (data-model.md), в API — число 1–3 (contract.md §6, розбіжність 3)."""

    AUTUMN = "autumn"
    SPRING = "spring"
    SUMMER = "summer"

    @classmethod
    def from_number(cls, number: int) -> "Trimester":
        return _TRIMESTER_BY_NUMBER[number]

    @property
    def number(self) -> int:
        return _NUMBER_BY_TRIMESTER[self]


_TRIMESTER_BY_NUMBER = {1: Trimester.AUTUMN, 2: Trimester.SPRING, 3: Trimester.SUMMER}
_NUMBER_BY_TRIMESTER = {value: key for key, value in _TRIMESTER_BY_NUMBER.items()}


class LoadLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CourseKind(str, Enum):
    """
    Тип дисципліни в каталозі. Профорієнтовність залежить від напрямку студента (course_directions),
    тому на рівні дисципліни лише normative / elective, як `DisciplineType` в API.
    """

    NORMATIVE = "normative"
    ELECTIVE = "elective"


class PublicationStatus(str, Enum):
    PUBLISHED = "published"
    ARCHIVED = "archived"


class InstructorRole(str, Enum):
    LECTURER = "lecturer"
    PRACTICE = "practice"


class InstructorPreferenceKind(str, Enum):
    PREFERRED = "preferred"
    UNWANTED = "unwanted"


class DocumentMimeType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


class DocumentParseStatus(str, Enum):
    PENDING = "pending"
    PARSED = "parsed"
    FAILED = "failed"


class PlanStatus(str, Enum):
    """`approved` замість `approved_in_saz` з data-model.md — як в API v1 (contract.md §6, розбіжність 2)."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    AWAITING_DEANERY = "awaiting_deanery"
    APPROVED = "approved"


class PlanOrigin(str, Enum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"
    SAZ_SYNC = "saz_sync"


class PlanItemCategory(str, Enum):
    PROFESSIONAL = "professional"
    FREE_CHOICE = "free_choice"


class AcademicCategory(str, Enum):
    NORMATIVE = "normative"
    PROFESSIONAL = "professional"
    FREE_CHOICE = "free_choice"


class RecordSource(str, Enum):
    SELF_DECLARED = "self_declared"
    DEANERY_DOCUMENT = "deanery_document"
    APPROVED_PLAN = "approved_plan"
    ADMIN = "admin"
    SAZ_SYNC = "saz_sync"


class SyncSource(str, Enum):
    SAZ_CATALOG = "saz_catalog"
    FACULTY_CERTIFICATES = "faculty_certificates"


class SyncInitiator(str, Enum):
    ADMIN = "admin"
    SCHEDULER = "scheduler"


class SyncJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ModerationChangeType(str, Enum):
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"


class ModerationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AuditOutcome(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
