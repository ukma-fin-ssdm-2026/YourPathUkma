# Статичний аналіз коду — YourPathUkma

**Дата прогону:** 2026-10-15
**Стек:** бекенд — Python 3.12 / FastAPI / SQLAlchemy 2; фронтенд — React 19 / TypeScript 5.9 / Vite

## 1. Інструменти та конфігурація

| Частина | Шар | Інструмент | Версія | Конфігурація |
|---|---|---|---|---|
| Бекенд | **Безпека (SAST)** | **bandit** | 1.9.4 | `[tool.bandit]` у `pyproject.toml` |
| Бекенд | Безпека залежностей | pip-audit | 2.x | `requirements.txt` |
| Бекенд | Стиль / помилки | flake8 | 7.4.1 | `.flake8` (`max-line-length = 120`, `extend-ignore = E203`) |
| Бекенд | Форматування | black | 26.10.1 | `[tool.black]` у `pyproject.toml` |
| Фронтенд | **Безпека (SAST)** | **eslint-plugin-security** | 4.1.0 | `security.configs.recommended` у `frontend/eslint.config.js` |
| Фронтенд | **Безпека залежностей** | **npm audit** | npm 10.9 | `frontend/package-lock.json` |
| Фронтенд | Стиль / помилки | eslint (+ typescript-eslint, react-hooks, jsx-a11y) | 9.39.5 | `frontend/eslint.config.js` |
| Фронтенд | Форматування | prettier | 3.x | `frontend/.prettierrc.json` |

Команди:

```bash
# бекенд (з кореня)
bandit -c pyproject.toml -r src mcp scripts tests
pip-audit -r requirements.txt
flake8 src tests scripts mcp --statistics --count
black --check src tests scripts mcp

# фронтенд (з frontend/)
npm audit
npx eslint .            # включає eslint-plugin-security
npx prettier --check .
```

## 2. Покриття

| Частина | Що аналізувалося | Обсяг |
|---|---|---|
| Бекенд | `src/` (API, моделі БД, сервіс правил, seed), `mcp/`, `scripts/`, `tests/` | 54 файли, 5017 рядків коду (метрика bandit) |
| Фронтенд | `frontend/src/**/*.{ts,tsx}` (сторінки, API-клієнт, auth/PKCE, моки MSW, тести) | 151 файл, ≈13 500 рядків |
| Залежності | `requirements.txt`; `frontend/package-lock.json` (усе дерево, включно з транзитивними) | — |

Виключено свідомо: міграції Alembic і `frontend/src/api/generated` (згенерований код), `frontend/public/mockServiceWorker.js` (вендорний файл MSW), `dist`, `node_modules`, `.venv`. Пропущених через помилки файлів — 0, рядків з `# nosec` — 0.

## 3. Результати аналізаторів безпеки

### Зведення

| Інструмент | Знахідок до | Справжніх | Хибних | Знахідок після |
|---|---|---|---|---|
| bandit (`src`, `mcp`, `scripts`) | 1 — **B608** | **1** | 0 | 0 |
| bandit (`tests`) | 150 — B101 | 0 | 150 | 0 (правило вимкнено лише для тестів) |
| eslint-plugin-security | 18 — `detect-object-injection` | **1** (+1 такий самий рядок поруч, знайдений вручну) | 16 | 0 |
| pip-audit | 0 | — | — | 0 |
| npm audit | 0 (`found 0 vulnerabilities`) | — | — | 0 |

### Розбір хибних спрацювань

**bandit B101 `assert_used` у `tests/` (150 шт.).** Bandit попереджає, що `assert` вирізається при запуску з `python -O`. Це справжній ризик, якщо на `assert` тримається перевірка в продакшн-коді. Але в pytest `assert` і є механізмом перевірки, а тести ніколи не запускаються з `-O`. Тому правило вимкнене **тільки для `tests/`** через `[tool.bandit.assert_used] skips`, а в `src/` воно працює. Окремо перевірено: у `src/`, `mcp/` і `scripts/` немає жодного `assert`.

**eslint-plugin-security `detect-object-injection` (16 з 18).** Правило спрацьовує на будь-який доступ `obj[key]` зі змінним ключем. У нашому коді 16 таких місць — це звертання до константних таблиць-довідників, і ключ має закритий union-тип:

