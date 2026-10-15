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
Full documentation: [Project-Description.md](Project-Description.md)

Frontend: [frontend/README.md](frontend/README.md)
## Артефакти вимог
Документація за результатами Лабораторної роботи №2:
- [Системні вимоги (FR та NFR)](docs/requirements/requirements.md)
- [Користувацькі історії (User Stories)](docs/requirements/user-stories.md)
- [Матриця простежуваності (RTM)](docs/requirements/rtm.md)
- [Командний статут (Team Charter)](TeamCharter.md)
- [Процеси та мітки (Process Labels)](docs/process/labels.md)

## Архітектура
Архітектурна документація: [`/docs/architecture/`](docs/architecture/)

- [High-Level Design](docs/architecture/high-level-design.md)
- [Матриця простежуваності](docs/architecture/traceability-matrix.md)
- [Модель даних](docs/architecture/data-model.md)
- [Модель загроз (STRIDE)](docs/architecture/threat-model.md)
- [ADR](docs/architecture/decisions/)
- [API-контракт фронтенду і бекенду](docs/api/contract.md)
- UML-діаграми: [компонентів](docs/architecture/uml/svg/component-diagram.svg), [послідовності](docs/architecture/uml/svg/sequence-generate-plan.svg), [розгортання](docs/architecture/uml/svg/deployment.svg)

## Запуск API

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn src.api.main:app --reload --port 3000   # Swagger UI: http://127.0.0.1:3000/api-docs
pytest -q
```

Без `DATABASE_URL` дані зберігаються в локальному файлі `yourpath.sqlite`; для PostgreSQL: `docker compose up -d db` і `DATABASE_URL` з [`.env.example`](.env.example). Міграції (Alembic) і демо-дані застосовуються при старті. Деталі: [docs/architecture/database.md](docs/architecture/database.md).

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
