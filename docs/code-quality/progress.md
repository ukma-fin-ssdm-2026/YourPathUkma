# Звіт про прогрес розробки та структуру проєкту (Progress Report)

**Проєкт:** YourPathUkma (REST API + вебфронтенд)  
**Відповідальні ролі:** Quality Lead & Prototype Lead  
**Станом на:** 2026-11-01  

## Статус

| Частина | Стан | Перевірка |
|---|---|---|
| Бекенд (`src/`) | MVP реалізовано, вхід через Microsoft Entra ID працює (обмін коду, перевірка `id_token`, refresh-токени) | `pytest --cov=src -q`: **389 пройшли, 1 пропущено, 0 падінь**; покриття **84%** рядків і гілок (`--cov-branch`; лише за рядками 87%; 3156 рядків, 419 не покрито) |
| Фронтенд (`frontend/`) | Усі екрани студента й адміністратора реалізовано; вхід Microsoft 365 (Authorization Code + PKCE + nonce) підключено до бекенду | `vitest run`: **49 файлів, 443 тести проходять** |
| Інтеграція фронтенду з бекендом | Контракт входу узгоджено (`POST /auth/microsoft`); наскрізний сценарій із реальним акаунтом не перевірявся | див. розділ 4 |

Порівняно зі звітом від 21.10: тести бекенду зросли з 101 до 389, три тести, що падали (`test_plan_validation.py::test_create_plan_still_rejects_business_rule_violation`, `test_request_id.py` ×2), тепер проходять; тести фронтенду зросли з 434 до 443.

---

## 1. Бекенд: структура коду та модулів

Проєкт реалізовано на фреймворку **FastAPI** із використанням **SQLAlchemy ORM** та **Pydantic v2**, дотримуючись шарової архітектури (Layered Architecture):

```text
src/
├── api/
│   ├── main.py                  # Точка входу FastAPI, CORS, реєстрація роутерів, генерація OpenAPI
│   ├── common.py                # Обробка помилок (ApiError), пагінація, залежність get_current_student_id
│   ├── microsoft.py             # Вхід через Microsoft Entra ID: обмін коду, перевірка id_token
│   ├── auth_service.py          # Створення/пошук користувача, refresh-токени (ротація, відкликання)
│   ├── tokens.py                # Налаштування автентифікації, власні JWT доступу
│   ├── onboarding.py            # Перевірка статусу онбордингу студента
│   ├── plan_checks.py           # Перевірки бізнес-правил плану
│   └── routes/
│       ├── auth.py              # Маршрути /auth/*
│       ├── ai.py                # Генерація планів за допомогою ШІ
│       ├── certificates.py      # Сертифікатні програми
│       ├── deanery.py           # Документи деканату (/deanery-documents)
│       ├── disciplines.py       # Каталог дисциплін з фільтрами та пагінацією
│       ├── plans.py             # CRUD планів, validate, submit, export
│       ├── preferences.py       # Побажання студента на навчальний рік
│       ├── reference.py         # Довідники напрямків та викладачів
│       ├── system.py            # /health, /config
│       ├── user.py              # Профіль і академічна історія (/me)
│       └── admin/               # audit, catalog, certificates, sync, users
├── db/
│   ├── base.py, enums.py, config.py, session.py
│   ├── migrate.py               # Alembic
│   ├── seed.py                  # Початкові дані
│   └── models/                  # admin, ai, catalog, deanery, history, plans, preferences, users
├── parser/                      # Синхронізація каталогу із системи САЗ (fetcher, parsers/, diff, mapper, sync)
└── services/                    # email_domain, load_levels, plan_rules
```

Також у репозиторії: `migrations/versions/0001…0004` (остання, `0004_microsoft_auth.py`, переводить користувачів на Microsoft), `scripts/` (`generate_openapi.py`, `issue_token.py`, `saz_*.py`), `mcp/mcp_server.py`.

### Вхід через Microsoft (реалізовано)

