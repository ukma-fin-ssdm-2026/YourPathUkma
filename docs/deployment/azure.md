# Розгортання на Microsoft Azure (один Docker-контейнер)

Застосунок збирається в **один образ**: зібраний фронтенд (React) і API (FastAPI) працюють в одному процесі й на одному адресі. Образ публікується на Docker Hub, а Azure Container Apps його запускає. Окремий nginx не потрібен.

Навіщо один контейнер: refresh-cookie видається з `SameSite=strict`, `Secure` і шляхом `/api/v1/auth`, а фронтенд ходить на відносний `/api/v1`. На одному origin це працює без CORS.

```
Браузер ──HTTPS──▶ Azure Container Apps (ingress) ──▶ контейнер yourpath :8000
                                                        ├─ /            фронтенд (frontend/dist)
                                                        └─ /api/v1/...  API (FastAPI)
                                                              │
                                                              ▼
                                            Azure Database for PostgreSQL
```

## Що потрібно мати

- обліковий запис Azure з підпискою (підійде Azure for Students) і [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli);
- обліковий запис Docker Hub;
- доступ до app registration у Microsoft Entra (tenant НаУКМА): потрібні `MS_TENANT_ID` і `MS_CLIENT_ID`.

## 1. Збірка й публікація образу

**Вручну:**

```bash
docker build -t <user>/yourpath:1 \
  --build-arg VITE_MS_CLIENT_ID=<Application (client) ID> \
  --build-arg VITE_MS_TENANT=<Directory (tenant) ID> .
docker login
docker push <user>/yourpath:1
```

`VITE_MS_CLIENT_ID` і `VITE_MS_TENANT` це публічні ідентифікатори, вони вшиваються у збірку фронтенду. Секрети в образ не потрапляють (`.dockerignore` виключає `.env`, `*.sqlite`, `saz_raw/`).

**Через GitHub Actions:** у налаштуваннях репозиторію додайте secrets `DOCKERHUB_USERNAME` і `DOCKERHUB_TOKEN` (access token Docker Hub з правом Read & Write) та variables `VITE_MS_CLIENT_ID` і `VITE_MS_TENANT`. Потім Actions → «Publish Docker image» → Run workflow (або тег `v1.0.0`). Образ з'явиться як `<user>/yourpath:latest`.

> Публічний репозиторій на Docker Hub бачать усі. Якщо образ має бути закритим, зробіть репозиторій private і передайте облікові дані в Azure (`--registry-username/--registry-password`).

## 2. Ресурси в Azure

```bash
az login
az extension add --name containerapp --upgrade
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

az group create --name yourpath-rg --location westeurope
```

**База даних (PostgreSQL).** SQLite всередині контейнера не підходить: дані зникнуть при перезапуску.

```bash
az postgres flexible-server create \
  --resource-group yourpath-rg --name yourpath-db-<унікальне-ім'я> --location westeurope \
  --admin-user yourpath --admin-password '<надійний-пароль>' \
  --sku-name Standard_B1ms --tier Burstable --storage-size 32 --version 16 \
  --public-access 0.0.0.0          # дозволяє доступ службам Azure
az postgres flexible-server db create \
  --resource-group yourpath-rg --server-name yourpath-db-<унікальне-ім'я> --database-name yourpath
```

Рядок підключення: `postgresql://yourpath:<пароль>@yourpath-db-<ім'я>.postgres.database.azure.com:5432/yourpath?sslmode=require` (спецсимволи пароля треба закодувати для URL).

**Середовище й застосунок.**

```bash
az containerapp env create --name yourpath-env --resource-group yourpath-rg --location westeurope

az containerapp create --name yourpath --resource-group yourpath-rg --environment yourpath-env \
  --image docker.io/<user>/yourpath:latest \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 1 --cpu 0.5 --memory 1.0Gi \
  --secrets jwt-secret='<випадковий-рядок-від-48-символів>' db-url='<рядок-підключення>' \
  --env-vars APP_ENV=production COOKIE_SECURE=1 SEED_DEMO_DATA=0 \
             JWT_SECRET=secretref:jwt-secret DATABASE_URL=secretref:db-url \
             MS_TENANT_ID=<tenant-id> MS_CLIENT_ID=<client-id> ADMIN_EMAILS=<ваша-пошта>@ukma.edu.ua
```

