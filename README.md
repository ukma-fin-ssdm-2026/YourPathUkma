![CI](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/actions/workflows/ci.yaml/badge.svg)

# YourPathUkma

> A web platform for NaUKMA Faculty of Informatics students to build
> personalized academic plans with AI-powered course recommendations.

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

Також: [Project-Description.md](Project-Description.md) (повний опис проєкту), [AGENTS.md](AGENTS.md) (контекст для AI-агентів), [frontend/README.md](frontend/README.md) (frontend).

## Командний процес
- [Командний статут (Team Charter)](TeamCharter.md), розділ 8 «Використання ШІ»
- [Процеси та мітки (Process Labels)](docs/process/labels.md)
- CI: [`ci.yaml`](.github/workflows/ci.yaml) (ruff, bandit, перевірка OpenAPI, pytest з порогом покриття 80%; frontend: npm audit, lint, typecheck, test, build), [`deploy-api-docs.yml`](.github/workflows/deploy-api-docs.yml) (публікація `docs/api` на GitHub Pages), [`label-sync.yml`](.github/workflows/label-sync.yml) (синхронізація міток), [`mutation.yml`](.github/workflows/mutation.yml) (мутаційне тестування, ручний запуск)

## Артефакти вимог
Документація за результатами Лабораторної роботи №2:
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

## Запуск API

Потрібні Python 3.12 і Node.js 22 (як у CI).

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn src.api.main:app --reload --port 3000   # Swagger UI: http://127.0.0.1:3000/api-docs
pytest -q
```

Без `DATABASE_URL` дані зберігаються в локальному файлі `yourpath.sqlite`; для PostgreSQL: `docker compose up -d db` і `DATABASE_URL` з [`.env.example`](.env.example). Усі змінні середовища необов'язкові, їхній перелік є в `.env.example`. Міграції (Alembic) і демо-дані застосовуються при старті. Деталі: [docs/architecture/data-model.md](docs/architecture/data-model.md).

## Запуск frontend

З теки `frontend/` (повний опис: [frontend/README.md](frontend/README.md)):

```bash
npm ci
npm run gen:api               # типи з docs/api/openapi-generated.json
cp .env.example .env.local    # VITE_USE_MOCKS=true: ендпоінти без бекенду замінюють моки
npm run dev                   # http://localhost:5173, запити /api проксуються на http://localhost:3000
```

Для роботи з реальними даними спершу запустіть API (розділ вище).

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

**Нотатка щодо використання ШІ (запуск і тести):** розділи «Запуск frontend» і «Тести» та версії Python/Node у «Запуск API» додано за допомогою Claude (Claude Code). Команди й версії звірено з `.github/workflows/ci.yaml`, `requirements-dev.txt` і `frontend/README.md`; самі команди з README я не запускав. Посилання на Swagger UI (GitHub Pages) перевірено запитом 2026-10-24: `/api/`, `/api/index.html` і `/api/openapi-generated.yaml` відповідають кодом 200.

**Нотатка щодо використання ШІ (карта документації):** розділи «Карта документації», «Командний процес», «API», «Якість коду», «Тестування» та оновлені списки в «Артефакти вимог» й «Архітектура» створено за допомогою Claude (Claude Code). Перевірено скриптом, що відносні посилання в `.md` файлах репозиторію ведуть на наявні файли; опис CI звірено з файлами в `.github/workflows/`.
