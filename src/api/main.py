"""
Точка входу API YourPathUkma. Запуск з кореня репозиторію:

    uvicorn src.api.main:app --reload --port 3000

OpenAPI-специфікація генерується з коду при старті сервера (lifespan) і зберігається
у docs/api/openapi-generated.yaml та docs/api/openapi-generated.json. Вручну її не редагувати.

Використання ШІ: файл створено за допомогою Claude (Anthropic) на основі шаблону викладача (ЛР4).
Перевірка: запуск сервера, перевірка появи/оновлення openapi-generated.yaml після зміни коду,
перегляд Swagger UI (/api-docs) і ReDoc (/redoc).

Правки за зовнішнім рев'ю (review/received/review-report.md) внесено за допомогою Claude (Claude Code):
імпорти нагорі, журналювання замість print, X-Request-ID, CORS з env, захист від MCP_DEV_MODE у продакшні.
Перевірено: pytest і ruff check src/api.

Додатково (Claude, Anthropic): додано відсутні імпорти роутерів preferences, user, deanery (без них застосунок
не стартував з NameError) і виклик init_database() при старті (міграції та демо-дані).
Перевірка: ручний огляд; запуск сервера, pytest і ruff check src/api виконати перед комітом.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..db.migrate import init_database
from .common import RequestIdMiddleware, assert_safe_environment, register_error_handlers
from .routes import auth, deanery, disciplines, plans, preferences, reference, system, user
from .routes.admin import audit as admin_audit
from .routes.admin import catalog as admin_catalog
from .routes.admin import sync as admin_sync
from .routes.admin import users as admin_users

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("yourpath.api")

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs" / "api"


def save_openapi_spec(app: FastAPI) -> None:
    """Зберігає автоматично згенеровану специфікацію OpenAPI у файли."""
    spec = app.openapi()
    try:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        (DOCS_DIR / "openapi-generated.yaml").write_text(
            yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
        (DOCS_DIR / "openapi-generated.json").write_text(
            json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        logger.warning("Не вдалося зберегти OpenAPI-специфікацію в %s", DOCS_DIR, exc_info=True)
        return
    logger.info("OpenAPI-специфікацію згенеровано з коду: %s", DOCS_DIR / "openapi-generated.yaml")


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_safe_environment()
    init_database()
    save_openapi_spec(app)
    logger.info("Swagger UI: http://127.0.0.1:3000/api-docs, ReDoc: http://127.0.0.1:3000/redoc")
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
    servers=[
        {
            "url": "http://localhost:3000",
            "description": "Local development server (localhost)",
        }
    ],
    openapi_tags=[
        {"name": "System", "description": "Системні маршрути (моніторинг)"},
        {"name": "Plans", "description": "Індивідуальні навчальні плани студента (CRUD)"},
        {"name": "Disciplines", "description": "Каталог дисциплін (читання, фільтри)"},
        {"name": "Auth", "description": "Вхід через Google, оновлення і відкликання токена (заглушка)"},
        {"name": "Reference", "description": "Довідники: напрямки розвитку і викладачі"},
        {"name": "Preferences", "description": "Побажання студента на навчальний рік"},
        {"name": "Deanery documents", "description": "Документи деканату"},
        {"name": "Admin", "description": "Адміністрування: користувачі, довідники, синхронізація, аудит"},
        {"name": "User", "description": "Профіль студента, онбординг, академічна історія"},
    ],
    lifespan=lifespan,
)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_error_handlers(app)
app.include_router(plans.router)
app.include_router(disciplines.router)
app.include_router(auth.router)
app.include_router(reference.router)
app.include_router(system.router)
app.include_router(preferences.router)
app.include_router(user.router)
app.include_router(deanery.router)
app.include_router(admin_users.router)
app.include_router(admin_catalog.router)
app.include_router(admin_sync.router)
app.include_router(admin_audit.router)


@app.get("/health", tags=["System"], summary="Перевірка стану системи (Healthcheck)")
async def health_check():
    """Повертає стан сервісу для моніторингу."""
    return {"status": "ok", "version": "1.0.0", "message": "All systems operational"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host=os.getenv("API_HOST", "127.0.0.1"), port=3000, reload=True)