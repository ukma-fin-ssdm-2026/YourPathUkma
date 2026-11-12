"""MCP для локального API з явною Bearer-авторизацією.

Використання ШІ: Codex підключив MCP_API_TOKEN замість мертвого MCP_DEV_MODE.
Перевірка: pytest (авторизований запит через ASGI-клієнт), Ruff і Bandit.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.main import app  # noqa: E402
from src.api.tokens import decode_access_token  # noqa: E402


def api_client_kwargs() -> dict:
    """Локальний stdio-MCP працює з правами власника налаштованого токена."""
    token = os.getenv("MCP_API_TOKEN", "").strip()
    if not token or decode_access_token(token) is None:
        raise RuntimeError("Задайте чинний MCP_API_TOKEN: python -m scripts.issue_token email@ukma.edu.ua")
    return {
        "base_url": "http://localhost:3000",
        "headers": {"Authorization": f"Bearer {token}"},
        "timeout": 10,
    }


def create_mcp():
    # Відсутній/прострочений токен зупиняє запуск ще до створення сервера.
    kwargs = api_client_kwargs()
    from fastmcp import FastMCP

    return FastMCP.from_fastapi(app=app, name="YourPathUkma", httpx_client_kwargs=kwargs)


if __name__ == "__main__":
    create_mcp().run(transport="stdio")