| Файл | Вираз | Тип ключа |
|---|---|---|
| `lib/trimester.ts:9,13,17` | `KEYS[trimester]`, `LABELS[trimester]` | `Trimester = 1 \| 2 \| 3` |
| `ui/Badge.tsx:18,32` | `tones[tone]`, `statusView[status]` | `Tone`, `PlanStatus` |
| `ui/Button.tsx:35` (×2) | `variants[variant]`, `sizes[size]` | union пропсів |
| `features/builder/TrimesterColumn.tsx:62` | `ACCENT[trimester]` | `Trimester` |
| `features/builder/CatalogPanel.tsx:59` | `REASON[state]` | union станів |
| `features/plan-view/PlanViewPage.tsx:138` | `LEVEL_LABEL[level]` | `LoadLevel` |
| `features/profile/CreditsLedger.tsx:22` (×2) | `TONES[tone]`, `row[tone]` | `keyof typeof TONES` |
| `features/admin/sync/SyncPage.tsx:63`, `useSync.ts:24` | `SOURCE_LABEL[value]`, `LABELS[status]` | union з типів API |
| `features/admin/users/useUsers.ts:18` | `SOURCE_LABEL[source]` | `CourseYearSource` |
| `mocks/fixtures.ts:62` | `parts[category]` | `AcademicCategory`, тільки тестові моки |

TypeScript у режимі `strict` + `noUncheckedIndexedAccess` не дасть підставити сюди довільний рядок, тож ризику прототипного доступу немає. Правило вимкнене в `eslint.config.js`, обґрунтування записане в коментарі поруч. Інші 14 з 15 правил плагіна (`detect-eval-with-expression`, `detect-unsafe-regex`, `detect-non-literal-regexp`, `detect-bidi-characters` тощо) лишаються ввімкненими. **Ризик прийнято свідомо:** нові місця, де ключ приходить з мережі, правило вже не підсвітить. Компенсація — патерн `textFor` з розділу 5 і пункт у рев'ю-чеклісті: «ключ з відповіді сервера → тільки через `Object.hasOwn`».

## 4. Знахідка 1 (бекенд): B608 — SQL, зібраний f-рядком

| Поле | Значення |
|---|---|
| **Що знайдено** | SQL-запит збирається f-рядком з підстановкою імені таблиці |
| **Чим знайдено** | bandit 1.9.4, правило **B608** `hardcoded_sql_expressions`, CWE-89 (SQL Injection) |
| **Де** | `src/db/seed.py:152`, функція `_reset_identity_sequences` |
| **Severity / Confidence** | Medium / Low |
| **Рішення** | **Виправлено**: SQLAlchemy Core з bind-параметрами |

**Код до виправлення:**

```python
_TABLES_WITH_FIXED_IDS = ["directions", "instructors", "courses", "users", "individual_plans", "plan_items"]

for table in _TABLES_WITH_FIXED_IDS:
    max_id = db.scalar(text(f"SELECT MAX(id) FROM {table}"))                         # ← B608
    if max_id is not None:
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), :max_id)"),  # ← та сама вада
                   {"max_id": max_id})
```

Функція виконується під час кожного старту застосунку з порожньою БД: `init_database()` → `seed_demo_data()`. Вона зсуває лічильники identity у PostgreSQL.

**Чому це ризик:**
- **Зараз вада не експлуатується.** `table` береться з константного списку, а не від користувача, тому bandit і ставить Confidence Low. Це **латентна вразливість**, а не відкрита діра.
- **Сам шаблон небезпечний.** `text(f"... {x} ...")` — класичний CWE-89, бо SQL-текст і дані змішані. Досить перенести функцію в адмін-модуль і брати назву таблиці із запиту (наприклад, «скинути лічильник таблиці X» в адмінці, UC-15), щоб отримати SQL-ін'єкцію з правами власника БД.
- Bandit помітив лише перший рядок, бо той схожий на `SELECT … FROM`. **Другий рядок** (`setval(pg_get_serial_sequence('{table}', …))`) має ту саму ваду: ім'я вклеюється в рядковий літерал SQL. Інструмент дає сигнал, а повний обсяг проблеми визначає людина під час розбору.
- [`threat-model.md`](../architecture/threat-model.md) для межі **TB2** (Application Server → Master DB) вимагає параметризованих запитів. У `src/` це було єдине місце, яке це правило порушувало.

**Виправлення:**