- `microsoft.py` обмінює код авторизації на `id_token` через токен-ендпоінт Microsoft, перевіряє підпис за ключами JWKS (RS256), `iss`, `aud`, `exp`, `iat`, `tid` та `nonce`; поштовий домен звіряється зі списком дозволених, інакше `403 EMAIL_DOMAIN_NOT_ALLOWED`. Помилки провайдера дають `401` (`INVALID_AUTH_CODE`, `INVALID_ID_TOKEN`, `INVALID_NONCE`) або `503`.
- `auth_service.py` знаходить користувача за `ms_oid` (для старих записів за поштою, поки `ms_tid` порожній) або створює нового зі студентським профілем; адміністраторами стають пошти зі списку `admin_emails`.
- Refresh-токени зберігаються лише як SHA-256 хеш, ротуються при кожному оновленні й належать до «сімейства»; повторне використання вже відкликаного токена відкликає все сімейство (`REFRESH_TOKEN_REUSED`).

### Покриття тестами

Загальне покриття 84% рядків і гілок (87% лише за рядками). Найнижче: `src/parser/auth.py` (0%), `src/api/auth_service.py` (31%), `src/api/microsoft.py` (34%), `src/api/routes/admin/certificates.py` (38%). Низьке покриття модулів входу пояснюється тим, що тести лише підміняють `httpx.post` (`tests/test_auth.py`) і не перевіряють успішний прохід: підпис `id_token` за JWKS, `nonce`, домен пошти, створення користувача й ротацію refresh-токенів.

---

## 2. Фронтенд: стек і структура

Теку `frontend/` створено як окремий SPA-застосунок, інтерфейс повністю українською.

**Стек:** React 19, TypeScript (strict), Vite 8, Tailwind CSS 4, TanStack Query, Zustand, react-router 8, `@dnd-kit`, `sonner`. Тести: Vitest, Testing Library, MSW. Якість: ESLint (`jsx-a11y`, `security`, `react-hooks`), Prettier, типи API генеруються з `docs/api/openapi-generated.json` командою `npm run gen:api`. Для запуску потрібен Node.js 22.12 або новіший (на Node 20 `vitest` і `rolldown` не стартують).

```text
frontend/src/
├── api/        # fetch-клієнт (одноразовий refresh на 401), помилки, токен, queryClient, типи
├── app/        # routes.tsx, AppLayout, ConnectedLayout, nav.ts, сторінки помилок
├── auth/       # Вхід Microsoft 365: LoginPage, CallbackPage, login.ts, pkce.ts, session.ts, RequireAuth
├── features/   # profile, catalog, plans, builder, deanery, preferences, plan-view, admin
├── lib/        # credits, trimester, datetime, bytes, initials, download
├── mocks/      # MSW-мок усього API (VITE_USE_MOCKS=full), роль адміна через VITE_MOCK_ROLE=admin
├── styles/     # tokens.css, index.css
├── ui/         # Button, Badge, Card, Segmented, Switch, CountUp, motion.ts, useDialogFocus
└── test/       # Налаштування Vitest, спільні обробники
```

### Інтеграція з бекендом

- `auth/login.ts` будує адресу авторизації Microsoft з `state`, `nonce` і PKCE-викликом `code_challenge`, а після повернення надсилає на `POST /auth/microsoft` поля `code`, `code_verifier`, `nonce` і `redirect_uri`. Обмін коду й перевірку `id_token` виконує бекенд.
- `api/client.ts` додає Bearer-токен, а при відповіді `401` один раз оновлює токен (паралельні запити ділять один виклик refresh); якщо оновлення не вдалося, сесія вважається втраченою.
- Без налаштованого `VITE_MS_CLIENT_ID` та з `VITE_USE_MOCKS=true` фронтенд імітує вхід через мок-обробник.

### Екрани

| Маршрут | Що робить |
|---|---|
| `/login`, `/auth/callback` | Вхід через Microsoft 365 |
| `/onboarding` | Курс і спеціальність при першому вході |
| `/` | Профіль і журнал кредитів за курсами |
| `/path/plan`, `/path/saved` | Плани за роками, збережені плани |
| `/path/create` | Конструктор плану (+ `/document` і `/preferences`) |
| `/path/plan/:id` | Перегляд плану й експорт у PDF |
| `/catalog` | Каталог дисциплін |
| `/admin/*` | Лише для ролі `admin`: огляд, модерація, синхронізація, користувачі, напрямки, журнал |

