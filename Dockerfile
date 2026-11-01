# syntax=docker/dockerfile:1
#
# Один контейнер: зібраний фронтенд + API (FastAPI роздає frontend/dist, див. src/api/frontend_site.py).
# Збірка:  docker build -t yourpath --build-arg VITE_MS_CLIENT_ID=<id> --build-arg VITE_MS_TENANT=<tenant> .
# Запуск:  див. docs/deployment/azure.md (змінні середовища, PostgreSQL, Microsoft Entra).
#
# Використання ШІ: файл створено за допомогою Claude (Claude Code). Перевірка: збірка образу й запуск контейнера
# (GET /health, GET /, вхід у Swagger).

# ---------- Етап 1: збірка фронтенду ----------
FROM node:22-slim AS frontend
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json frontend/
RUN cd frontend && npm ci

COPY frontend frontend
# Типи API генеруються зі специфікації, яка лежить у репозиторії
COPY docs/api/openapi-generated.json docs/api/openapi-generated.json

# Публічні ідентифікатори Entra вшиваються у збірку; секрети сюди НЕ передаються
ARG VITE_MS_CLIENT_ID=""
ARG VITE_MS_TENANT="organizations"
ENV VITE_USE_MOCKS=false \
    VITE_API_BASE=/api/v1 \
    VITE_MS_CLIENT_ID=${VITE_MS_CLIENT_ID} \
    VITE_MS_TENANT=${VITE_MS_TENANT}
RUN cd frontend && npm run gen:api && npm run build

# ---------- Етап 2: API + збірка фронтенду ----------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations migrations
COPY src src
COPY --from=frontend /build/frontend/dist frontend/dist

# Застосунок при старті пише специфікацію в docs/api, тож тека має існувати й бути доступна для запису
RUN useradd --system --create-home app \
    && mkdir -p docs/api \
    && chown -R app:app /app
USER app

# production за замовчуванням: потрібні MS_TENANT_ID, MS_CLIENT_ID, JWT_SECRET (>= 32 символів), COOKIE_SECURE=1
ENV APP_ENV=production \
    PORT=8000 \
    FRONTEND_DIST=/app/frontend/dist
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8000'), timeout=3).status == 200 else 1)"

# --proxy-headers: за ingress Azure TLS завершується до контейнера, а справжній IP клієнта приходить у X-Forwarded-For
CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