```python
_MODELS_WITH_FIXED_IDS = [Direction, Instructor, Course, User, IndividualPlan, PlanItem]

for model in _MODELS_WITH_FIXED_IDS:
    max_id = db.scalar(select(func.max(model.id)))
    if max_id is not None:
        sequence = func.pg_get_serial_sequence(model.__tablename__, "id")
        db.execute(select(func.setval(sequence, max_id)))
```

- Колонку і таблицю для `MAX(id)` SQLAlchemy бере з метаданих моделі й сам квотує.
- Ім'я таблиці для `pg_get_serial_sequence` тепер іде **bind-параметром**. Скомпільований для PostgreSQL SQL:
  ```sql
  SELECT setval(pg_get_serial_sequence(%(pg_get_serial_sequence_1)s::VARCHAR, %(pg_get_serial_sequence_2)s::VARCHAR),
                %(setval_2)s::INTEGER) AS setval_1
  -- params: {'pg_get_serial_sequence_1': 'directions', 'pg_get_serial_sequence_2': 'id', 'setval_2': 3}
  ```
- Функція приймає лише ORM-моделі, оголошені в коді. Імпорт `text` із `seed.py` прибрано.
- `# nosec` не використовувався: ваду виправлено, а не приховано.

**Перевірка:** bandit → `No issues identified`; скомпільований SQL переглянуто вручну; `pytest` дає той самий результат до і після (розділ 8). Гілка PostgreSQL виконується в CI, бо тести там ідуть на `postgres:16`.

## 5. Знахідка 2 (фронтенд): доступ до прототипу Object за кодом помилки із сервера

| Поле | Значення |
|---|---|
| **Що знайдено** | Пошук перекладу помилки в об'єкті-словнику за рядком із відповіді API без перевірки, що ключ власний |
| **Чим знайдено** | eslint-plugin-security 4.1.0, правило **`security/detect-object-injection`** (CWE-1321, Prototype Pollution / небезпечний доступ до прототипу) |
| **Де** | `frontend/src/features/builder/saveErrors.ts:35` (`ITEM_TEXT[code]`). Під час розбору знайдено таку саму ваду на рядку 26 (`CODE_TEXT[error.code]`), яку плагін **не** підсвітив |
| **Рішення** | **Виправлено** + регресійний тест |

**Код до виправлення:**

```ts
const CODE_TEXT: Record<string, string> = { PLAN_NOT_EDITABLE: "…", PLAN_NOT_SUBMITTABLE: "…" };

const known = CODE_TEXT[error.code];          // error.code — рядок із JSON-відповіді сервера
if (known) return { itemErrors: {}, form: [known] };
…
if (item && code && ITEM_TEXT[code]) itemErrors[item.course_id] = ITEM_TEXT[code]!;
```

**Чому це ризик.** `CODE_TEXT` — звичайний об'єкт, тому `CODE_TEXT["constructor"]`, `["toString"]`, `["__proto__"]` повертають не `undefined`, а функцію `Object`, метод прототипу або сам `Object.prototype`. Значення truthy, тож воно потрапляє в масив повідомлень `form` і далі в JSX. React падає з помилкою `Objects are not valid as a React child`, і сторінка конструктора плану ламається. Тип `Record<string, string>` це приховує: TypeScript «вірить», що там рядок. Це загроза типу Tampering на межі **TB1** (React SPA ↔ Application Server) з моделі загроз: фронтенд не має довіряти формі відповіді. Тіло помилки може прийти не лише від нашого бекенду, а й від проксі, балансувальника або під час MITM у dev-середовищі.

**Відтворено тестом** `frontend/src/features/builder/saveErrors.test.ts`. До виправлення 4 тести з 5 падали:

```
× код constructor дає звичайне повідомлення   — Received: [Function Object]
× код toString дає звичайне повідомлення      — Received: [Function toString]
× код __proto__ дає звичайне повідомлення     — Received: {}
× код hasOwnProperty дає звичайне повідомлення — Received: [Function hasOwnProperty]
```

**Виправлення.** Обидва пошуки йдуть через одну функцію, яка дивиться лише на власні ключі таблиці:

```ts
function textFor(table: Record<string, string>, code: string | undefined): string | undefined {
  return code !== undefined && Object.hasOwn(table, code) ? table[code] : undefined;
}

const known = textFor(CODE_TEXT, error.code);
…
const text = textFor(ITEM_TEXT, code);
if (item && text) itemErrors[item.course_id] = text;
```

