"""
Спільне для адмінських кінцевих точок (contract.md §3.9): перевірка ролі та запис у журнал аудиту.

Роль береться з БД, не з клієнта (R2). Спроба студента зайти в /admin/* фіксується в журналі
з outcome = denied (SEC-001).
"""

from typing import Any, Dict, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ....db import enums as db_enums
from ....db.models.admin import AuditLog
from ....db.models.users import User
from ....db.session import get_db
from ...common import ApiError, get_current_student_id



def client_ip(request: Request) -> Optional[str]:
    """IP з'єднання. X-Forwarded-For навмисно не читаємо: клієнт може його підробити."""
    return request.client.host if request.client else None


def write_audit(
    db: Session,
    *,
    actor_id: Optional[int],
    action: str,
    object_type: str,
    object_id: Optional[int] = None,
    outcome: db_enums.AuditOutcome = db_enums.AuditOutcome.ALLOWED,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
) -> None:
    """Додає запис до сесії, але не робить commit: він має потрапити в ту саму транзакцію, що й сама зміна."""
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            outcome=outcome,
            old_value=old_value,
            new_value=new_value,
            ip=ip,
        )
    )


def require_admin(
    request: Request,
    user_id: int = Depends(get_current_student_id),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "Відсутній або некоректний токен авторизації")
    if user.role != db_enums.UserRole.ADMIN:
        write_audit(
            db,
            actor_id=user.id,
            action="admin.access",
            object_type="AdminEndpoint",
            outcome=db_enums.AuditOutcome.DENIED,
            new_value={"method": request.method, "path": request.url.path},
            ip=client_ip(request),
        )
        db.commit()
        raise ApiError(403, "FORBIDDEN_ROLE", "Потрібна роль адміністратора")
    return user