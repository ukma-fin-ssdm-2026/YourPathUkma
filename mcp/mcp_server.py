# Згенеровано за допомогою ШІ (Antigravity)
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Без токена API вимагає авторизації (401); для MCP вмикаємо тестового студента.
os.environ["MCP_DEV_MODE"] = "1"

from fastmcp import FastMCP

from src.api.main import app

mcp = FastMCP.from_fastapi(app=app)

if __name__ == "__main__":
    mcp.run()
