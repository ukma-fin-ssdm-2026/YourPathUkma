"""
Модульні тести спільних адмінських функцій: client_ip, write_audit, require_admin і _entry_fields журналу.

Запит і сесія БД підроблені, тож перевіряється лише логіка без HTTP і без бази.

Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: pytest, ruff.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.api.common import ApiError
from src.api.routes.admin.audit import _entry_fields
from src.api.routes.admin.common import client_ip, require_admin, write_audit
from src.db import enums as db_enums
from src.db.models.admin import AuditLog


def _request(host=None, method="GET", path="/api/v1/admin/users"):
    client = SimpleNamespace(host=host) if host is not None else None
    return SimpleNamespace(client=client, method=method, url=SimpleNamespace(path=path))


# --- client_ip ---


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8::1", "2001:db8::1"),
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
        ("testclient", None),  # TestClient передає не-IP, а колонка ip має тип inet
        ("", None),
        ("999.1.1.1", None),
    ],
)
def test_client_ip_returns_only_valid_addresses(host, expected):
    assert client_ip(_request(host)) == expected


def test_client_ip_without_client_is_none():
    assert client_ip(_request(None)) is None


# --- write_audit ---


def test_write_audit_adds_record_without_committing(fake_session):
    write_audit(
        fake_session,
        actor_id=1,
        action="user.update",
        object_type="User",
        object_id=42,
        old_value={"role": "student"},
        new_value={"role": "admin"},
        ip="203.0.113.7",
    )

    entry = fake_session.add.call_args.args[0]
    assert isinstance(entry, AuditLog)
    assert (entry.actor_id, entry.action, entry.object_type, entry.object_id) == (1, "user.update", "User", 42)
    assert entry.old_value == {"role": "student"}
    assert entry.new_value == {"role": "admin"}
    assert entry.ip == "203.0.113.7"
    fake_session.commit.assert_not_called()  # запис має потрапити в транзакцію самої зміни


def test_write_audit_defaults_to_allowed_outcome(fake_session):
    write_audit(fake_session, actor_id=None, action="sync.start", object_type="SyncJob")

    entry = fake_session.add.call_args.args[0]
    assert entry.outcome == db_enums.AuditOutcome.ALLOWED
    assert entry.actor_id is None


# --- require_admin ---


def test_require_admin_rejects_unknown_user(fake_session):
    fake_session.get.return_value = None

    with pytest.raises(ApiError) as error:
        require_admin(_request("203.0.113.7"), user_id=999, db=fake_session)

    assert error.value.status_code == 401
    fake_session.add.assert_not_called()


def test_require_admin_denies_student_and_audits_attempt(fake_session):
    student = SimpleNamespace(id=42, role=db_enums.UserRole.STUDENT)
    fake_session.get.return_value = student

    with pytest.raises(ApiError) as error:
        require_admin(_request("203.0.113.7", "DELETE", "/api/v1/admin/directions/3"), user_id=42, db=fake_session)

    assert (error.value.status_code, error.value.code) == (403, "FORBIDDEN_ROLE")
    entry = fake_session.add.call_args.args[0]
    assert entry.outcome == db_enums.AuditOutcome.DENIED
    assert entry.new_value == {"method": "DELETE", "path": "/api/v1/admin/directions/3"}
    assert entry.ip == "203.0.113.7"
    fake_session.commit.assert_called_once()  # відмову фіксуємо, хоч запит і завершується помилкою


def test_require_admin_returns_admin_user(fake_session):
    admin = SimpleNamespace(id=1, role=db_enums.UserRole.ADMIN)
    fake_session.get.return_value = admin

    assert require_admin(_request(), user_id=1, db=fake_session) is admin
    fake_session.add.assert_not_called()


# --- _entry_fields (журнал аудиту) ---


def _entry(**overrides):
    data = {
        "id": 9001,
        "actor_id": 1,
        "action": "plan.read",
        "object_type": "IndividualPlan",
        "object_id": 5,
        "outcome": db_enums.AuditOutcome.ALLOWED,
        "ip": "203.0.113.7",
        "created_at": datetime(2026, 10, 1, 12, 0),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_entry_fields_includes_actor_when_name_is_known():
    fields = _entry_fields(_entry(), "Адміністратор")

    assert fields["actor"].id == 1
    assert fields["actor"].full_name == "Адміністратор"
    assert fields["ip"] == "203.0.113.7"


@pytest.mark.parametrize(
    ("actor_id", "actor_name"),
    [(None, "Адміністратор"), (1, None), (None, None)],
    ids=["no-actor-id", "no-name", "system-event"],
)
def test_entry_fields_actor_is_none_without_id_or_name(actor_id, actor_name):
    assert _entry_fields(_entry(actor_id=actor_id), actor_name)["actor"] is None


def test_entry_fields_stringifies_ip_and_keeps_missing_ip_as_none():
    ip_object = MagicMock()
    ip_object.__str__.return_value = "198.51.100.1"

    assert _entry_fields(_entry(ip=ip_object), None)["ip"] == "198.51.100.1"
    assert _entry_fields(_entry(ip=None), None)["ip"] is None
