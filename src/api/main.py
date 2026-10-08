"""
Точка входу API YourPathUkma. Запуск з кореня репозиторію:

    uvicorn src.api.main:app --reload --port 3000

OpenAPI-специфікація генерується з коду при старті сервера (lifespan) і зберігається
у docs/api/openapi-generated.yaml та docs/api/openapi-generated.json. Вручну її не редагувати.

Використання ШІ: файл створено за допомогою Claude (Anthropic) на основі шаблону викладача (ЛР4).
Перевірка: запуск сервера, перевірка появи/оновлення openapi-generated.yaml після зміни коду,
перегляд Swagger UI (/api-docs) і ReDoc (/redoc).
"""
import json
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI
from .common import register_error_handlers
from .routes import disciplines, plans
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "api"


def save_openapi_spec(app: FastAPI) -> None:
    """Зберігає автоматично згенеровану специфікацію OpenAPI у файли."""
    spec = app.openapi()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "openapi-generated.yaml").write_text(
        yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    (DOCS_DIR / "openapi-generated.json").write_text(
        json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("✅ OpenAPI spec auto-generated from code!")
    print(f"📁 Saved to: {DOCS_DIR / 'openapi-generated.yaml'}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    save_openapi_spec(app) 
    print("Swagger UI: http://127.0.0.1:3000/api-docs")
    print("ReDoc:      http://127.0.0.1:3000/redoc") 
    yield


app = FastAPI(
    title="YourPathUkma API",
    description=(
        "REST API платформи для побудови індивідуального навчального плану студентів НаУКМА: "
        "плани вибіркових дисциплін, каталог дисциплін, контроль кредитного навантаження.\n\n"
        "**Автентифікація:** JWT Bearer (Google Workspace SSO). У поточній заглушці приймається "
        "будь-який непорожній токен: натисніть Authorize і введіть, наприклад, `test`."
    ),
    version="1.0.0",
    docs_url="/api-docs",  
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "Plans", "description": "Індивідуальні навчальні плани студента (CRUD)"},
        {"name": "Disciplines", "description": "Каталог дисциплін (читання, фільтри)"},
    ],
    lifespan=lifespan,
)

register_error_handlers(app)
app.include_router(plans.router)
app.include_router(disciplines.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=3000, reload=True)