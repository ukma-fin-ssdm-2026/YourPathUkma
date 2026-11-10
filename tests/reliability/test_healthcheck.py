"""Перевірка CLI під час втрати доступу до файлу БД (ін'єкція збою).

subprocess потрібен для перевірки справжньої CLI-команди.

Використання ШІ: тест і точкові виключення Bandit створено за допомогою Codex.
Перевірка: pytest, Ruff і Bandit; аргументи запуску перевірено вручну.
"""

import json
import os
import sqlite3
import subprocess  # nosec B404
import sys

from src.db.config import ROOT_DIR


def test_healthcheck_reports_unhealthy_when_database_disappears(tmp_path):
    database = tmp_path / "healthcheck.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("SELECT 1")
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{database}")

    def run_command():
        # Фіксований модуль і поточний Python; користувацького вводу й shell немає.
        return subprocess.run(  # nosec B603
            [sys.executable, "-m", "src.healthcheck"],
            cwd=ROOT_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            shell=False,
        )

    healthy = run_command()
    assert healthy.returncode == 0, healthy.stderr
    assert json.loads(healthy.stdout) == {"status": "healthy", "checks": {"database": "healthy"}}

    # Ін'єкція збою: файл доступної раніше БД зникає перед наступною перевіркою.
    database.unlink()
    unhealthy = run_command()

    assert unhealthy.returncode == 1, unhealthy.stderr
    assert json.loads(unhealthy.stdout) == {
        "status": "unhealthy",
        "checks": {"database": "unhealthy"},
        "message": "Database check failed",
    }
    assert unhealthy.stderr == ""
    assert str(database) not in unhealthy.stdout
    assert not database.exists(), "Health check must not recreate a missing database"
