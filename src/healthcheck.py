"""Команда перевірки доступності БД: python -m src.healthcheck.

Використання ШІ: команду створено за допомогою Codex. Перевірка: Ruff і ручні
запуски з доступною SQLite, недоступною БД та некоректним налаштуванням.
"""

import json
import multiprocessing
from multiprocessing.connection import Connection
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from src.db.config import ROOT_DIR, database_url

TIMEOUT_SECONDS = 5


def _check_database(sender: Connection) -> None:
    """Окремий процес дозволяє обмежити також DNS і зависання драйвера."""
    engine = None
    try:
        url = make_url(database_url())
        if url.get_backend_name() == "sqlite":
            # Перевірка не повинна створювати порожню БД і повідомляти про успіх.
            if not url.database or url.database == ":memory:":
                raise ValueError("Health check requires a persistent database")
            path = Path(url.database).resolve()
            url = url.set(database=f"{path.as_uri()}?mode=ro", query={"uri": "true"})
        engine = create_engine(url, poolclass=NullPool)
        with engine.connect() as connection:
            healthy = connection.execute(text("SELECT 1")).scalar_one() == 1
        sender.send("healthy" if healthy else "unhealthy")
    except (SQLAlchemyError, RuntimeError, ValueError, ImportError, OSError):
        # Не виводимо URL, облікові дані або внутрішні повідомлення драйвера.
        sender.send("unhealthy")
    finally:
        if engine is not None:
            engine.dispose()
        sender.close()


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_check_database, args=(sender,))
    status = "unhealthy"
    reason = "Database check failed"
    try:
        process.start()
        sender.close()
        if receiver.poll(TIMEOUT_SECONDS):
            status = receiver.recv()
        else:
            reason = "Database check timed out"
    except (EOFError, OSError, RuntimeError):
        pass
    finally:
        if process.pid is not None:
            process.join(timeout=0.1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        receiver.close()
        sender.close()

    result = {"status": status, "checks": {"database": status}}
    if status != "healthy":
        result["message"] = reason
    print(json.dumps(result))
    return 0 if status == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
