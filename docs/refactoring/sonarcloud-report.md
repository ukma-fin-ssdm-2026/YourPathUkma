# Звіт про аналіз якості коду в SonarCloud (YourPathUkma)

**Проєкт:** YourPathUkma (REST API + вебфронтенд)
**Відповідальні ролі:** Quality Lead
**Інструмент:** SonarCloud (проєкт `ukma-fin-ssdm-2026_YourPathUkma`)
**Станом на:** 30.10.2026
**Версія / коміт аналізу:** 0b62882

## 1. Загальна інформація

| Параметр | Значення |
|---|---|
| Репозиторій | ukma-fin-ssdm-2026/YourPathUkma |
| Гілка / PR аналізу | pre-refactor / PR #167 |
| Дата аналізу | 30.10.2026 |
| Quality Gate | Passed |
| Кількість рядків коду (LoC) | 52,881 |

## 2. Підсумок за категоріями

| Категорія | Кількість проблем | Рейтинг (A–E) | Висновок |
|---|---|---|---|
| Security | 16 | E | 14 проблем у CI/CD workflow, 2 у моках фронтенду; 1 Blocker (script injection) |
| Reliability | 28 | C | 1 Blocker (CORS); 21 проблема у згенерованому звіті покриття |
| Maintainability | 16 | A | 4 Blocker, 2 High, 1 Medium, 9 Low; 12 з них у згенерованому JS-звіті покриття |
| Duplications | 5,5% | — | 46 файлів, 3170 дубльованих рядків; 41 файлів — згенерований звіт покриття |

Додатково: Security Hotspots — 0, Technical Debt — 2h 24min.

## 2.1. Обрані метрики для покращення та Security Rating (стан «ДО»)

### 1. Таблиця 3 обраних метрик якості (стан «ДО» — коміт `0b62882` / `pre-refactor`)

| № | Показник | Значення «ДО» | Обґрунтування вибору та ціль рефакторингу |
|---|---|---|---|
| **1** | **Reliability Rating** (або Reliability Issues) | **C** (28 проблем: 1 Blocker, 2 High, 25 Medium) | **Критична надійність бекенду.** 1 Blocker через неправильний порядок `CORSMiddleware` у `src/api/main.py` призводить до втрати CORS-заголовків на помилках; 2 High дефекти Pydantic у `deanery.py` та `preferences.py` викликані необов'язковими полями без дефолтного `= None`. Ціль — підвищити рейтинг до **A**. |
| **2** | **Technical Debt** (Технічний борг) | **2h 24min** (20 Code Smells) | **Ключовий показник підтримуваності (Maintainability).** Включає оцінений Sonar час на виправлення блокерів та конвенцій у коді. Ціль — скоротити технічний борг через рефакторинг та виправлення архітектурних зауважень. |
| **3** | **Duplicated Lines (%)** (Відсоток дублювання) | **5,5%** (3170 рядків у 46 файлах) | **Чистота та точність метрик коду.** Показник штучно завищений включенням до аналізу 41 файлу згенерованого звіту покриття `docs/testing/coverage/` (3069 рядків). Ціль — усунути звіт з аналізу через `sonar.exclusions` та зменшити дублювання в тестових фікстурах фронтенду, знизивши відсоток дублювання до < 2%. |

---

### 2. Обов'язковий показник: Security Rating (стан «ДО»)

| Показник | Рейтинг «ДО» | Кількість проблем | Vulnerabilities | Security Hotspots | Статус |
|---|---|---|---|---|---|
| **Security Rating** | **E** | 16 (1 Blocker, 1 High, 12 Medium, 2 Low) | 14 | 0 / 0 | 🔴 Потребує негайного виправлення |

#### Коментар про причини поточного значення:

Рейтинг безпеки знаходиться на найнижчому рівні (**E**), оскільки SonarQube присвоює рейтинг E будь-якому проєкту, що містить хоча б одну незакриту вразливість рівня **Blocker**:
1. **Blocker (Script Injection, CWE-78):** у `.github/workflows/mutation.yml` L36 вираз `${{ inputs.paths }}` підставлявся безпосередньо в тіло bash-команди `run`. Це дозволяє особі, яка запускає workflow, передати рядок з командними розділювачами (наприклад, `; rm -rf` або `; curl ...`) і виконати довільні команди на білд-раннері.
2. **High (Unpinned Action Commit SHA, CWE-829):** у `.github/workflows/deploy-api-docs.yml` L37 сторонній action використовується без фіксації за повним 40-символьним SHA коміту, що створює ризик атаки на ланцюжок постачання (supply chain).
3. **Medium (12 проблем у workflows):** підозра на захардкоджений секрет `PASSWORD` у `.github/workflows/ci.yaml` L21, виклики `pip install` без `--only-binary :all:`, встановлення npm без `--ignore-scripts`, та незафіксовані точні версії пакетів.
4. **Low (2 проблеми у тестах фронтенду):** виявлені захардкоджені IP-адреси `10.0.0.15` у `fixtures.ts` L275 та `handlers.ts` L302 (верифіковано: синтетичні мок-дані для перегляду журналу аудиту в тестах, мережевого з'єднання немає, загрози не несуть).

#### Зв'язок із попередніми лабораторними роботами:

* **Зв'язок із Лабораторною 3 (`docs/architecture/threat-model.md` — Модель загроз STRIDE):**
  * Script injection у `mutation.yml` прямо реалізує загрози **Tampering (підміна даних/коду)** та **Elevation of Privilege (підвищення привілеїв)**: скомпрометований процес на CI-раннері отримує доступ до контексту репозиторію, змінних середовища та секретів (`GITHUB_TOKEN`).
  * Попередження про захардкоджений `PASSWORD` у `ci.yaml` відповідає загрозі **Information Disclosure (витік облікових даних)**.
  * Порядок `CORSMiddleware` у `src/api/main.py` корелює із загрозою **Information Disclosure / Spoofing**: відсутність коректних CORS-заголовків на помилкових відповідях не блокує запити належним чином на рівні клієнта або розкриває внутрішній стан API.
* **Зв'язок із Лабораторною 5 (`docs/code-quality/static-analysis.md` — SAST-аналізатори):**
  * У Лаб 5 сканери **Bandit** (для Python) та **eslint-plugin-security** (для TypeScript) перевіряли виключно прикладний код застосунку в `src/` та `frontend/src/` (де всі реальні вразливості на кшталт B608 було виправлено).
  * Жоден локальний аналізатор коду не перевіряв інфраструктуру автоматизації CI/CD (`.github/workflows/`). Саме SonarQube Cloud виявив критичні прогалини в конфігураціях GitHub Actions, доповнивши контур безпеки проєкту.

#### План усунення проблем безпеки:
* **Крок 1 (Blocker):** передати вхідні параметри запуску mutmut через безпечну змінну оточення `env: MUTATE_PATHS` замість прямої підстановки в `run` (реалізовано в PR #168).
* **Крок 2 (High / Medium):** провести рев'ю конфігурації `.github/workflows/ci.yaml`, переконатися, що слово `PASSWORD` не є реальним секретом, та зафіксувати commit SHA зовнішніх action.
* **Крок 3 (Low):** позначити 2 захардкоджені тестові IP у фронтенд-фікстурах як Safe / False Positive в інтерфейсі SonarCloud.

## 3. Security

**Показники:** проблем Security — 16 (Blocker 1, High 1, Medium 12, Low 2); Vulnerabilities — 14; Security Hotspots (переглянуто / усього) — 0 / 0; рейтинг — E.

**Результати аналізу:**

14 проблем категорії Security стосуються CI/CD-конфігурації (`.github/workflows/`), 2 — фронтенду. Коду застосунку вони не зачіпають. За severity: Blocker — 1, High — 1, Medium — 12, Low — 2. Найкритичніша — ін'єкція скрипта через `inputs.paths` у `mutation.yml`. Решта — незафіксовані версії залежностей, встановлення без `--only-binary :all:` / `--ignore-scripts` та action без фіксації за SHA. Орієнтовна трудомісткість за оцінкою Sonar: 1 год на ін'єкцію, по 30 хв на SHA, PASSWORD і `--ignore-scripts`, по 1 год на кожну з решти.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `.github/workflows/mutation.yml` L36 | script injection (CWE) | Blocker | `inputs.paths` потрапляє напряму в `run`; значення задає той, хто запускає workflow | Передати вираз через змінну середовища (`env:`) і використовувати її в `run` | Fixed: `inputs.paths` передається через `env: MUTATE_PATHS`, у `run` використано `"$MUTATE_PATHS"` (PR #168) |
| 2 | `.github/workflows/deploy-api-docs.yml` L37 | full commit SHA (CWE) | High | Залежність підключена не за повним SHA коміту | Зафіксувати action за повним SHA коміту | Open |
| 3 | `.github/workflows/ci.yaml` L21 | hard-coded credential (CWE) | Medium | Виявлено «PASSWORD», можливий захардкоджений секрет | Перевірити, що це не реальний секрет; за потреби винести в GitHub Secrets | Open |
| 4 | `.github/workflows/ci.yaml` L38 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 5 | `.github/workflows/ci.yaml` L38 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 6 | `.github/workflows/ci.yaml` L40 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 7 | `.github/workflows/ci.yaml` L40 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 8 | `.github/workflows/ci.yaml` L42 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 9 | `.github/workflows/ci.yaml` L42 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 10 | `.github/workflows/ci.yaml` L70 | npm: `--ignore-scripts` (CWE) | Medium | Без `--ignore-scripts` під час встановлення пакетів запускаються lifecycle-скрипти | Додати `--ignore-scripts` | Open |
| 11 | `.github/workflows/deploy-api-docs.yml` L31 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 12 | `.github/workflows/deploy-api-docs.yml` L31 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 13 | `.github/workflows/mutation.yml` L30 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 14 | `.github/workflows/mutation.yml` L30 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 15 | `frontend/src/test/handlers.ts` L302 | захардкоджена IP адреса (S1313 / CWE-547) | Low | Виявлено захардкоджену IP-адресу 10.0.0.15 у фікстурах записів аудиту | Перевірено: це синтетичні мок-дані для імітації журналу аудиту в UI, реального мережевого з'єднання немає. Позначити як Safe / Won't Fix у SonarCloud. | Open (Safe by design) |
| 16 | `frontend/src/test/fixtures.ts` L275 | захардкоджена IP адреса (S1313 / CWE-547) | Low | Виявлено захардкоджену IP-адресу 10.0.0.15 у тестових MSW-хендлерах журналу аудиту | Перевірено: це тестовий об'єкт аудиту для Vitest/MSW. Загрози розкриття внутрішньої мережі немає. Позначити як Safe / Won't Fix у SonarCloud. | Open (Safe by design) |

## 4. Reliability

**Показники:** проблем Reliability — 28 (Blocker 1, High 2, Medium 25); Bugs — 13; рейтинг — C.

**Результати аналізу:**

Знайдено 28 проблем Reliability: Blocker — 1, High — 2, Medium — 25. Три найсерйозніші — у коді бекенда (`main.py`, `deanery.py`, `preferences.py`), вони також враховані в Maintainability. Ще 21 проблема (доступність `<label>`/`<th>`, `isNaN`, `parseInt`) стосується згенерованого звіту покриття в `docs/testing/coverage/`, який краще виключити з аналізу Sonar. Решта: регулярні вирази з backtracking у `pkce.ts` і `download.ts` (по 20 хв), `multipart.ts` та `pytest.raises` у тесті. Схожі проблеми в таблиці згруповано за файлом; кількість окремих проблем вказано в описі.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `src/api/main.py` L113 | cors, configuration | Blocker | `CORSMiddleware` додано не останнім у ланцюжку middleware (також Maintainability, Blocker) | Додавати `CORSMiddleware` останнім | Open |
| 2 | `src/api/routes/deanery.py` L49 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Maintainability, High) | Додати `= None` | Fixed: у `DeaneryDocumentResponse` додано `= None` для `parse_error` (PR #170) |
| 3 | `src/api/routes/preferences.py` L59 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Maintainability, High) | Додати `= None` | Open |
| 4 | `frontend/src/auth/pkce.ts` L5 | regex, performance | Medium | Регулярний вираз із супер-лінійною складністю через backtracking (20 хв) | Спростити регулярний вираз | Open |
| 5 | `frontend/src/lib/download.ts` L5 | regex, performance | Medium | Регулярний вираз із супер-лінійною складністю через backtracking (20 хв) | Спростити регулярний вираз | Open |
| 6 | `frontend/src/test/multipart.ts` L7 | type-dependent | Medium | Причина відхилення Promise не є `Error` | Відхиляти Promise з `new Error(...)` | Open |
| 7 | `tests/test_free_elective_remaining.py` (L19) | pytest, tests | Medium | Виняток перевіряється не через контекстний менеджер (також Maintainability, Medium) | Використати `with pytest.raises(...)` | Open |
| 8 | `docs/testing/coverage/class_index.html` L47 | accessibility, wcag2-a | Medium | Поле вводу без пов'язаного `<label>` | Додати `<label>` до поля | Open |
| 9 | `docs/testing/coverage/class_index.html` L80, L85, L89 | accessibility, wcag2-a | Medium | Тег `<th>` без атрибута `id` або `scope` (3 шт.) | Додати `scope` або `id` | Open |
| 10 | `docs/testing/coverage/function_index.html` L47 | accessibility, wcag2-a | Medium | Поле вводу без пов'язаного `<label>` | Додати `<label>` до поля | Open |
| 11 | `docs/testing/coverage/function_index.html` L80, L85, L89 | accessibility, wcag2-a | Medium | Тег `<th>` без атрибута `id` або `scope` (3 шт.) | Додати `scope` або `id` | Open |
| 12 | `docs/testing/coverage/index.html` L46 | accessibility, wcag2-a | Medium | Поле вводу без пов'язаного `<label>` | Додати `<label>` до поля | Open |
| 13 | `docs/testing/coverage/index.html` L77, L82, L86 | accessibility, wcag2-a | Medium | Тег `<th>` без атрибута `id` або `scope` (3 шт.) | Додати `scope` або `id` | Open |
| 14 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L53 | convention | Medium | `isNaN` замість `Number.isNaN` (2 проблеми на одному рядку; також Maintainability, Low) | Замінити на `Number.isNaN` | Open |
| 15 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L203, L204, L207, L324, L556, L576, L671 | convention | Medium | `parseInt` замість `Number.parseInt` (7 шт.; також Maintainability, Low) | Замінити на `Number.parseInt` | Open |

## 5. Maintainability

**Показники:** проблем Maintainability — 16 (Blocker 4, High 2, Medium 1, Low 9); Code Smells — 20; Technical Debt — 2h 24min; Debt Ratio — 0 %; рейтинг — A.

**Результати аналізу:**

Знайдено 16 проблем Maintainability: Blocker — 4, High — 2, Medium — 1, Low — 9. Чотири з них (CORS у `main.py`, значення за замовчуванням у `deanery.py` і `preferences.py`, `pytest.raises`) одночасно належать до Reliability. Ще три Blocker — неоголошені змінні в згенерованому `coverage_html_cb_*.js` (звіт покриття в `docs/testing/coverage/`); цей файл генерується інструментом покриття, тож його краще виключити з аналізу Sonar, а не правити вручну. Решта 9 проблем категорії Low — це convention-зауваження (`Number.isNaN` та `Number.parseInt`) у тому ж згенерованому файлі покриття. Усі проблеми мають оцінку трудомісткості 2–5 хв.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `src/api/main.py` L113 | cors, configuration | Blocker | `CORSMiddleware` додано не останнім у ланцюжку middleware (також Reliability, Blocker) | Додавати `CORSMiddleware` останнім | Open |
| 2 | `src/api/routes/deanery.py` L49 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Reliability, High) | Додати явне значення за замовчуванням (`= None`) | Fixed: у `DeaneryDocumentResponse` додано `= None` для `parse_error` (PR #170) |
| 3 | `src/api/routes/preferences.py` L59 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Reliability, High) | Додати явне значення за замовчуванням (`= None`) | Open |
| 4 | `tests/test_free_elective_remaining.py` L19 | pytest, tests | Medium | Виняток перевіряється не через контекстний менеджер (також Reliability, Medium) | Обгорнути код, що кидає виняток, у `with pytest.raises(...)` | Open |
| 5 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L166 | pitfall | Blocker | Змінна `cell` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Open |
| 6 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L358 | pitfall | Blocker | Змінна `cls` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Open |
| 7 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` (рядок не вказано) | pitfall | Blocker | Змінна `key` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Open |
| 8 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L53 | convention | Low | `isNaN` замість `Number.isNaN` (2 проблеми на одному рядку; також Reliability, Medium) | Замінити на `Number.isNaN` (або виключити звіт покриття з аналізу) | Open |
| 9 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L203, L204, L207, L324, L556, L576, L671 | convention | Low | `parseInt` замість `Number.parseInt` (7 шт.; також Reliability, Medium) | Замінити на `Number.parseInt` (або виключити звіт покриття з аналізу) | Open |

## 6. Duplications

**Показники:** файлів з дублюванням — 46; дубльованих рядків — 3170; Duplicated Lines Density — 5,5%; Duplicated Blocks — 202; Duplicated Files — 46.

**Результати аналізу:**

Sonar показує дублювання у 46 файлах, усього 3170 дубльованих рядків. З них 41 файлів (3069 рядків) — згенерований звіт покриття в `docs/testing/coverage/`; його варто виключити з аналізу, після чого дублювання у цих файлах зникне. Реальний код — 5 файлів фронтенду (101 рядків): тести та моки, де дублюються повторювані блоки. Відсоток дублювання по всьому проєкту у вставці не наведено. Згенеровані файли згруповано в один рядок таблиці.

| # | Файли з дублюванням | Дубльовані рядки (%) | Кількість рядків | Опис | План усунення | Статус |
|---|---|---|---|---|---|---|
| 1 | `docs/testing/coverage/*.html` (41 файлів, згенерований звіт покриття) | 7.5–71.0 % | 3069 | Дублюється типова розмітка HTML-звіту (найбільше в `__init__.py`-сторінках: 71,0 %; у `index.html` — 36,7 %, 243 рядки) | Виключити `docs/testing/coverage/` з аналізу Sonar (`sonar.exclusions`) або не комітити згенерований звіт | Open |
| 2 | `frontend/src/auth/login.test.ts` | 18.2 % | 27 | Повторювані блоки в тесті | Винести спільний код у допоміжну функцію / фікстуру | Open |
| 3 | `frontend/src/features/plan-view/export.test.tsx` | 14.9 % | 14 | Повторювані блоки в тесті | Винести спільний код у допоміжну функцію / фікстуру | Open |
| 4 | `frontend/src/mocks/core.ts` | 7.8 % | 23 | Повторюваний код у мок-даних | Винести спільний код у допоміжну функцію / фікстуру | Open |
| 5 | `frontend/src/test/handlers.ts` | 7.1 % | 23 | Повторюваний код в MSW-хендлерах | Винести спільний код у допоміжну функцію / фікстуру | Open |
| 6 | `frontend/src/features/plan-view/view.test.tsx` | 6.8 % | 14 | Повторювані блоки в тесті | Винести спільний код у допоміжну функцію / фікстуру | Open |

## 7. Обрані метрики та Security Rating (стан «ПІСЛЯ» — після рефакторингу)

> Шаблон для фіксації результатів після злиття змін у `main` та прогону повторного аналізу в SonarQube Cloud.

### 1. Порівняльна таблиця метрик (ДО та ПІСЛЯ рефакторингу)

| № | Показник | Стан «ДО» (коміт `0b62882`) | Стан «ПІСЛЯ» (новий коміт `main`) | Зміна (Δ) | Оцінка результату |
|---|---|---|---|---|---|
| **0** | **Security Rating** *(обов'язковий)* | **E** (16 проблем) | TODO: [A–E] | TODO | Очікується **A** після закриття Blocker ін'єкції у `mutation.yml` (PR #168) |
| **1** | **Reliability Rating** | **C** (28 проблем) | TODO: [A–E] | TODO | Очікується **A** після виправлення `main.py` (CORS), `deanery.py` та `preferences.py` |
| **2** | **Technical Debt** | **2h 24min** (20 Code Smells) | TODO: [Xh Ymin] | TODO: -X min | Очікується списання за рахунок усунення Blocker/High проблем |
| **3** | **Duplicated Lines (%)** | **5,5%** (3170 рядків) | TODO: [X.X %] | TODO: -X % | Очікується падіння до < 2% після виключення `docs/testing/coverage/` |

---

### 2. Коментар до Security Rating «ПІСЛЯ»:

* **Фактичний рейтинг після змін:** TODO: [A / ...]
* **Аналіз змін у безпеці:**
  * Blocker script injection у `.github/workflows/mutation.yml` (CWE-78): успішно усунуто через винесення `inputs.paths` у змінну середовища `MUTATE_PATHS` (PR #168).
  * Чи з'явилися нові зауваження безпеки після внесеного коду: TODO (Ні / Так).
  * Статус ризиків моделі загроз STRIDE: підвищення привілеїв (Elevation of Privilege) через білд-раннери усунуто, загрози підміни коду мінімізовано.

---

### 3. Скриншоти з панелі SonarQube Cloud

#### Панель стану «ПІСЛЯ» (останній коміт `main` після рефакторингу):
*TODO: Додати скриншот сторінки Overview / Issues стану «ПІСЛЯ» (або посилання на файл скриншота)*

---

### 4. Результати регресійного тестування

| Тестовий набір | Кількість тестів | Статус | Коментар |
|---|---|---|---|
| Бекенд (`pytest`) | TODO: [напр. 228 passed] | TODO: [Passed] | Усі тести (юніт, правила, авторизація, NFR) зелені |
| Фронтенд (`npm test`) | TODO: [напр. 48 passed] | TODO: [Passed] | Компоненти та моки працюють без помилок |
| Поведінкова регресія | 0 дефектів | Passed | Зовнішня функціональність системи не змінилася |

---

## 8. Опис виконаних рефакторингів та висновки

> Кожен учасник команди документує свій виконаний рефакторинг (щонайменше один із використанням ШІ-агента).

### Рефакторинг 1 (Виконавець: Данило Савчук, Аналітик коду / Безпеки)
* **Запах коду (Code Smell):** TODO (наприклад: *Порушення порядку middleware у `main.py`* або *Некоректний виклик `pytest.raises` у `tests/test_free_elective_remaining.py`*)
* **Техніка рефакторингу з каталогу:** TODO (наприклад: *Reorder Middleware Chain* / *Use Idiomatic Context Manager*)
* **Що залишилося незмінним (інваріант):** TODO (наприклад: *Формат відповідей API та додавання заголовків X-Request-ID і CORS*)
* **Який тест це доводить:** TODO (наприклад: *`tests/test_api_common.py`*)
* **Використання ШІ:** Виконано з допомогою ШІ-агента; запропоновані зміни перевірено рядок за рядком; регресійні тести пройдено.

### Рефакторинг 2 (Виконавець: ...)
* **Запах коду:** ...
* **Техніка рефакторингу:** ...
* **Що залишилося незмінним:** ...
* **Який тест це доводить:** ...

---

## 9. Підсумкові висновки

TODO: Короткий висновок команди про ефективність обраних технік рефакторингу, динаміку технічного боргу та уроки інтеграції SonarQube Cloud у процес релізу.

## Використання ШІ

Структуру шаблону (шапка, розділи за категоріями) створено за допомогою Claude Code.
Фактичних даних SonarCloud файл не містить; перевірка — лише перегляд структури.

Статуси `src/api/main.py` L113 і `src/api/routes/preferences.py` L59 оновлено за допомогою Claude Code. Перевірено через API SonarCloud (2026-10-30): аналіз PR #171 (коміт `d263e9a`) — Quality Gate OK, 0 нових проблем; на `main` (аналіз `0b62882`, до виправлень) обидві проблеми ще відкриті, тож остаточно вони закриються після мерджу й нового аналізу.
Статус «Fixed» для пункту 1 розділу Security (script injection у `mutation.yml`) додано за допомогою Claude Code; перевірка — перегляд диффу, нового аналізу SonarCloud ще не було.
Статус «Fixed» для `deanery.py` (Reliability 2, Maintainability 2) додано за допомогою Claude Code; перевірка — перегляд диффу PR #170, нового аналізу SonarCloud ще не було.
До розділу Maintainability та зведеної таблиці додано 9 проблем рівня Low (Number.isNaN та Number.parseInt у згенерованому JS-звіті покриття docs/testing/coverage/) за допомогою Gemini. Перевірено: звірка зі скриншотами панелі SonarCloud та розділом Reliability.
Секції 2.1 (стан «ДО», вибір 3 метрик і Security Rating зі зв'язком з Лаб 3 і 5) та 7–9 (стан «ПІСЛЯ», порівняльна таблиця, регресійне тестування, опис рефакторингів) додано за допомогою Gemini. Перевірено: відповідність критеріям оцінювання Лабораторної роботи 8.
