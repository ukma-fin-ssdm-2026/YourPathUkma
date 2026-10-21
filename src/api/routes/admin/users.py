"""
Адмінка: користувачі та академічна історія студентів (contract.md §3.9).

GET /admin/users, GET /admin/users/{id}, PATCH /admin/users/{id},
GET /admin/users/{id}/academic-history, POST /admin/users/{id}/academic-history/verify.

Плани студентів адмін тут не бачить (SEC-001, contract.md §6, розбіжність 14).
Усі зміни пишуться в журнал аудиту в тій самій транзакції.
"""

from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from ....db import enums as db_enums
from ....db.base import utcnow
from ....db.models.history import AcademicRecord
from ....db.models.users import StudentProfile, User
from ....db.session import get_db
from ...common import ApiError, PaginationInfo, error_responses
from ..auth import UserRole
from ..user import AcademicHistoryResponse, MeResponse, _build_me, _group_by_year
from .common import client_ip, require_admin, write_audit

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

_USER_NOT_FOUND = ("USER_NOT_FOUND", "Користувача з ID 42 не знайдено")
_FORBIDDEN = ("FORBIDDEN_ROLE", "Потрібна роль адміністратора")


class AdminStudentInfo(BaseModel):
    specialty: Optional[str] = None
    course_year: Optional[int] = None
    course_year_source: Optional[db_enums.CourseYearSource] = None


class AdminUser(BaseModel):
    id: int = Field(..., examples=[42])
    email: str = Field(..., examples=["vl.smyrnov@ukma.edu.ua"])
    full_name: str
    role: UserRole
    created_at: datetime
    last_login_at: Optional[datetime] = None
    student: Optional[AdminStudentInfo] = Field(None, description="null, якщо студентського профілю немає")


class PaginatedAdminUsers(BaseModel):
    users: List[AdminUser]
    pagination: PaginationInfo


class AdminUserDetail(MeResponse):
    """Та сама форма, що GET /me, плюс службові дати."""

    created_at: datetime
    last_login_at: Optional[datetime] = None


class AdminStudentPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    course_year: Optional[int] = Field(None, ge=1, le=4)
    specialty: Optional[str] = Field(None, min_length=2, max_length=150)


class AdminUserPatch(BaseModel):
    role: Optional[UserRole] = None
    student: Optional[AdminStudentPatch] = None


class VerifyRecordsRequest(BaseModel):
    record_ids: List[int] = Field(..., min_length=1, max_length=100)


class SkippedRecord(BaseModel):
    id: int
    code: str


class VerifyRecordsResponse(BaseModel):
    verified: List[int]
    skipped: List[SkippedRecord]


def _to_admin_user(user: User) -> AdminUser:
    profile = user.student_profile
    return AdminUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        student=(
            AdminStudentInfo(
                specialty=profile.specialty,
                course_year=profile.course_year,
                course_year_source=profile.course_year_source,
            )
            if profile is not None
            else None
        ),
    )


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "USER_NOT_FOUND", f"Користувача з ID {user_id} не знайдено")
    return user


