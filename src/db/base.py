"""
Базовий клас моделей і переносні типи колонок.

Цільова БД — PostgreSQL (jsonb, bytea, inet, bigint identity). Ті самі моделі працюють на SQLite (локальний запуск
без Docker): специфічні для PostgreSQL типи підключено через `with_variant`.

Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: pytest на SQLite і PostgreSQL,
`alembic check`.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Type

from sqlalchemy import JSON, BigInteger, DateTime, Integer, MetaData, Numeric, String, TypeDecorator
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase

# Стабільні імена обмежень: потрібні Alembic для downgrade і змін схемы
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


BigIntId = BigInteger().with_variant(Integer(), "sqlite")
JsonDoc = JSON().with_variant(JSONB(), "postgresql")
IpAddress = String(45).with_variant(INET(), "postgresql")
Credits = Numeric(4, 1, asdecimal=False)


class UTCDateTime(TypeDecorator):
    """timestamptz. SQLite не зберігає часовий пояс, тому при читанні повертаємо UTC явно."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: Optional[datetime], dialect):
        if value is not None:
            if isinstance(value, str):
                value = datetime.fromisoformat(value)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
        return value


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def db_enum(enum_cls: Type[Enum], name: str) -> SAEnum:
    """Enum як varchar + CHECK: однаково на обох СУБД, нове значення додається без ALTER TYPE."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )


def normalize_text(value: str) -> str:
    """
    Ключ для пошуку і звірки назв без урахування регістру (AGENTS.md §10).
    lower()/LIKE у SQLite не знають кирилиці, тому нормалізуємо в Python і зберігаємо в окремій колонці.
    """
    return " ".join(value.casefold().split())