**Перевірка:** `saveErrors.test.ts` — 5/5; усі тести фронтенду — 430/430 (48 файлів); `npx eslint .` — 0 проблем; `tsc --noEmit` — 0 помилок.

## 6. Загроза з threat-model.md: як код їй протистоїть (R3 — IDOR)

**R3 (TB1, Information Disclosure):** студент підставляє чужий `id` у `GET /api/plans/{id}`.

Захист у `src/api/routes/plans.py`:
- `student_id` береться лише з автентифікації (`Depends(get_current_student_id)`). У тілі запиту його не приймають.
- Список планів фільтрується в самому запиті: `.where(IndividualPlan.student_id == student_id)`.
- Один план можна отримати тільки через `_find_plan(db, plan_id, student_id)`, яка перевіряє власника.
- Тест `tests/test_db_plans.py`: план 3 (іншого студента) для студента 42 → відмова.

На фронтенді додатково закрито **R7** (крадіжка токена через XSS): `frontend/src/api/token.ts` тримає access-токен лише в пам'яті модуля, а не в `localStorage`. У `sessionStorage` лежать тільки одноразові PKCE `verifier` і `state`, і після обміну коду вони видаляються (`auth/login.ts`, блок `finally`). Пошук `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function` по `frontend/src` дав 0 збігів. Зовнішні посилання з `target="_blank"` мають `rel="noopener noreferrer"`.

**Розбіжність, виявлена вручну (не інструментом):** R3 вимагає повертати **404** для чужого ресурсу, щоб не розкривати факт його існування. `_find_plan` натомість повертає **403 `PLAN_FORBIDDEN`**. Оскільки id послідовні, зловмисник може відрізнити «плану немає» від «план є, але чужий» і так оцінити кількість планів. Вміст плану не розкривається, тому ризик низький. **Ризик прийнято тимчасово:** зміна зачіпає контракт API (OpenAPI, фронтенд, `test_db_plans.py`), тому її винесено в окрему задачу. Це приклад межі статичного аналізу: SAST шукає небезпечні шаблони коду, але не знає бізнес-правил доступу.

## 7. Результати стильового шару

| Інструмент | До | Після | Коментар |
|---|---|---|---|
| flake8 | 79 | 60 | виправлено **F811 ×12 + E402** у `src/api/main.py` |
| black | 23 файли на переформатування | 23 | масово не форматували (див. нижче) |
| eslint (стиль + typescript-eslint + react-hooks + jsx-a11y) | 0 | 0 | — |
| prettier | 92 файли з розбіжностями | 92 | масово не форматували; нові/змінені файли відформатовано |

flake8 за кодами (до): W292 — 23, E302 — 19, E501 — 12, **F811 — 12**, E402 — 9, інші — 4.

Найцікавіші знахідки — **F811 + E402 у `src/api/main.py`**. Після злиття гілок там лишилися два блоки імпортів роутерів і два виклики `logging.basicConfig`. Імена перевизначалися, а другий виклик налаштування логування мовчки нічого не робив. Це ознака неакуратного merge, а не просто стиль. **Виправлено:** дубль прибрано.

Масове переформатування black/prettier (23 + 92 файли) у цій роботі свідомо не робили, щоб не заховати справжні зміни в диффі. Рекомендація: окремий коміт `black src tests scripts mcp` і `npx prettier --write .`.

## 8. Інтеграція в робочий процес

- **CI, job `build`** (`.github/workflows/ci.yaml`): новий крок `Security scan (bandit)`. Ненульовий код при знахідці валить PR.
- **CI, job `frontend`**: новий крок `npm audit --audit-level=high`. eslint-plugin-security запускається в наявному кроці `npm run lint`.
- **pre-commit** (`.pre-commit-config.yaml`): форматер `black`, лінтер `flake8`, сканер секретів `gitleaks`, хук `bandit` з конфігом із `pyproject.toml`. Прогін gitleaks — у розділі 10.
- Усі винятки (B101 у тестах, `detect-object-injection`) описані в конфігах з обґрунтуванням. У коді немає жодного `# nosec` чи `eslint-disable`.

Помічені побічно проблеми (не предмет цієї роботи, передано команді):
- `ruff check` у CI повертає 66 помилок (здебільшого `I001`, сортування імпортів; частину виправить `ruff check --fix`). Job `build` червоний ще до цих змін.
- 3 тести бекенду падають до і після змін (перевірено на копії з оригінальним кодом): `test_plan_validation.py::test_create_plan_still_rejects_business_rule_violation` і два в `test_request_id.py` (`request_id` у тілі ≠ заголовку `X-Request-ID`).
- `npm run typecheck` без попереднього `npm run gen:api` дає 15 помилок, бо згенерований `schema.d.ts` у `.gitignore`. У CI порядок кроків правильний.

