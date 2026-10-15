"""
Ресурс «Користувач» (User): профіль студента, онбординг, академічна історія (contract.md §3.2).

Кінцеві точки: GET /me, POST /me/onboarding, GET/POST /me/academic-history, DELETE /me/academic-history/{id}.
Лічильники кредитів не зберігаються: вони рахуються з academic_records (записи з approved_plan
створюватиме перехід плану в `approved`, див. contract.md §3.2.2).
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...db import enums as db_enums
from ...db.models.catalog import Course
from ...db.models.history import AcademicRecord
from ...db.models.users import StudentProfile, User
from ...db.session import get_db
from ..common import ApiError, ErrorDetail, error_responses, get_current_student_id
from ..onboarding import get_onboarded_student
from .auth import AuthUser
from .system import Limits

router = APIRouter(prefix="/api/v1", tags=["User"])

# Контракт не обмежує academic_year історії (на відміну від планів, 2024–2030): студент 4 курсу почав у 2023
HISTORY_YEAR_MIN = 2015
HISTORY_YEAR_MAX = 2030


# ---------- Схеми: профіль ----------


class CreditsInfo(BaseModel):
    total_used: float = Field(..., description="Усього пройдено кредитів", examples=[118.5])
    total_limit: int = Field(..., description="Ліміт за програму", examples=[240])
    free_choice_used: float = Field(..., description="Вільний вибір за всі роки", examples=[9.0])
    free_choice_limit: int = Field(..., description="Ліміт вільного вибору", examples=[25])
    professional_used: float = Field(..., description="Профорієнтовні кредити", examples=[27.0])
    professional_limit: int = Field(..., description="Орієнтир профорієнтовних кредитів", examples=[54])


class StudentInfo(BaseModel):
    faculty: str = Field(..., examples=["ФІ"])
    specialty: Optional[str] = Field(None, examples=["Інженерія програмного забезпечення"])
    course_year: Optional[int] = Field(None, description="null до онбордингу", examples=[3])
    course_year_source: Optional[db_enums.CourseYearSource] = Field(None, description="Хто вказав курс")
    onboarding_required: bool = Field(..., description="true, якщо курс або спеціальність не заповнені")
    can_create_plan: bool = Field(..., description="false для 1 курсу і до онбордингу")
    load_levels_mode: Literal["manual", "auto"] = Field(..., description="auto для 4 курсу (FR-003)")
    credits: CreditsInfo
    saz_synced_at: Optional[datetime] = Field(None, description="Остання синхронізація з САЗ (заблоковано, R14)")


class MeResponse(AuthUser):
    student: Optional[StudentInfo] = Field(None, description="null для адміна без студентського профілю")


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    course_year: int = Field(..., ge=1, le=4, description="Курс навчання", examples=[3])
    specialty: str = Field(..., min_length=2, max_length=150, examples=["Інженерія програмного забезпечення"])


# ---------- Схеми: академічна історія ----------


class AcademicRecordResponse(BaseModel):
    id: int = Field(..., examples=[310])
    academic_year: int = Field(..., description="Рік початку навчального року", examples=[2024])
    course_year: int = Field(..., ge=1, le=4, examples=[1])
    course_id: Optional[int] = Field(None, description="null, якщо дисципліни вже немає в каталозі", examples=[301])
    title: str = Field(..., examples=["Алгоритми та структури даних"])
    trimester: int = Field(..., ge=1, le=3, description="1 — осінь, 2 — весна, 3 — літо", examples=[1])
    credits: float = Field(..., examples=[6.0])
    category: db_enums.AcademicCategory
    source: db_enums.RecordSource
    verified: bool = Field(..., description="Підтверджено адміністратором")
    created_at: datetime


class AcademicYearGroup(BaseModel):
    academic_year: int
    course_year: int
    total_credits: float
    records: List[AcademicRecordResponse]


class AcademicHistoryResponse(BaseModel):
    years: List[AcademicYearGroup] = Field(..., description="Записи, згруповані за навчальним роком")


class AcademicRecordInput(BaseModel):
    academic_year: int = Field(..., ge=HISTORY_YEAR_MIN, le=HISTORY_YEAR_MAX, examples=[2024])
    course_year: int = Field(..., ge=1, le=4, examples=[1])
    course_id: Optional[int] = Field(None, gt=0, description="Дисципліна з каталогу; null — вказати title і credits")
    title: Optional[str] = Field(None, min_length=2, max_length=300, description="Обов'язково, якщо course_id = null")
    trimester: int = Field(..., ge=1, le=3, examples=[1])
    credits: Optional[float] = Field(None, gt=0, le=30, description="Обов'язково, якщо course_id = null")
    category: db_enums.AcademicCategory


class AddRecordsRequest(BaseModel):
    records: List[AcademicRecordInput] = Field(..., min_length=1, max_length=60)


class AddRecordsResponse(BaseModel):
    records: List[AcademicRecordResponse]


# ---------- Допоміжні функції ----------


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації")
    return user


def _credits(db: Session, student_id: int) -> CreditsInfo:
    rows = db.execute(
        select(AcademicRecord.category, func.sum(AcademicRecord.credits))
        .where(AcademicRecord.student_id == student_id)
        .group_by(AcademicRecord.category)
    ).all()
    by_category = {category: float(total or 0) for category, total in rows}
    limits = Limits()
    return CreditsInfo(
        total_used=round(sum(by_category.values()), 1),
        total_limit=limits.total_credits,
        free_choice_used=round(by_category.get(db_enums.AcademicCategory.FREE_CHOICE, 0.0), 1),
        free_choice_limit=limits.free_choice_credits,
        professional_used=round(by_category.get(db_enums.AcademicCategory.PROFESSIONAL, 0.0), 1),
        professional_limit=limits.professional_credits,
    )


def _is_onboarded(profile: Optional[StudentProfile]) -> bool:
    return profile is not None and profile.course_year is not None and bool(profile.specialty)


def _build_me(db: Session, user: User) -> MeResponse:
    profile = user.student_profile
    student = None
    if profile is not None:
        onboarded = _is_onboarded(profile)
        student = StudentInfo(
            faculty=profile.faculty,
            specialty=profile.specialty,
            course_year=profile.course_year,
            course_year_source=profile.course_year_source,
            onboarding_required=not onboarded,
            can_create_plan=onboarded and profile.course_year >= 2,
            load_levels_mode="auto" if profile.course_year == 4 else "manual",
            credits=_credits(db, user.id),
            saz_synced_at=profile.saz_synced_at,
        )
    return MeResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value, student=student)


def _record_response(record: AcademicRecord) -> AcademicRecordResponse:
    return AcademicRecordResponse(
        id=record.id,
        academic_year=record.academic_year,
        course_year=record.course_year,
        course_id=record.course_id,
        title=record.title,
        trimester=record.trimester.number,
        credits=record.credits,
        category=record.category,
        source=record.source,
        verified=record.verified,
        created_at=record.created_at,
    )


def _group_by_year(records: List[AcademicRecord]) -> AcademicHistoryResponse:
    grouped: Dict[int, List[AcademicRecord]] = defaultdict(list)
    for record in records:
        grouped[record.academic_year].append(record)
    years = []
    for year in sorted(grouped):
        items = sorted(grouped[year], key=lambda r: (r.trimester.number, r.id))
        years.append(
            AcademicYearGroup(
                academic_year=year,
                course_year=items[0].course_year,
                total_credits=round(sum(r.credits for r in items), 1),
                records=[_record_response(r) for r in items],
            )
        )
    return AcademicHistoryResponse(years=years)


# ---------- Профіль ----------


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Профіль поточного користувача",
    description="Профіль і лічильники кредитів. `student` = null для адміна без студентського профілю.",
    responses={200: {"description": "Профіль отримано"}, **error_responses(401)},
)
def get_me(user_id: int = Depends(get_current_student_id), db: Session = Depends(get_db)):
    return _build_me(db, _get_user(db, user_id))


@router.post(
    "/me/onboarding",
    response_model=MeResponse,
    summary="Онбординг: курс і спеціальність",
    description="Одноразове заповнення профілю. Повторний виклик → 409, змінити може лише адмін.",
    responses={
        200: {"description": "Профіль заповнено"},
        **error_responses(
            401,
            409,
            422,
            overrides={
                409: ("ALREADY_ONBOARDED", "Курс і спеціальність уже вказано, змінити їх може лише адміністратор")
            },
        ),
    },
)
def onboard(
    payload: OnboardingRequest,
    user_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    profile = user.student_profile
    if _is_onboarded(profile):
        raise ApiError(409, "ALREADY_ONBOARDED", "Курс і спеціальність уже вказано, змінити їх може лише адміністратор")
    if profile is None:
        profile = StudentProfile(user_id=user.id)
        user.student_profile = profile
    profile.course_year = payload.course_year
    profile.specialty = payload.specialty
    profile.course_year_source = db_enums.CourseYearSource.SELF_DECLARED
    db.commit()
    return _build_me(db, user)


# ---------- Академічна історія ----------


@router.get(
    "/me/academic-history",
    response_model=AcademicHistoryResponse,
    summary="Академічна історія студента",
    description="Пройдені дисципліни, згруповані за навчальним роком. Без пагінації.",
    responses={200: {"description": "Історію отримано"}, **error_responses(401, 422)},
)
def list_academic_history(
    academic_year: Optional[int] = Query(
        None, ge=HISTORY_YEAR_MIN, le=HISTORY_YEAR_MAX, description="Лише цей навчальний рік"
    ),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    query = select(AcademicRecord).where(AcademicRecord.student_id == student_id)
    if academic_year is not None:
        query = query.where(AcademicRecord.academic_year == academic_year)
    return _group_by_year(list(db.scalars(query)))


@router.post(
    "/me/academic-history",
    response_model=AddRecordsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Додати пройдені дисципліни",
    description=(
        "Додає 1–60 записів із `source = self_declared`. Якщо задано `course_id`, `title` і `credits` "
        "беруться з каталогу. `course_year` запису не може перевищувати курс студента; "
        "вільний вибір за всі роки ≤ 25 кредитів."
    ),
    responses={
        201: {"description": "Записи додано"},
        **error_responses(
            401,
            409,
            422,
            overrides={409: ("ONBOARDING_REQUIRED", "Спершу вкажіть курс і спеціальність")},
        ),
    },
)
def add_academic_history(
    payload: AddRecordsRequest,
    profile: StudentProfile = Depends(get_onboarded_student),
    db: Session = Depends(get_db),
):
    student_id = profile.user_id
    ids = [r.course_id for r in payload.records if r.course_id is not None]
    courses: Dict[int, Course] = {}
    already_taken: set = set()
    if ids:
        courses = {c.id: c for c in db.scalars(select(Course).where(Course.id.in_(ids)))}
        already_taken = set(
            db.scalars(
                select(AcademicRecord.course_id).where(
                    AcademicRecord.student_id == student_id, AcademicRecord.course_id.in_(ids)
                )
            )
        )

    details: List[ErrorDetail] = []
    seen: set = set()
    rows: List[AcademicRecord] = []
    for index, rec in enumerate(payload.records):
        prefix = f"records.{index}"
        if rec.course_year > profile.course_year:
            details.append(
                ErrorDetail(
                    field=f"{prefix}.course_year",
                    message=f"COURSE_YEAR_TOO_HIGH: запис за {rec.course_year} курс, а студент на {profile.course_year}",
                )
            )
        if rec.course_id is not None:
            course = courses.get(rec.course_id)
            if course is None:
                details.append(
                    ErrorDetail(
                        field=f"{prefix}.course_id",
                        message=f"COURSE_NOT_FOUND: дисципліни {rec.course_id} немає в каталозі",
                    )
                )
                continue
            if rec.course_id in seen or rec.course_id in already_taken:
                details.append(
                    ErrorDetail(
                        field=f"{prefix}.course_id",
                        message=f"DUPLICATE_COURSE: дисципліна {rec.course_id} уже є в історії",
                    )
                )
                continue
            seen.add(rec.course_id)
            title, credits = course.title, course.credits
        else:
            if not rec.title:
                details.append(
                    ErrorDetail(field=f"{prefix}.title", message="TITLE_REQUIRED: без course_id потрібна назва")
                )
            if rec.credits is None:
                details.append(
                    ErrorDetail(field=f"{prefix}.credits", message="CREDITS_REQUIRED: без course_id потрібні кредити")
                )
            if not rec.title or rec.credits is None:
                continue
            title, credits = rec.title, rec.credits
        rows.append(
            AcademicRecord(
                student_id=student_id,
                academic_year=rec.academic_year,
                course_year=rec.course_year,
                course_id=rec.course_id,
                title=title,
                credits=credits,
                trimester=db_enums.Trimester.from_number(rec.trimester),
                category=rec.category,
                source=db_enums.RecordSource.SELF_DECLARED,
                verified=False,
            )
        )

    if not details:
        limit = Limits().free_choice_credits
        used = db.scalar(
            select(func.coalesce(func.sum(AcademicRecord.credits), 0)).where(
                AcademicRecord.student_id == student_id,
                AcademicRecord.category == db_enums.AcademicCategory.FREE_CHOICE,
            )
        )
        new = sum(r.credits for r in rows if r.category == db_enums.AcademicCategory.FREE_CHOICE)
        if used + new > limit:
            details.append(
                ErrorDetail(
                    field="records",
                    message=f"FREE_ELECTIVE_LIMIT_EXCEEDED: вільний вибір за всі роки {round(used + new, 1)} > {limit} кредитів",
                )
            )
    if details:
        raise ApiError(422, "VALIDATION_ERROR", "Невалідні вхідні дані", details)

    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError:
        # Одночасний запит устиг додати ту саму дисципліну (UNIQUE student_id, course_id)
        db.rollback()
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Невалідні вхідні дані",
            [ErrorDetail(field="records", message="DUPLICATE_COURSE: дисципліна вже є в історії")],
        )
    return AddRecordsResponse(records=[_record_response(r) for r in rows])


@router.delete(
    "/me/academic-history/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити власний запис історії",
    description="Лише записи `self_declared`, які ще не підтверджені адміном.",
    responses={
        204: {"description": "Запис видалено"},
        **error_responses(
            401,
            404,
            409,
            422,
            overrides={
                404: ("RECORD_NOT_FOUND", "Запис з ID 310 не знайдено"),
                409: ("RECORD_NOT_DELETABLE", "Видаляти можна лише непідтверджені записи, додані вручну"),
            },
        ),
    },
)
def delete_academic_record(
    record_id: int = Path(..., gt=0, description="ID запису історії", examples=[310]),
    student_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
):
    record = db.get(AcademicRecord, record_id)
    # Чужий запис не розкриваємо: 404, як і для неіснуючого (R3)
    if record is None or record.student_id != student_id:
        raise ApiError(404, "RECORD_NOT_FOUND", f"Запис з ID {record_id} не знайдено")
    if record.source != db_enums.RecordSource.SELF_DECLARED or record.verified:
        raise ApiError(409, "RECORD_NOT_DELETABLE", "Видаляти можна лише непідтверджені записи, додані вручну")
    db.delete(record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)