Дизайн «Credit Ledger» з шаром анімацій (`feat/frontend-motion`, з урахуванням `prefers-reduced-motion`) і доменні правила кредитів (240 за 4 роки, вільний вибір до 25, профорієнтовні 54 або `professional_limit` з API) описано в `frontend/README.md`.

### Якість і CI

CI (`.github/workflows/ci.yaml`, job `frontend`): `npm ci`, `gen:api`, `lint`, `typecheck`, `test`, `build`. Доступність: правила `jsx-a11y`, фокус у діалогах, ролі `progressbar`/`group`.

---

## 3. Що змінилося з 21.10

- Автентифікація переведена з Google на Microsoft Entra ID у коді, базі даних (міграція `0004_microsoft_auth.py`) і тестах; фронтенд і бекенд використовують один маршрут `POST /auth/microsoft`.
- Перевірка коду авторизації більше не заглушка: реалізовано обмін коду, перевірку підпису й claims `id_token`, ротацію refresh-токенів.
- Усі тести бекенду проходять (раніше три падали). Старий маршрут `POST /auth/google` видалено.
- Документацію API та моделі даних узгоджено з Microsoft-автентифікацією (`docs/api/`, `docs/architecture/`).

## 4. Відомі розриви та обмеження

1. **Залишки Google у коді.** Маршрут `POST /auth/google` видалено (тест `test_legacy_google_login_endpoint_is_removed` це перевіряє), але в `src/api/routes/system.py` поле відповіді `/config` досі називається `google_client_id`, а значення береться зі змінної `GOOGLE_CLIENT_ID` з типовим `dev-client-id.apps.googleusercontent.com`, хоча опис поля вже говорить про Microsoft. Також у службовому коментарі `src/api/routes/auth.py` (рядок 8) лишилася згадка `GoogleLoginRequest`. Перейменування поля `/config` змінює контракт API, тому його треба робити разом із фронтендом (`VITE_MS_CLIENT_ID`) і перегенерацією `docs/api/openapi-generated.*`.
2. **Вхід із реальним акаунтом.** Обмін коду з Microsoft залежить від зовнішнього сервісу, а тести лише підміняють `httpx.post` і не перевіряють успішний вхід (покриття `microsoft.py` 34%); сценарій із реальним акаунтом `@ukma.edu.ua` на розгорнутому застосунку окремо не фіксувався.
3. **Наскрізний сценарій.** Фронтенд у тестах працює проти MSW-моків; повний прохід студента й адміністратора на живому бекенді варто пройти перед записом демонстраційного відео.
4. **Парсер САЗ.** `src/parser/auth.py` не покрито тестами (0%), `fetcher.py` покрито на 67%.
5. **Фронтенд.** `tsc`, `eslint` і Prettier для цього звіту повторно не запускалися; у попередньому звіті Prettier (CRLF) повідомляв про стильові розбіжності в 155 файлах. Автоматичних візуальних тестів анімацій немає.
6. **Залежності.** `npm ci` повідомляє про 14 вразливостей середньої серйозності в залежностях фронтенду (`npm audit`), їх ще не опрацьовано.
7. **Діаграми.** SVG-файли UML редагувалися вручну (PlantUML не запускався), підписи може знадобитися уточнити перегенерацією.

---

**Використання ШІ:** оновлення цього звіту підготовлено за допомогою ШІ (Claude, Anthropic) на основі попередньої версії документа, вихідного коду `src/api/microsoft.py`, `src/api/auth_service.py`, `frontend/src/auth/login.ts`, `frontend/src/api/client.ts`, структури репозиторію та виводу тестів. Перевірка: цифри отримано власним запуском `pytest --cov=src --cov-branch -q` (389 пройшли, 1 пропущено, 84% рядків і гілок) і `npm test -- --run` (49 файлів, 443 тести) 01.11.2026; вміст `src/api/routes/auth.py` повністю не переглядався (залишки Google знайдено командою `grep -rni google src tests`), застосунок із реальним акаунтом Microsoft не запускався.
