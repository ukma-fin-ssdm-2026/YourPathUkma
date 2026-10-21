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

1. **Назви Google у коді бекенду.** Тексти оновлено, але ідентифікатори лишилися: маршрут `POST /auth/google`, модель `GoogleLoginRequest`, колонка `User.google_sub`, поле `google_client_id` у `/config`, змінна `GOOGLE_CLIENT_ID`. Фронтенд викликає `POST /auth/microsoft` і очікує `VITE_MS_CLIENT_ID`, тому для інтеграції потрібне окреме перейменування (маршрут, схема, міграція Alembic, тести, OpenAPI).
2. **Автентифікація й дані бекенду.** Перевірка коду Microsoft ще заглушка; реальної перевірки ID-токена немає.
3. **Тести бекенду.** 3 тести падають (див. таблицю статусу), їх треба виправити окремо.
4. **Фронтенд.** Працює проти MSW-моків; з живим бекендом не запускався. Анімації перевірено юніт-тестами та вручну в мок-режимі, автоматичних візуальних тестів немає. Prettier (CRLF) повідомляє про стильові розбіжності в 155 файлах, відомі й не виправлялися.
5. **Діаграми.** SVG-файли UML відредаговано вручну (PlantUML не запускався), ширину підписів може знадобитися уточнити перегенерацією.

---

**Використання ШІ:** структуру фронтенду, таблиці та оновлення цього звіту підготовлено за допомогою ШІ (Claude, Anthropic) на основі читання коду `frontend/` та `src/`. Перевірка: числа тестів отримано запуском `pytest -q` і `vitest run`, перелік файлів і маршрутів звірено з `frontend/README.md` та `frontend/src/app/routes.tsx`; застосунок з живим бекендом не запускався.
