# Звіт про прогрес розробки та структуру проєкту (Progress Report)

**Проєкт:** YourPathUkma (REST API + вебфронтенд)  
**Відповідальні ролі:** Quality Lead & Prototype Lead  
**Станом на:** 2026-10-21  

## Статус

| Частина | Стан | Перевірка |
|---|---|---|
| Бекенд (`src/`) | MVP реалізовано | `pytest -q`: 101 пройшов, 1 пропущено, **3 падають** (`test_plan_validation.py::test_create_plan_still_rejects_business_rule_violation`, `test_request_id.py` ×2); ці падіння були й до змін у документації |
| Фронтенд (`frontend/`) | Усі екрани студента й адміністратора реалізовано, працює на MSW-моках | `vitest run`: 49 файлів, 434 тести проходять; `tsc --noEmit` і `eslint` без помилок |
| Інтеграція фронтенду з бекендом | Не завершена | Фронтенд викликає `POST /auth/microsoft`, бекенд поки має `POST /auth/google` (див. розділ 4) |

---

## 1. Бекенд: структура коду та модулів

Проєкт реалізовано на фреймворку **FastAPI** із використанням **SQLAlchemy ORM** та **Pydantic v2**, дотримуючись шарової архітектури (Layered Architecture):

```text
src/
├── api/
│   ├── main.py                  # Точка входу FastAPI, конфігурація CORS, реєстрація роутерів, генерація OpenAPI
│   ├── common.py                # Обробка помилок (ApiError), пагінація, залежність get_current_student_id
│   ├── onboarding.py            # Перевірка статусу онбордингу студента (get_onboarded_student)
│   ├── plan_checks.py           # Перевірки бізнес-правил плану
│   └── routes/
│       ├── auth.py              # Вхід через корпоративний акаунт Microsoft 365 (/auth/*), поки заглушка
│       ├── deanery.py           # Завантаження документів деканату (/deanery-documents)
│       ├── disciplines.py       # Каталог дисциплін з фільтрами та пагінацією (/disciplines)
│       ├── plans.py             # CRUD індивідуальних планів, validate, submit, export (/plans)
│       ├── preferences.py       # Побажання студента на навчальний рік (/preferences)
│       ├── reference.py         # Довідники напрямків та викладачів (/directions, /instructors)
│       ├── system.py            # Healthcheck та конфігурація (/health, /config)
│       ├── user.py              # Профіль студента та академічна історія (/me, /me/academic-history)
│       └── admin/               # Адміністративна панель (users, catalog, sync, audit)
└── db/
    ├── base.py                  # DeclarativeBase, функції нормалізації
    ├── enums.py                 # Enum-типи (PlanStatus, LoadLevel, Trimester тощо)
    ├── migrate.py               # Управління міграціями Alembic
    ├── session.py               # Сесії бази даних
    └── models/                  # SQLAlchemy ORM-моделі
```

---

## 2. Фронтенд: стек і структура

