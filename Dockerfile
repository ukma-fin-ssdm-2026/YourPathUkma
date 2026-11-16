# Використання ШІ: Codex підготував образ API. Перевірка: Linux/amd64 build,
# міграції й HTTP 200 від API; workflow повторює smoke test до публікації.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Спільний перевірений Linux/Python 3.12 lock включає також інструменти CI.
COPY requirements-ci.lock ./
RUN pip install --no-cache-dir --require-hashes --only-binary :all: -r requirements-ci.lock \
    && useradd --create-home --uid 10001 app
COPY --chown=app:app src ./src
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini ./
RUN chown app:app /app
USER app
EXPOSE 3000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "3000"]