## 9. Висновки

1. Аналізатори безпеки знайшли **дві справжні вади**. На бекенді це латентна SQL-ін'єкція (B608 / CWE-89), на фронтенді — доступ до прототипу за даними із сервера, що ламає UI (`detect-object-injection` / CWE-1321). Обидві виправлено на рівні шаблону, без `# nosec` чи `eslint-disable`. Фронтенд-ваду закріплено регресійним тестом.
2. В обох випадках інструмент вказав на один рядок, а така сама вада була поруч і її **не** помітили (`setval` у `seed.py`, `CODE_TEXT[error.code]` у `saveErrors.ts`). Знахідку SAST треба розбирати, а не просто «гасити» рядок.
3. Більшість спрацювань — хибні: 150 B101 у тестах і 16 з 18 `detect-object-injection`. Їх вимкнено точково й з обґрунтуванням. Через типізацію TypeScript правило `detect-object-injection` дає мало корисного сигналу, тож прийнято компромісне рішення з компенсуючим заходом.
4. Залежності бекенду й фронтенду на дату прогону не мають відомих вразливостей (pip-audit, npm audit).
5. Стильовий шар теж знайшов змістовну проблему: F811 вказав на артефакт merge у точці входу API.
6. Статичний аналіз не замінює рев'ю за моделлю загроз: розбіжність 403/404 у R3 жоден інструмент не помітив.

## 10. Pre-commit і пошук секретів (gitleaks)

**Дата прогону:** 2026-10-29

`.pre-commit-config.yaml` у корені репозиторію запускає перед кожним комітом:

| Хук | Роль | Версія (`rev`) |
|---|---|---|
| `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files` | базові перевірки файлів | pre-commit-hooks v6.0.0 |
| `black` | **форматер** | 24.3.0 |
| `flake8` | **лінтер** | 7.0.0 |
| `gitleaks` | **сканер секретів** | v8.18.2 (`verbose: true`) |
| `bandit` | SAST | 1.9.4 |

Хук `gitleaks` виконує `gitleaks protect --verbose --redact --staged`: перевіряє **лише проіндексовані зміни** (те, що потрапить у коміт), а знайдений секрет у виводі замінює на `REDACTED`. Якщо gitleaks знаходить секрет, він повертає код 1, і pre-commit зупиняє коміт.

Встановлення і запуск:

```bash
pip install pre-commit
pre-commit install                 # хуки спрацьовують на кожен git commit
pre-commit run gitleaks            # ручний запуск на проіндексованих файлах
```

### 10.1. Що хук зупинив: тестовий секрет у коміті

Перевірка зроблена в одноразовому клоні репозиторію. У файл `scripts/leak_demo.py` записано **випадково згенерований фейковий** токен у форматі GitHub PAT (`ghp_` + 36 символів), файл додано в індекс (`git add`), після чого запущено хук:

```python
# demo: випадково згенерований фейковий токен
GITHUB_TOKEN = "ghp_…"   # 36 випадкових символів, не справжній токен
```

```
$ pre-commit run gitleaks
Detect hardcoded secrets.................................................Failed
- hook id: gitleaks
- duration: 0.05s
- exit code: 1

○
    │╲
    │ ○
    ○ ░
    ░    gitleaks

Finding:     GITHUB_TOKEN = "REDACTED
Secret:      REDACTED
RuleID:      github-pat
Entropy:     4.953056
File:        scripts/leak_demo.py
Line:        2
Fingerprint: scripts/leak_demo.py:github-pat:2

12:24AM INF 1 commits scanned.
12:24AM INF scan completed in 23.2ms
12:24AM WRN leaks found: 1
```

Код завершення pre-commit — **1**, тобто `git commit` з цим файлом не відбувся б. gitleaks визначив тип секрету (правило `github-pat`), файл і рядок, а сам токен у виводі приховано (`--redact`), тож він не потрапляє в логи CI чи термінал колег.

Після виправлення (токен читається зі змінної середовища, як і решта секретів у `.env.example`) хук проходить:

```python
import os

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
```