@router.get(
    "/users",
    response_model=PaginatedAdminUsers,
    summary="Користувачі (студенти й адміни)",
    description=(
        "Фільтри комбінуються через AND. `q` шукає підрядок в email або ПІБ. Сортування за `id`. "
        "Примітка: на SQLite пошук за кирилицею чутливий до регістру, на PostgreSQL — ні."
    ),
    responses={200: {"description": "Список отримано"}, **error_responses(401, 403, 422, overrides={403: _FORBIDDEN})},
)
def list_users(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, min_length=2, max_length=100, description="Підрядок email або ПІБ"),
    role: Optional[UserRole] = Query(None),
    course_year: Optional[int] = Query(None, ge=1, le=4),
    course_year_source: Optional[db_enums.CourseYearSource] = Query(None),
    onboarding_required: Optional[bool] = Query(
        None, description="Лише студенти без курсу чи спеціальності (true) або з ними (false)"
    ),
):
    filters = []
    if q:
        filters.append(or_(User.email.icontains(q, autoescape=True), User.full_name.icontains(q, autoescape=True)))
    if role:
        filters.append(User.role == db_enums.UserRole(role.value))
    if course_year:
        filters.append(StudentProfile.course_year == course_year)
    if course_year_source:
        filters.append(StudentProfile.course_year_source == course_year_source)
    if onboarding_required is not None:
        incomplete = or_(
            StudentProfile.user_id.is_(None),
            StudentProfile.course_year.is_(None),
            StudentProfile.specialty.is_(None),
            StudentProfile.specialty == "",
        )
        if onboarding_required:
            filters.append(and_(User.role == db_enums.UserRole.STUDENT, incomplete))
        else:
            filters.append(and_(User.role == db_enums.UserRole.STUDENT, ~incomplete))

    joined = User.id == StudentProfile.user_id
    total = db.scalar(select(func.count(User.id)).select_from(User).outerjoin(StudentProfile, joined).where(*filters))
    users = db.scalars(
        select(User)
        .outerjoin(StudentProfile, joined)
        .where(*filters)
        .options(selectinload(User.student_profile))
        .order_by(User.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return PaginatedAdminUsers(
        users=[_to_admin_user(u) for u in users],
        pagination=PaginationInfo(limit=limit, offset=offset, total=total, has_more=(offset + limit) < total),
    )


@router.get(
    "/users/{user_id}",
    response_model=AdminUserDetail,
    summary="Користувач і профіль студента",
    description="`student` має повну форму з `GET /me`, разом з лічильниками кредитів. Планів студента тут немає.",
    responses={
        200: {"description": "Користувача знайдено"},
        **error_responses(401, 403, 404, 422, overrides={403: _FORBIDDEN, 404: _USER_NOT_FOUND}),
    },
)
def get_user(user_id: int = Path(..., gt=0, examples=[42]), db: Session = Depends(get_db)):
    user = _get_user(db, user_id)
    me = _build_me(db, user)
    return AdminUserDetail(**me.model_dump(), created_at=user.created_at, last_login_at=user.last_login_at)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUser,
    summary="Змінити роль, курс або спеціальність",
    description=(
        "Усі поля необов'язкові. Зміна `course_year` або `specialty` ставить `course_year_source = admin`. "
        "Адмін не може змінити роль сам собі (409). Кожна зміна пишеться в журнал аудиту."
    ),
    responses={
        200: {"description": "Користувача оновлено"},
        **error_responses(
            401,
            403,
            404,
            409,
            422,
            overrides={
                403: _FORBIDDEN,
                404: _USER_NOT_FOUND,
                409: ("CANNOT_CHANGE_OWN_ROLE", "Адміністратор не може змінити власну роль"),
            },
        ),
    },
)
def patch_user(
    payload: AdminUserPatch,
    request: Request,
    user_id: int = Path(..., gt=0, examples=[42]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = _get_user(db, user_id)
    old: Dict[str, object] = {}
    new: Dict[str, object] = {}

    if payload.role is not None and payload.role.value != user.role.value:
        if user.id == admin.id:
            raise ApiError(409, "CANNOT_CHANGE_OWN_ROLE", "Адміністратор не може змінити власну роль")
        old["role"], new["role"] = user.role.value, payload.role.value
        user.role = db_enums.UserRole(payload.role.value)

    student = payload.student
    if student is not None and (student.course_year is not None or student.specialty is not None):
        profile = user.student_profile
        if profile is None:
            profile = StudentProfile(user_id=user.id)
            user.student_profile = profile
        old["course_year_source"] = profile.course_year_source.value if profile.course_year_source else None
        if student.course_year is not None:
            old["course_year"], new["course_year"] = profile.course_year, student.course_year
            profile.course_year = student.course_year
        if student.specialty is not None:
            old["specialty"], new["specialty"] = profile.specialty, student.specialty
            profile.specialty = student.specialty
        profile.course_year_source = db_enums.CourseYearSource.ADMIN
        new["course_year_source"] = db_enums.CourseYearSource.ADMIN.value

    if new:
        write_audit(
            db,
            actor_id=admin.id,
            action="user.update",
            object_type="User",
            object_id=user.id,
            old_value=old,
            new_value=new,
            ip=client_ip(request),
        )
        db.commit()
    return _to_admin_user(user)


@router.get(
    "/users/{user_id}/academic-history",
    response_model=AcademicHistoryResponse,
    summary="Академічна історія студента",
    description="Та сама форма, що `GET /me/academic-history`, згруповано за навчальним роком.",
    responses={
        200: {"description": "Історію отримано"},
        **error_responses(401, 403, 404, 422, overrides={403: _FORBIDDEN, 404: _USER_NOT_FOUND}),
    },
)
def get_user_history(
    user_id: int = Path(..., gt=0, examples=[42]),
    academic_year: Optional[int] = Query(None, ge=2015, le=2030),
    db: Session = Depends(get_db),
):
    _get_user(db, user_id)
    query = select(AcademicRecord).where(AcademicRecord.student_id == user_id)
    if academic_year is not None:
        query = query.where(AcademicRecord.academic_year == academic_year)
    return _group_by_year(list(db.scalars(query)))


@router.post(
    "/users/{user_id}/academic-history/verify",
    response_model=VerifyRecordsResponse,
    summary="Підтвердити записи історії",
    description=(
        "Підтверджує записи `self_declared`. Пропущені записи повертаються в `skipped`: "
        "`RECORD_NOT_FOUND` (немає або належить іншому студенту) і `RECORD_NOT_VERIFIABLE` "
        "(не `self_declared` або вже підтверджено)."
    ),
    responses={
        200: {"description": "Записи оброблено"},
        **error_responses(401, 403, 404, 422, overrides={403: _FORBIDDEN, 404: _USER_NOT_FOUND}),
    },
)
def verify_records(
    payload: VerifyRecordsRequest,
    request: Request,
    user_id: int = Path(..., gt=0, examples=[42]),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_user(db, user_id)
    ids = list(dict.fromkeys(payload.record_ids))
    records = {r.id: r for r in db.scalars(select(AcademicRecord).where(AcademicRecord.id.in_(ids)))}

    verified: List[int] = []
    skipped: List[SkippedRecord] = []
    now = utcnow()
    for record_id in ids:
        record = records.get(record_id)
        if record is None or record.student_id != user_id:
            skipped.append(SkippedRecord(id=record_id, code="RECORD_NOT_FOUND"))
        elif record.source != db_enums.RecordSource.SELF_DECLARED or record.verified:
            skipped.append(SkippedRecord(id=record_id, code="RECORD_NOT_VERIFIABLE"))
        else:
            record.verified = True
            record.verified_by = admin.id
            record.verified_at = now
            verified.append(record_id)

    if verified:
        write_audit(
            db,
            actor_id=admin.id,
            action="academic_record.verify",
            object_type="User",
            object_id=user_id,
            new_value={"record_ids": verified},
            ip=client_ip(request),
        )
        db.commit()
    return VerifyRecordsResponse(verified=verified, skipped=skipped)