Теку `frontend/` створено як окремий SPA-застосунок, інтерфейс повністю українською. Покрокова історія розробки: гілки `feat/frontend-01-scaffold` … `feat/frontend-21a-full-mocks`, далі `feat/frontend-motion` (PR #112).

**Стек:** React 19, TypeScript (strict), Vite 8, Tailwind CSS 4, TanStack Query, Zustand, react-router 8, `@dnd-kit` (перетягування дисциплін), `sonner` (сповіщення). Тести: Vitest, Testing Library, MSW. Якість: ESLint (плагіни `jsx-a11y`, `security`, `react-hooks`), Prettier, типи API генеруються з `docs/api/openapi-generated.json` командою `npm run gen:api`.

```text
frontend/src/
├── api/              # fetch-клієнт, обробка помилок, токен, queryClient, типи (generated/ у .gitignore)
├── app/              # routes.tsx, AppLayout, ConnectedLayout, nav.ts, сторінки помилок
├── auth/             # Вхід Microsoft 365 (Authorization Code + PKCE): LoginPage, CallbackPage, login.ts, pkce.ts, session.ts, RequireAuth
├── features/
│   ├── profile/      # Профіль, онбординг (курс і спеціальність), журнал кредитів, ліміти
│   ├── catalog/      # Каталог дисциплін: фільтри, пошук із debounce, пагінація
│   ├── plans/        # Таблиця планів за роками, збережені плани, діалог підтвердження
│   ├── builder/      # Конструктор плану: каталог, три триместри, drag-and-drop, підсумок кредитів, збереження й подання
│   ├── deanery/      # Документ деканату, завантаження файлів, нормативні дисципліни
│   ├── preferences/  # Побажання: навантаження, напрямки, викладачі
│   ├── plan-view/    # Перегляд плану й експорт у PDF
│   └── admin/        # Огляд, модерація каталогу, синхронізація, користувачі, напрямки, журнал дій
├── lib/              # credits, trimester, datetime, bytes, initials, download
├── mocks/            # MSW-мок усього API (VITE_USE_MOCKS=full), роль адміна через VITE_MOCK_ROLE=admin
├── styles/           # tokens.css (змінні дизайн-системи), index.css (глобальні стилі й анімації)
├── ui/               # Button, Badge, Card, Segmented, Switch, CountUp, motion.ts, useDialogFocus
└── test/             # Налаштування Vitest, спільні обробники
```

Обсяг: близько 8 200 рядків застосунку (без тестів) і 52 файли тестів/допоміжних тестових модулів.

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

### Доменні правила на фронтенді

Конструктор і підсумок (`features/builder/plan.ts`, `SummaryStrip.tsx`, `lib/credits.ts`) показують ліміти кредитів (240 за 4 роки, вільний вибір до 25, профорієнтовні 54 або значення `professional_limit` з API), блокують подання плану лише з вільного вибору і перекладають серверні коди помилок (`saveErrors.ts`) у зрозумілі повідомлення. Нормативні дисципліни деканату тільки для читання.

### Дизайн і анімації

Дизайн «Credit Ledger»: токени кольору в `tokens.css`, шрифти Unbounded (заголовки й числа) та Onest (текст), пласкі поверхні з рамками. Гілка `feat/frontend-motion` додала шар руху без зміни макета:

- поява екранів і блоків (`rise`, `pop-in`) із каскадною затримкою через `--i`;
- смуги кредитів (`bar-grow`), клітинки таблиці планів (`cell-in`), числа `CountUp`;
- ковзне тло `Segmented`, пружна ручка `Switch`, підсвічування рядків таблиць;
- анімації виходу: діалог (`useExitTransition`) і картка дисципліни при видаленні з плану;
- плавні переходи між розділами й вкладками;
- повага до `prefers-reduced-motion`: рух вимкнено, дії виконуються одразу (`ui/motion.ts`, `canAnimate()`).

### Якість і CI

- CI (`.github/workflows/ci.yaml`, job `frontend`): `npm ci`, `gen:api`, `lint`, `typecheck`, `test`, `build`.
- Доступність: правила `jsx-a11y`, фокус у діалогах (`useDialogFocus`), ролі `progressbar`/`group`.
- Нові модулі руху покриті тестами (`ui/motion.test.tsx`: вихід діалогу, видалення картки, reduced-motion).

---

## 3. Що змінилося в документації

- Автентифікація описана як вхід через Microsoft 365 (раніше текст казав «Google Workspace SSO»), уточнено перевірки ID-токена (`tid`, домен пошти).
- Файли з теки `review/` перенесено в `docs/code-quality/` (`review-report.md` — порівняння ШІ-огляду й ручного, `received-review-report.md` — звіт щодо YourPathUkma API).
- Для змін у описах API перегенеровано `docs/api/openapi-generated.*`; у файлах виявлено накопичений дрейф зі стану коду, тому дифф великий.

## 4. Відомі розриви та обмеження

1. **Назви Google у коді бекенду.** Тексти оновлено, але ідентифікатори лишилися Google; фронтенд викликає `POST /auth/microsoft`. Що саме перенести, дивіться в розділі 5.
2. **Автентифікація й дані бекенду.** Перевірка коду Microsoft ще заглушка; реальної перевірки ID-токена немає.
3. **Тести бекенду.** 3 тести падають (див. таблицю статусу), їх треба виправити окремо.
4. **Фронтенд.** Працює проти MSW-моків; з живим бекендом не запускався. Анімації перевірено юніт-тестами та вручну в мок-режимі, автоматичних візуальних тестів немає. Prettier (CRLF) повідомляє про стильові розбіжності в 155 файлах, відомі й не виправлялися.
5. **Діаграми.** SVG-файли UML відредаговано вручну (PlantUML не запускався), ширину підписів може знадобитися уточнити перегенерацією.


## 5. Що потрібно перенести з Google на Microsoft

Тексти документації вже оновлено. Лишається змінити код і дані, перелік нижче.

### Бекенд (`src/`)

| Файл | Зараз | Потрібно |
|---|---|---|
| `src/api/routes/auth.py:102,108` | маршрут `POST /auth/google`, функція `login_with_google` | маршрут `POST /auth/microsoft`, функція `login_with_microsoft` (фронтенд викликає саме його: `frontend/src/auth/login.ts`) |
| `src/api/routes/auth.py:8,40` | схема `GoogleLoginRequest` | `MicrosoftLoginRequest` (поля `code`, `code_verifier`, `redirect_uri` лишаються); оновити згадку в docstring |
| `src/api/routes/auth.py` (логіка) | код не перевіряється, повертається тестовий студент | обмін коду з Microsoft Entra ID, перевірка ID-токена (`iss`, `aud`, `exp`, `tid` = tenant НаУКМА, домен пошти `ukma.edu.ua`), відповідь `403 DOMAIN_NOT_ALLOWED` для чужих доменів (її очікує мок `frontend/src/mocks/handlers.ts`) |
| `src/api/routes/system.py:46,64` | поле `google_client_id`, змінна `GOOGLE_CLIENT_ID` зі значенням `...apps.googleusercontent.com` | `microsoft_client_id` (або `ms_client_id`), змінна `MS_CLIENT_ID`, плюс `MS_TENANT`; фронтенд бере їх з `VITE_MS_CLIENT_ID` і `VITE_MS_TENANT`, тому узгодити назви |

### База даних

| Файл | Зараз | Потрібно |
|---|---|---|
| `src/db/models/users.py:24` | колонка `User.google_sub` (unique) | `User.ms_sub` (субʼєкт `oid`/`sub` із токена Microsoft) |
| `migrations/versions/0001_initial_schema.py:56,68` | `google_sub`, constraint `uq_users_google_sub` | не редагувати, а додати нову міграцію Alembic: `op.alter_column("users", "google_sub", new_column_name="ms_sub")` і перейменування constraint `uq_users_ms_sub`; для вже існуючих користувачів `sub` Google не збігається із Microsoft, тому потрібен план звʼязування акаунтів за `email` |
| `src/db/seed.py:106` | `User(..., google_sub=f"seed-{user_id}")` | `ms_sub=...` |

### Тести

| Файл | Потрібно |
|---|---|
| `tests/test_auth.py:1,16,32` | URL `/api/v1/auth/microsoft`, оновити docstring |
| `tests/test_api_smoke.py:60` | шлях `/api/v1/auth/microsoft` у перевірці наявності маршрутів |
| `tests/test_plan_rules.py:2,14,22,25` | імпорт і використання `MicrosoftLoginRequest`, docstring |

### Контракт і документація

| Файл | Потрібно |
|---|---|
| `docs/api/openapi-generated.{json,yaml}` | перегенерувати: `python scripts/generate_openapi.py` (зміниться шлях, `operationId`, схема, поле `/config`); CI вимагає коміту цих файлів |
| `docs/api/contract.md:262,336,375,404,1394,1542,1575` | `/auth/google` → `/auth/microsoft`, `google_client_id` → нове поле, приклад `client_id` без `googleusercontent.com`, заголовок розділу `POST /auth/google` |
| `docs/architecture/data-model.md:43,70`, `threat-model.md:16,46`, `uml/data-model.plantuml:32`, `uml/deployment.puml:48` (+ `svg/`) | `google_sub` → `ms_sub` |

### Порядок виконання

1. Нова гілка від `main`: перейменування у `auth.py`, `system.py`, `users.py`, `seed.py`.
2. Міграція Alembic для колонки й constraint.
3. Оновити тести, прогнати `pytest -q`.
4. `python scripts/generate_openapi.py`, оновити `contract.md` і діаграми, закомітити.
5. `cd frontend && npm run gen:api && npm test`, щоб переконатися, що згенеровані типи збігаються зі схемою.
6. Задати `MS_CLIENT_ID`/`MS_TENANT` на бекенді та `VITE_MS_CLIENT_ID`/`VITE_MS_TENANT` на фронтенді, перевірити вхід з реальним акаунтом `@ukma.edu.ua`.

---

**Використання ШІ:** структуру фронтенду, таблиці та оновлення цього звіту підготовлено за допомогою ШІ (Claude, Anthropic) на основі читання коду `frontend/` та `src/`. Перевірка: числа тестів отримано запуском `pytest -q` і `vitest run`, перелік файлів і маршрутів звірено з `frontend/README.md` та `frontend/src/app/routes.tsx`; застосунок з живим бекендом не запускався.