```
$ pre-commit run gitleaks
Detect hardcoded secrets.................................................Passed
- hook id: gitleaks
- duration: 0.05s

12:24AM INF 1 commits scanned.
12:24AM INF scan completed in 22.3ms
12:24AM INF no leaks found
```

Тестовий клон після перевірки видалено. У робочий репозиторій фейковий токен не потрапляв.

### 10.2. Що хук перевірив: поточний стан репозиторію

Хук бачить лише проіндексовані зміни, тож секрет, закомічений **до** встановлення хука, він не помітить. Тому тим самим бінарником gitleaks (зібраним pre-commit з `rev: v8.18.2`) окремо проскановано **всю історію git**:

```
$ gitleaks detect --source . --redact -v
INF 349 commits scanned.
INF scan completed in 575ms
INF no leaks found
```

Для порівняння, `pre-commit run gitleaks --all-files` без проіндексованих змін дає `Passed` і `0 commits scanned`: прапорець `--all-files` на цей хук не впливає, бо gitleaks сам читає індекс git, а не список файлів від pre-commit. Повну перевірку дає саме `gitleaks detect`.

**Результат:** у 349 комітах (усі локальні гілки на 2026-10-29, без merge-комітів: `git rev-list --all --no-merges --count` = 349) секретів не знайдено. `.env` є в `.gitignore`, у репозиторії лише `.env.example` і `frontend/.env.example` із заглушками.

**Обмеження:** локальний хук можна обійти (`git commit --no-verify` або просто не виконати `pre-commit install`). Тому для R10 з [`threat-model.md`](../architecture/threat-model.md) (витік API-ключа LLM) рекомендовано дублювати gitleaks у GitHub Actions — так само, як це вже зроблено для bandit.

## Використання ШІ

- **Що зроблено за допомогою ШІ (Claude, Claude Code):**
  - запуск bandit, pip-audit, flake8, black, npm audit, eslint + eslint-plugin-security, prettier;
  - розбір усіх знахідок;
  - виправлення B608 у `src/db/seed.py`, дубльованих імпортів у `src/api/main.py`, прототипного доступу у `frontend/src/features/builder/saveErrors.ts`;
  - тест `saveErrors.test.ts`;
  - конфігурація bandit (`pyproject.toml`) і eslint-plugin-security (`frontend/eslint.config.js`, `package.json`);
  - кроки в `.github/workflows/ci.yaml` і хук у `.pre-commit-config.yaml`;
  - цей звіт;
  - розділ 10 (2026-10-29): прогін хука gitleaks через pre-commit 4.7.0 (тестовий фейковий секрет в одноразовому клоні + сканування всієї історії git) і опис результатів.
- **Як перевірено:**
  - bandit і eslint повторно прогнано після виправлень: 0 знахідок;
  - flake8: 79 → 60;
  - новий тест падав до виправлення і проходить після; усі 430 тестів фронтенду проходять; `tsc --noEmit` — 0 помилок;
  - скомпільований для PostgreSQL SQL переглянуто вручну;
  - `pytest` до і після змін дає однаковий результат (92 passed, ті самі 3 падіння, не пов'язані зі змінами);
  - вивід gitleaks у розділі 10 скопійовано з реального запуску (прибрано лише ANSI-кольори); код завершення pre-commit із секретом перевірено окремо (1); після виправлення хук має статус `Passed`.
- Звіт потребує рев'ю командою перед здачею.

## Статус на 2026-10-24

Повторний прогін усіх перелічених вище перевірок (крім pip-audit і flake8, які не встановлені в `.venv`). Основний звіт вище описує стан на 2026-10-15.

| Перевірка | Результат |
|---|---|
| bandit (`src`, `mcp`, `scripts`, `tests`) | 0 проблем, 0 `# nosec` |
| Виправлення B608 (`seed.py`) і `saveErrors.ts` | на місці |
| `ruff check .` | чисто (одну `I001` у міграції виправлено) |
| `pytest` | 254 passed, 1 skipped; три падіння з розділу 8 більше не відтворюються (Python 3.14 локально, CI на 3.12) |
| `vitest` / `tsc --noEmit` / `eslint` | 437/437 / 0 помилок / 0 проблем |
| `npm audit` | знайдено 1 high (`undici` 7.30.0), виправлено `npm audit fix` до 7.30.1, тепер 0 |
| black / prettier | 13 / 97 файлів потребують форматування, окрема гілка `style/black-prettier-format` |
