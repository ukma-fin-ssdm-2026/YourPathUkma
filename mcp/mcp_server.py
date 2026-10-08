# Згенеровано за допомогою ШІ (Antigravity)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastmcp import FastMCP
from src.api.main import app

mcp = FastMCP.from_fastapi(app=app)

if __name__ == "__main__":
    mcp.run()