Секрет для `JWT_SECRET`: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

> Тримайте **одну репліку** (`--min-replicas 1 --max-replicas 1`): міграції Alembic виконуються при старті, а фонові задачі синхронізації живуть у процесі застосунку.

Адреса застосунку (HTTPS видається автоматично):

```bash
az containerapp show --name yourpath --resource-group yourpath-rg \
  --query properties.configuration.ingress.fqdn --output tsv
```

Після цього додайте адресу в налаштування (вона відома лише тепер):

```bash
az containerapp update --name yourpath --resource-group yourpath-rg \
  --set-env-vars ALLOWED_REDIRECT_URIS=https://<fqdn>/auth/callback CORS_ORIGINS=https://<fqdn>
```

## 3. Microsoft Entra

В app registration: **Authentication → Add a platform → Single-page application** і додайте redirect URI `https://<fqdn>/auth/callback`. Без цього вхід через Microsoft у продакшні не спрацює. Якщо застосунок зареєстровано як Web, додайте `MS_CLIENT_SECRET` секретом (для SPA з PKCE він не потрібен).

## 4. Змінні середовища

| Змінна | Значення в production |
|---|---|
| `APP_ENV` | `production` (вимагає `MS_TENANT_ID`, `MS_CLIENT_ID` і `COOKIE_SECURE=1`) |
| `JWT_SECRET` | секрет, мінімум 32 символи (Azure secret) |
| `DATABASE_URL` | PostgreSQL з `?sslmode=require` (Azure secret) |
| `MS_TENANT_ID`, `MS_CLIENT_ID` | з app registration |
| `COOKIE_SECURE` | `1` (за замовчуванням) |
| `ALLOWED_REDIRECT_URIS` | `https://<fqdn>/auth/callback` |
| `CORS_ORIGINS` | `https://<fqdn>` |
| `ADMIN_EMAILS` | пошти, які при першому вході отримують роль адміністратора |
| `SEED_DEMO_DATA` | `0` (без демо-даних) |
| `FRONTEND_DIST`, `PORT` | задано в образі (`/app/frontend/dist`, `8000`) |

## 5. Перевірка

```bash
curl https://<fqdn>/health          # {"status":"ok",...}
```

Відкрийте `https://<fqdn>/`, увійдіть через Microsoft. Swagger UI: `https://<fqdn>/api-docs`. Журнал контейнера: `az containerapp logs show --name yourpath --resource-group yourpath-rg --follow`.

Перевірити образ локально до деплою: `JWT_SECRET=<32+ символів> docker compose --profile app up --build`, далі `http://localhost:8000`.

## 6. Оновлення версії

Опублікуйте новий тег образу й виконайте:

```bash
az containerapp update --name yourpath --resource-group yourpath-rg --image docker.io/<user>/yourpath:<новий-тег>
```

## Обмеження й безпека

- **Парсер САЗ у контейнері не працює**: Playwright і Chromium не входять в образ, а вхід у САЗ потребує видимого вікна браузера (`scripts/saz_login.py`). Для демо залишайте `SAZ_AUTORUN=0`. Запуск парсера в хмарі потребує окремого рішення.
- Не кладіть секрети в образ чи змінні збірки: `JWT_SECRET`, пароль бази й `MS_CLIENT_SECRET` передаються тільки як secrets Container Apps.
- Один образ і одна репліка достатні для навчального проєкту; горизонтальне масштабування потребує винесення міграцій і фонових задач.

## Орієнтовна вартість

PostgreSQL Burstable B1ms ≈ 12–15 USD на місяць, Container Apps при невеликому навантаженні кілька USD, Docker Hub безкоштовно (один приватний репозиторій). Точні ціни: [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/). Зупинка БД й застосунку, коли вони не потрібні, економить кошти.

---
**Нотатка щодо використання ШІ:** документ створено за допомогою Claude (Claude Code) за кодом проєкту (`Dockerfile`, `src/api/frontend_site.py`, `src/api/tokens.py`, `docker-compose.yml`). Команди `az` і параметри Azure не запускались у реальній підписці: їх треба перевірити під час першого розгортання за актуальною документацією Azure.
