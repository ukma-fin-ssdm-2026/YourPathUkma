![CI](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/actions/workflows/ci.yaml/badge.svg)

# YourPathUkma

> A web platform for NaUKMA Faculty of Informatics students to build
> personalized academic plans with AI-powered course recommendations.

**Онлайн-версія:** [https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io](https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io) · [Розгорнута система](docs/deployment/deployed-system.md)

## Team

| Member | GitHub | Email |
|---|---|---|
| Оксана | [@Sanna001](https://github.com/Sanna001) | o.afanasieva@ukma.edu.ua |
| Данило | [@nemaproblem478](https://github.com/nemaproblem478) | d.savchuk@ukma.edu.ua |
| Дар'я | [@dchorna](https://github.com/dchorna) | d.chorna@ukma.edu.ua |
| Владислав | [@zarraban](https://github.com/zarraban) | vl.smyrnov@ukma.edu.ua |

## Overview

YourPathUkma helps students of the Faculty of Informatics at NaUKMA
build their individual academic plan for each year of study.

The platform allows students to:
- choose elective courses and distribute them across trimesters
- track credit load progress (240 credits over 4 years)
- receive personalized AI recommendations based on their chosen
  development directions

> Mandatory courses are fully determined by the dean's office and are
> not selected by the student — they are only displayed in the plan
> builder for load visibility.

Students sign in via their corporate NaUKMA email.

## Розгорнута система

Застосунок розгорнуто публічно в Microsoft Azure (Azure Container Apps і Azure Database for PostgreSQL, один Docker-образ):

- **Сайт:** [https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io](https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io) (вхід лише з поштою `@ukma.edu.ua` через Microsoft)
- **Swagger UI розгорнутого API:** [https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io/api-docs](https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io/api-docs)
- Опис, схема, обмеження й перевірка: [docs/deployment/deployed-system.md](docs/deployment/deployed-system.md)

---

## Карта документації

Артефакти за лабораторними роботами. Відеозвіти (Loom) лежать у [`Labs`](Labs/) у файлах `LabNN/video_<ім'я>.txt`.

| Лаб. | Тема | Розділ README | Папка |
|---|---|---|---|
| 1 | Командна робота, CI | [Командний процес](#командний-процес) | корінь, [`.github/workflows/`](.github/workflows/) |
| 2 | Вимоги | [Артефакти вимог](#артефакти-вимог) | [`docs/requirements/`](docs/requirements/) |
| 3 | Архітектура | [Архітектура](#архітектура) | [`docs/architecture/`](docs/architecture/) |
| 4 | API | [API](#api) | [`docs/api/`](docs/api/) |
| 5 | Якість коду | [Якість коду](#якість-коду) | [`docs/code-quality/`](docs/code-quality/) |
| 6 | Тестування | [Тестування](#тестування) | [`docs/testing/`](docs/testing/) |
| 7 | Валідація й рефакторинг | [Валідація](#валідація), [Рефакторинг](#рефакторинг) | [`docs/validation/`](docs/validation/), [`docs/refactoring/`](docs/refactoring/) |

Також: [Project-Description.md](Project-Description.md) (повний опис проєкту), [AGENTS.md](AGENTS.md) (контекст для AI-агентів), [frontend/README.md](frontend/README.md) (frontend).

## Командний процес
- [Командний статут (Team Charter)](TeamCharter.md), розділ 8 «Використання ШІ»
- [Процеси та мітки (Process Labels)](docs/process/labels.md)
- CI: [`ci.yaml`](.github/workflows/ci.yaml) (ruff, bandit, перевірка OpenAPI, pytest з порогом покриття 80%; frontend: npm audit, lint, typecheck, test, build), [`deploy-api-docs.yml`](.github/workflows/deploy-api-docs.yml) (публікація `docs/api` на GitHub Pages), [`label-sync.yml`](.github/workflows/label-sync.yml) (синхронізація міток), [`mutation.yml`](.github/workflows/mutation.yml) (мутаційне тестування, ручний запуск)

## Артефакти вимог
Документація за результатами Лабораторної роботи №2:
- [Міні-ТЗ (одна сторінка)](docs/requirements/mini-spec.md)
- [Системні вимоги (FR та NFR)](docs/requirements/requirements.md)
- [Користувацькі історії (User Stories)](docs/requirements/user-stories.md)
- [Матриця простежуваності (RTM)](docs/requirements/rtm.md)

## Архітектура
Архітектурна документація: [`/docs/architecture/`](docs/architecture/)

- [High-Level Design](docs/architecture/high-level-design.md)
- [Матриця простежуваності (вимоги → компоненти)](docs/architecture/traceability-matrix.md)
- [Модель даних](docs/architecture/data-model.md)
- [Модель загроз (STRIDE)](docs/architecture/threat-model.md)
- ADR: [ADR-001 (модульний моноліт)](docs/architecture/decisions/ADR-001.md), [ADR-002 (черга модерації парсера САЗ)](docs/architecture/decisions/ADR-002.md), [ADR-003 (ізоляція даних для AI)](docs/architecture/decisions/ADR-003.md)
- UML-діаграми ([джерела](docs/architecture/uml/)): [компонентів](docs/architecture/uml/svg/component-diagram.svg), [послідовності](docs/architecture/uml/svg/sequence-generate-plan.svg), [розгортання](docs/architecture/uml/svg/deployment.svg), [моделі даних](docs/architecture/uml/svg/data-model.svg)

## API
Документація API: [`/docs/api/`](docs/api/)

- [Проєктування API](docs/api/api-design.md)
- [API-контракт фронтенду і бекенду](docs/api/contract.md)
- [Атрибути якості API (NFR)](docs/api/quality-attributes.md)
- OpenAPI, згенерований з коду: [YAML](docs/api/openapi-generated.yaml), [JSON](docs/api/openapi-generated.json)
- **Онлайн-документація API (GitHub Pages):** [Swagger UI](https://ukma-fin-ssdm-2026.github.io/YourPathUkma/api/) (сторінка [`docs/api/index.html`](docs/api/index.html); сайт публікується з теки `docs/` гілки `main`)

## Якість коду
Документація: [`/docs/code-quality/`](docs/code-quality/)

- [Звіт про код-рев'ю](docs/code-quality/review-report.md): порівняння ручного й AI-рев'ю проєкту іншої команди ([ручне рев'ю](docs/code-quality/unispace_review.md), [AI-рев'ю](docs/code-quality/raw-ai-review.md))
- [Отримане рев'ю нашого коду](docs/code-quality/received-review-report.md)
- [Статичний аналіз (ruff, bandit, npm audit)](docs/code-quality/static-analysis.md)
- [Прогрес реалізації](docs/code-quality/progress.md)

## Тестування
Документація: [`/docs/testing/`](docs/testing/)

- [Стратегія тестування](docs/testing/testing-strategy.md)
- [Журнал налагодження](docs/testing/debugging-log.md)
- [Нотатки про якість тестів](docs/testing/test-quality-notes.md)
- [Звіт про покриття (HTML)](docs/testing/coverage/README.md)

## Валідація
Документація: [`/docs/validation/`](docs/validation/)

- [Тест-план](docs/validation/test-plan.md): тест-кейси TP-01…TP-18 для правил плану, API планів і каталогу дисциплін, ризики й критерії виходу; бонуси: таблиця переходів між станами плану (ST-01…ST-13) і виконуваний нефункціональний тест SEC-001
- [Журнал оглядів](docs/validation/review-log.md): огляд нашого тест-плану командою Rehab і внесені зміни; огляд PR із тестами, згенерованими ШІ

## Рефакторинг
Документація: [`/docs/refactoring/`](docs/refactoring/)

- [Звіт про аналіз якості коду в SonarCloud](docs/refactoring/sonarcloud-report.md): проблеми за категоріями (Security, Reliability, Maintainability, Duplications) і статуси їх виправлення

## Запуск API

Потрібні Python 3.12 і Node.js 22 (як у CI).

```bash
cp .env.example .env                            # Windows (cmd): copy .env.example .env
# Секрет підпису токенів (мінімум 32 символи) записується в .env; без нього API не стартує
python -c "import re,secrets,pathlib; p=pathlib.Path('.env'); p.write_text(re.sub(r'(?m)^JWT_SECRET=.*$', 'JWT_SECRET='+secrets.token_urlsafe(48), p.read_text()))"
pip install -r requirements.txt -r requirements-dev.txt
uvicorn src.api.main:app --reload --port 3000   # Swagger UI: http://127.0.0.1:3000/api-docs
pytest -q
```

Файл `.env` застосунок читає сам при старті (`python-dotenv`). **Обов'язкова лише `JWT_SECRET`** (не менше 32 символів, інакше застосунок зупиняється на старті). Решта має типові значення:

| Змінна | Коли потрібна |
|---|---|
| `DATABASE_URL` | не потрібна поза production: без неї дані зберігаються в локальному файлі `yourpath.sqlite` (при `APP_ENV=production` змінна обов'язкова); для PostgreSQL: `docker compose up -d db` і значення з [`.env.example`](.env.example) |
| `MS_TENANT_ID`, `MS_CLIENT_ID` (і `MS_CLIENT_SECRET` для типу застосунку Web) | для входу через Microsoft і обов'язково при `APP_ENV=production` |
| `ADMIN_EMAILS` | пошти, які при першому вході отримують роль адміністратора |
| `COOKIE_SECURE=0` | лише для `http://localhost` (Safari); у production заборонено |

Міграції (Alembic) і демо-дані застосовуються при старті. Деталі: [docs/architecture/data-model.md](docs/architecture/data-model.md).

## Запуск frontend

З теки `frontend/` (повний опис: [frontend/README.md](frontend/README.md)):

```bash
npm ci
npm run gen:api               # типи з docs/api/openapi-generated.json
cp .env.example .env.local    # VITE_USE_MOCKS=true: ендпоінти без бекенду замінюють моки
npm run dev                   # http://localhost:5173, запити /api проксуються на http://localhost:3000
```

Для роботи з реальними даними спершу запустіть API (розділ вище).

## Вхід у застосунок

Є два способи ввійти: з власною реєстрацією застосунку в Microsoft Entra або без неї.

### Варіант A. Реальний вхід через Microsoft Entra

1. У Microsoft Entra (tenant НаУКМА) створіть app registration з redirect URI `http://localhost:5173/auth/callback`.
2. У `.env` (корінь) заповніть `MS_TENANT_ID`, `MS_CLIENT_ID` (і `MS_CLIENT_SECRET`, якщо тип застосунку Web), `JWT_SECRET`, `ALLOWED_REDIRECT_URIS`, `COOKIE_SECURE=0` для `http://localhost`, а в `ADMIN_EMAILS` вкажіть свою пошту, щоб отримати роль адміністратора.
3. У `frontend/.env.local` (`cp .env.example .env.local`) задайте `VITE_USE_MOCKS=false`, `VITE_MS_CLIENT_ID` і `VITE_MS_TENANT` (ті самі значення, що в `.env`), запустіть API і `npm run dev`.

Докладніше: [frontend/README.md](frontend/README.md).

### Варіант B. Без власної реєстрації в Entra

**Інтерфейс із моками.** У `frontend/.env.local` задайте:

```bash
VITE_USE_MOCKS=true        # вхід і адмінка на моках, решта запитів іде на реальний API
# VITE_USE_MOCKS=full      # моки всього, бекенд не потрібен
VITE_MOCK_ROLE=admin       # необов'язково: екрани адміністратора (користувачі, модерація, синхронізація, журнал дій)
```

`VITE_MS_CLIENT_ID` залиште порожнім і натисніть «Увійти через Microsoft»: з увімкненими моками застосунок імітує повернення з Microsoft і входить мок-користувачем. Без `VITE_MOCK_ROLE` це студент.

**API та Swagger.** Токен для демо-користувача з бази:

```bash
python -m scripts.issue_token admin@ukma.edu.ua     # адміністратор
python -m scripts.issue_token student@ukma.edu.ua   # студент 2 курсу
```

Скрипт друкує access-токен (живе 15 хв, потрібен `JWT_SECRET` у `.env`). Вставте його в Authorize у Swagger UI (`/api-docs`) або передайте заголовком `Authorization: Bearer <токен>`. Демо-користувачі створюються разом із демо-даними при першому старті API.

## Docker і розгортання

Фронтенд і API збираються в один образ (`Dockerfile`): API сам роздає зібраний фронтенд, тож на Azure достатньо одного контейнера й бази PostgreSQL. Перевірити образ локально разом із базою:

```bash
JWT_SECRET=<мінімум 32 символи> docker compose --profile app up --build   # http://localhost:8000
```

Публікація на Docker Hub (workflow [`docker-publish.yml`](.github/workflows/docker-publish.yml)) і розгортання на Azure Container Apps: [docs/deployment/azure.md](docs/deployment/azure.md). Розгорнутої системи за публічною адресою поки немає.

## Тести

```bash
# backend (з кореня), команда як у CI з порогом покриття 80%
pytest -q --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=80

# frontend (з frontend/)
npm test
npm run lint
npm run typecheck
```

Звіт про покриття: [docs/testing/coverage/](docs/testing/coverage/README.md).

## Запуск MCP Сервера (Бонус до Лаб 4)
У проєкті реалізовано автоматичну генерацію MCP-сервера напряму з FastAPI за допомогою `fastmcp`.

**Як запустити та перевірити через MCP Inspector:**
1. Встановіть залежність: `pip install fastmcp`
2. Запустіть Inspector (переконайтеся, що ви знаходитесь у корені проєкту):
   ```bash
   npx @modelcontextprotocol/inspector python mcp/mcp_server.py
   ```
3. У браузері відкриється сторінка Inspector. Ви побачите всі кінцеві точки (наприклад, `health_check`, `list_plans`) як готові інструменти з описами, підтягнутими зі Swagger!

**Підключення до агента (наприклад, Claude Desktop):**
Додайте наступний блок до вашого `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "YourPathUkma": {
      "command": "python",
      "args": ["АБСОЛЮТНИЙ_ШЛЯХ_ДО_ПРОЄКТУ/mcp/mcp_server.py"]
    }
  }
}
```

---
**Нотатка щодо використання ШІ (Бонус MCP)**
* **Агент:** Antigravity (Google)
* **Що створено:** Файл `mcp/mcp_server.py` та інструкція в README.
* **Який виклик:** "Получиться ли слеать MCP сервер по етому примеру именно для нашего проекта"
* **Що спрацювало не так (обмеження автогенерації):** Оскільки наш API вимагає авторизації, `fastmcp` намагатиметься перетворити FastAPI `Depends()` на звичайні вхідні параметри для інструмента. Якщо ШІ-агент не знатиме, як згенерувати токен, він не зможе успішно виконати запити до захищених маршрутів. Щоб агент працював ідеально, у майбутньому доведеться написати спеціальні "обгортки" (wrappers) для функцій безпосередньо під MCP, щоб вони ігнорували JWT авторизацію і працювали від імені тестового студента.

---
**Нотатка щодо використання ШІ (посилання на API-контракт):** рядок із посиланням на `docs/api/contract.md` у розділі «Архітектура» додано за допомогою Claude (Claude Code); перевірено, що файл існує за цим шляхом.

**Нотатка щодо використання ШІ (розгорнута система):** рядок про онлайн-версію, розділ «Розгорнута система» і сторінку `docs/deployment/deployed-system.md` створено за допомогою Claude (Claude Code) за станом реального розгортання в Azure. Перевірка: `GET /health` = 200, сайт і Swagger відкриваються.

**Нотатка щодо використання ШІ (запуск, змінні середовища, вхід):** розділи «Запуск API» (кроки з `.env` і `JWT_SECRET`, таблиця змінних) і «Вхід у застосунок» створено за допомогою Claude (Claude Code) за зауваженнями репетиції проміжного оцінювання. Перевірка: порожній `.env` без `JWT_SECRET` зупиняє старт, а після кроків з README API стартує; `scripts/issue_token.py` видає токен, який приймає API.

**Нотатка щодо використання ШІ (запуск і тести):** розділи «Запуск frontend» і «Тести» та версії Python/Node у «Запуск API» додано за допомогою Claude (Claude Code). Команди й версії звірено з `.github/workflows/ci.yaml`, `requirements-dev.txt` і `frontend/README.md`; самі команди з README я не запускав. Посилання на Swagger UI (GitHub Pages) перевірено запитом 2026-10-24: `/api/`, `/api/index.html` і `/api/openapi-generated.yaml` відповідають кодом 200.

**Нотатка щодо використання ШІ (міні-ТЗ):** посилання на міні-ТЗ у розділі «Артефакти вимог» додано за допомогою Claude (Claude Code); перевірено, що файл існує.

**Нотатка щодо використання ШІ (карта документації):** розділи «Карта документації», «Командний процес», «API», «Якість коду», «Тестування» та оновлені списки в «Артефакти вимог» й «Архітектура» створено за допомогою Claude (Claude Code). Перевірено скриптом, що відносні посилання в `.md` файлах репозиторію ведуть на наявні файли; опис CI звірено з файлами в `.github/workflows/`.

**Нотатка щодо використання ШІ (валідація й рефакторинг):** рядок «7» у «Карті документації» та розділи «Валідація» і «Рефакторинг» додано за допомогою Claude. Опис складено за початками `docs/validation/test-plan.md`, `docs/validation/review-log.md` і `docs/refactoring/sonarcloud-report.md`; існування файлів за вказаними шляхах звірено зі структурою репозиторію. Посилання-якорі `#валідація` і `#рефакторинг` скриптом не перевірялись.
