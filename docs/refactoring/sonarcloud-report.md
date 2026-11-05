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
| 2 | `.github/workflows/deploy-api-docs.yml` L37 | full commit SHA (CWE) | High | Залежність підключена не за повним SHA коміту | Зафіксувати action за повним SHA коміту | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `peaceiris/actions-gh-pages` закріплено за SHA коміту `84c30a8…` (v4.1.0); підтвердить аналіз після мерджу |
| 3 | `.github/workflows/ci.yaml` L21 | hard-coded credential (CWE) | Medium | Виявлено «PASSWORD», можливий захардкоджений секрет | Перевірити, що це не реальний секрет; за потреби винести в GitHub Secrets | Open (імовірний false positive): `POSTGRES_PASSWORD` — пароль тестової БД у service-контейнері CI, не секрет; не змінювалось. Позначити як False Positive у Sonar (потрібні права адміна) |
| 4 | `.github/workflows/ci.yaml` L38 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `pip install --only-binary :all:`; підтвердить аналіз після мерджу |
| 5 | `.github/workflows/ci.yaml` L38 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open: потрібен lock-файл з усіма транзитивними залежностями (`pip-compile`/constraints); окремий PR, у цій лабораторній не виконується |
| 6 | `.github/workflows/ci.yaml` L40 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `pip install --only-binary :all:`; підтвердить аналіз після мерджу |
| 7 | `.github/workflows/ci.yaml` L40 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `ruff==0.17.0`; підтвердить аналіз після мерджу |
| 8 | `.github/workflows/ci.yaml` L42 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `pip install --only-binary :all:`; підтвердить аналіз після мерджу |
| 9 | `.github/workflows/ci.yaml` L42 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `bandit[toml]==1.9.4`; підтвердить аналіз після мерджу |
| 10 | `.github/workflows/ci.yaml` L70 | npm: `--ignore-scripts` (CWE) | Medium | Без `--ignore-scripts` під час встановлення пакетів запускаються lifecycle-скрипти | Додати `--ignore-scripts` | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `npm ci --ignore-scripts` (перевірено на чистій копії: `gen:api`, `typecheck`, 452 тести, `build`); підтвердить аналіз після мерджу |
| 11 | `.github/workflows/deploy-api-docs.yml` L31 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `pip install --only-binary :all:`; підтвердить аналіз після мерджу |
| 12 | `.github/workflows/deploy-api-docs.yml` L31 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open: потрібен lock-файл з усіма транзитивними залежностями (`pip-compile`/constraints); окремий PR, у цій лабораторній не виконується |
| 13 | `.github/workflows/mutation.yml` L30 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`fde10e2`): `pip install --only-binary :all:`; підтвердить аналіз після мерджу |
| 14 | `.github/workflows/mutation.yml` L30 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open: потрібен lock-файл з усіма транзитивними залежностями (`pip-compile`/constraints); окремий PR, у цій лабораторній не виконується |
| 15 | `frontend/src/test/handlers.ts` L274 | захардкоджена IP адреса (S1313 / CWE-547) | Low | Виявлено захардкоджену IP-адресу 10.0.0.15 у фікстурах записів аудиту | Замінено на константу loopback `DEFAULT_MOCK_AUDIT_IP` ("127.0.0.1"), безпечну за S1313 | Fixed: Виправлено в гілці `refactor/ip-address-fix` |
| 16 | `frontend/src/mocks/fixtures.ts` L309 | захардкоджена IP адреса (S1313 / CWE-547) | Low | Виявлено захардкоджену IP-адресу 10.0.0.15 у тестових MSW-хендлерах журналу аудиту | Замінено на константу loopback `DEFAULT_MOCK_AUDIT_IP` ("127.0.0.1"), безпечну за S1313 | Fixed: Виправлено в гілці `refactor/ip-address-fix` |

## 4. Reliability

**Показники:** проблем Reliability — 28 (Blocker 1, High 2, Medium 25); Bugs — 13; рейтинг — C.

**Результати аналізу:**

Знайдено 28 проблем Reliability: Blocker — 1, High — 2, Medium — 25. Три найсерйозніші — у коді бекенда (`main.py`, `deanery.py`, `preferences.py`), вони також враховані в Maintainability. Ще 21 проблема (доступність `<label>`/`<th>`, `isNaN`, `parseInt`) стосується згенерованого звіту покриття в `docs/testing/coverage/`, який краще виключити з аналізу Sonar. Решта: регулярні вирази з backtracking у `pkce.ts` і `download.ts` (по 20 хв), `multipart.ts` та `pytest.raises` у тесті. Схожі проблеми в таблиці згруповано за файлом; кількість окремих проблем вказано в описі.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `src/api/main.py` L113 | cors, configuration | Blocker | `CORSMiddleware` додано не останнім у ланцюжку middleware (також Maintainability, Blocker) | Додавати `CORSMiddleware` останнім | Fixed: `CORSMiddleware` додається останнім, після `RequestIdMiddleware` (PR #171; перевірено в коді `main`) |
| 2 | `src/api/routes/deanery.py` L49 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Maintainability, High) | Додати `= None` | Fixed: у `DeaneryDocumentResponse` додано `= None` для `parse_error` (PR #170) |
| 3 | `src/api/routes/preferences.py` L59 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Maintainability, High) | Додати `= None` | Fixed: у `PreferencesResponse` додано `= None` для `certificate_program_id` (PR #171; перевірено в коді `main`) |
| 4 | `frontend/src/auth/pkce.ts` L5 | regex, performance | Medium | Регулярний вираз із супер-лінійною складністю через backtracking (20 хв) | Спростити регулярний вираз | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`ebaa831`); підтвердить аналіз після мерджу |
| 5 | `frontend/src/lib/download.ts` L5 | regex, performance | Medium | Регулярний вираз із супер-лінійною складністю через backtracking (20 хв) | Спростити регулярний вираз | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`ebaa831`); підтвердить аналіз після мерджу |
| 6 | `frontend/src/test/multipart.ts` L7 | type-dependent | Medium | Причина відхилення Promise не є `Error` | Відхиляти Promise з `new Error(...)` | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`f90af3f`); підтвердить аналіз після мерджу |
| 7 | `tests/test_free_elective_remaining.py` (L19) | pytest, tests | Medium | Виняток перевіряється не через контекстний менеджер (також Maintainability, Medium) | Використати `with pytest.raises(...)` | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`1603686`); підтвердить аналіз після мерджу |
| 8 | `docs/testing/coverage/class_index.html` L47 | accessibility, wcag2-a | Medium | Поле вводу без пов'язаного `<label>` | Додати `<label>` до поля | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 9 | `docs/testing/coverage/class_index.html` L80, L85, L89 | accessibility, wcag2-a | Medium | Тег `<th>` без атрибута `id` або `scope` (3 шт.) | Додати `scope` або `id` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 10 | `docs/testing/coverage/function_index.html` L47 | accessibility, wcag2-a | Medium | Поле вводу без пов'язаного `<label>` | Додати `<label>` до поля | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 11 | `docs/testing/coverage/function_index.html` L80, L85, L89 | accessibility, wcag2-a | Medium | Тег `<th>` без атрибута `id` або `scope` (3 шт.) | Додати `scope` або `id` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 12 | `docs/testing/coverage/index.html` L46 | accessibility, wcag2-a | Medium | Поле вводу без пов'язаного `<label>` | Додати `<label>` до поля | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 13 | `docs/testing/coverage/index.html` L77, L82, L86 | accessibility, wcag2-a | Medium | Тег `<th>` без атрибута `id` або `scope` (3 шт.) | Додати `scope` або `id` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 14 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L53 | convention | Medium | `isNaN` замість `Number.isNaN` (2 проблеми на одному рядку; також Maintainability, Low) | Замінити на `Number.isNaN` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 15 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L203, L204, L207, L324, L556, L576, L671 | convention | Medium | `parseInt` замість `Number.parseInt` (7 шт.; також Maintainability, Low) | Замінити на `Number.parseInt` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |

## 5. Maintainability

**Показники:** проблем Maintainability — 16 (Blocker 4, High 2, Medium 1, Low 9); Code Smells — 20; Technical Debt — 2h 24min; Debt Ratio — 0 %; рейтинг — A.

**Результати аналізу:**

Знайдено 16 проблем Maintainability: Blocker — 4, High — 2, Medium — 1, Low — 9. Чотири з них (CORS у `main.py`, значення за замовчуванням у `deanery.py` і `preferences.py`, `pytest.raises`) одночасно належать до Reliability. Ще три Blocker — неоголошені змінні в згенерованому `coverage_html_cb_*.js` (звіт покриття в `docs/testing/coverage/`); цей файл генерується інструментом покриття, тож його краще виключити з аналізу Sonar, а не правити вручну. Решта 9 проблем категорії Low — це convention-зауваження (`Number.isNaN` та `Number.parseInt`) у тому ж згенерованому файлі покриття. Усі проблеми мають оцінку трудомісткості 2–5 хв.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `src/api/main.py` L113 | cors, configuration | Blocker | `CORSMiddleware` додано не останнім у ланцюжку middleware (також Reliability, Blocker) | Додавати `CORSMiddleware` останнім | Fixed: див. Reliability №1 (PR #171) |
| 2 | `src/api/routes/deanery.py` L49 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Reliability, High) | Додати явне значення за замовчуванням (`= None`) | Fixed: у `DeaneryDocumentResponse` додано `= None` для `parse_error` (PR #170) |
| 3 | `src/api/routes/preferences.py` L59 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Reliability, High) | Додати явне значення за замовчуванням (`= None`) | Fixed: див. Reliability №3 (PR #171) |
| 4 | `tests/test_free_elective_remaining.py` L19 | pytest, tests | Medium | Виняток перевіряється не через контекстний менеджер (також Reliability, Medium) | Обгорнути код, що кидає виняток, у `with pytest.raises(...)` | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`1603686`); підтвердить аналіз після мерджу |
| 5 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L166 | pitfall | Blocker | Змінна `cell` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 6 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L358 | pitfall | Blocker | Змінна `cls` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 7 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` (рядок не вказано) | pitfall | Blocker | Змінна `key` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 8 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L53 | convention | Low | `isNaN` замість `Number.isNaN` (2 проблеми на одному рядку; також Reliability, Medium) | Замінити на `Number.isNaN` (або виключити звіт покриття з аналізу) | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 9 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L203, L204, L207, L324, L556, L576, L671 | convention | Low | `parseInt` замість `Number.parseInt` (7 шт.; також Reliability, Medium) | Замінити на `Number.parseInt` (або виключити звіт покриття з аналізу) | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |

## 6. Duplications

**Показники:** файлів з дублюванням — 46; дубльованих рядків — 3170; Duplicated Lines Density — 5,5%; Duplicated Blocks — 202; Duplicated Files — 46.

**Результати аналізу:**

Sonar показує дублювання у 46 файлах, усього 3170 дубльованих рядків. З них 41 файлів (3069 рядків) — згенерований звіт покриття в `docs/testing/coverage/`; його варто виключити з аналізу, після чого дублювання у цих файлах зникне. Реальний код — 5 файлів фронтенду (101 рядків): тести та моки, де дублюються повторювані блоки. Відсоток дублювання по всьому проєкту у вставці не наведено. Згенеровані файли згруповано в один рядок таблиці.

| # | Файли з дублюванням | Дубльовані рядки (%) | Кількість рядків | Опис | План усунення | Статус |
|---|---|---|---|---|---|---|
| 1 | `docs/testing/coverage/*.html` (41 файлів, згенерований звіт покриття) | 7.5–71.0 % | 3069 | Дублюється типова розмітка HTML-звіту (найбільше в `__init__.py`-сторінках: 71,0 %; у `index.html` — 36,7 %, 243 рядки) | Виключити `docs/testing/coverage/` з аналізу Sonar (`sonar.exclusions`) або не комітити згенерований звіт | Виключено з аналізу в `.sonarcloud.properties` (`4a57173`); ефект з'явиться після мерджу й нового аналізу |
| 2 | `frontend/src/auth/login.test.ts` | 18.2 % | 27 | Повторювані блоки в тесті | Винести спільний код у допоміжну функцію / фікстуру | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`8c0ce5a`, `it.each`); точний блок Sonar звірити після аналізу |
| 3 | `frontend/src/features/plan-view/export.test.tsx` | 14.9 % | 14 | Повторювані блоки в тесті | Винести спільний код у допоміжну функцію / фікстуру | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`e828997`) |
| 4 | `frontend/src/mocks/core.ts` | 7.8 % | 23 | Повторюваний код у мок-даних | Винести спільний код у допоміжну функцію / фікстуру | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`49f0422`) |
| 5 | `frontend/src/test/handlers.ts` | 7.1 % | 23 | Повторюваний код в MSW-хендлерах | Винести спільний код у допоміжну функцію / фікстуру | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`49f0422`) |
| 6 | `frontend/src/features/plan-view/view.test.tsx` | 6.8 % | 14 | Повторювані блоки в тесті | Винести спільний код у допоміжну функцію / фікстуру | Fixed: Виправлено в гілці `refactor/sonar-report-fixes` (`e828997`) |

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

Фінальний прогін виконано 2026-11-05 на `main` (коміт `c00fa86`, після злиття PR #197 з рефакторингами й PR #198 з автоматизованим релізом, версія 0.1.1). Середовище: macOS (MacBook M1 Pro), Python 3.12, чиста копія залежностей (`pip install -r requirements.txt -r requirements-dev.txt`, `npm ci`).

| Тестовий набір | Кількість тестів | Статус | Коментар |
|---|---|---|---|
| Бекенд (`pytest -q`) | 389 passed, 1 skipped | Passed | Один тест пропущено навмисно: `tests/test_db_schema.py:61` — тригер append-only існує лише в PostgreSQL, а локально тести йдуть на SQLite. Це не збій і не зміна поведінки |
| Фронтенд (`npm test -- --run`) | 452 passed (49 файлів) | Passed | Було 443 до додавання тестів для `download.ts` і `pkce.ts`; жоден наявний тест не змінювався з очікуваної поведінки |
| Типи (`npm run gen:api && npm run typecheck`) | 0 помилок | Passed | Див. примітку про перший прогін нижче |
| Лінтер фронтенду (`npx eslint .`) | 0 помилок | Passed | |
| Поведінкова регресія | 0 дефектів | Passed | Зовнішня функціональність системи не змінилася |

**Збої та їхні причини.** Рефакторинг-збоїв (тест, що почав падати після зміни коду) не було. Єдина помилка за весь прогін — перший запуск `npx tsc --noEmit` у `frontend/` без попередньої генерації типів: 16 помилок (`TS2307` для `./generated/schema` і похідні `TS7006`/`TS7053` implicit any). Причина — файл `src/api/generated/schema` не комітиться в репозиторій, а створюється командою `npm run gen:api`. Після `npm run gen:api` перевірка типів проходить без помилок. Код не змінювався.

**Як регресія контролювалась протягом роботи:**
* кожен рефакторинг виконано окремим комітом із повним прогоном тестів (деталі в розділі 8);
* для кожного рефакторингу визначено тест, що доводить збереження зовнішньої поведінки (розділ 8);
* перед злиттям у `main` усі перевірки PR були зелені (Quality Gate пройдено, 5 checks passed);
* після злиття повний набір тестів повторно запущено на `main` (таблиця вище).

---

## 8. Опис виконаних рефакторингів та висновки

> Кожен учасник команди документує свій виконаний рефакторинг (щонайменше один із використанням ШІ-агента).

### Рефакторинги за звітом SonarQube Cloud (Виконавець: Владислав Смирнов, керівник рефакторингу; виконано з ШІ-агентом Claude Code)

#### Запахи й техніки

| Категорія | Code Smell | Опис (джерело в звіті) | Рішення (Refactoring) | Коміт |
|---|---|---|---|---|
| Надмірність (Duplications) | Duplicate Code | Однаковий блок імітації завантаження файлу в двох тестах (Duplications №3, №6) | Extract Method | `e828997` |
| Надмірність (Duplications) | Duplicate Code | Тіло відповіді `/config` продубльоване в моках і тестових хендлерах (Duplications №4, №5) | Extract Method | `49f0422` |
| Надмірність (Duplications) | Duplicate Code | Три тести з однаковою структурою (Duplications №2) | Parameterize Method | `8c0ce5a` |
| Надійність (Reliability) | Невірне використання API (правило Sonar для pytest) | `pytest.raises` викликається з lambda (Reliability №7, Maintainability №4) | Substitute Algorithm | `1603686` |
| Надійність (Reliability) | Відхилення Promise не з `Error` (правило Sonar) | `reject(reader.error)`, де значення може бути `null` (Reliability №6) | Replace Error Code with Exception | `f90af3f` |
| Надійність (Reliability) | Regex з backtracking (правило Sonar, performance) | Квадратична складність у `download.ts` і `pkce.ts` (Reliability №4, №5) | Substitute Algorithm | `ebaa831` |
| Згенерований код | Згенерований звіт покриття | Дублювання й проблеми в `docs/testing/coverage/` (Duplications №1, Reliability №8–15, Maintainability №5–7) | не Refactoring: зміна області аналізу (`.sonarcloud.properties`) | `4a57173` |
| Безпека (Security, CI/CD) | Небезпечні налаштування CI | `pip` без `--only-binary`, незакріплені ruff/bandit, `npm ci` без `--ignore-scripts`, action без SHA (Security №2, №4, №6–11, №13) | не Refactoring: hardening конфігурації CI | `fde10e2` |

#### Для кожного рефакторингу: що лишається незмінним, що змінюється, який тест це доводить

**1. Extract Method: `mockDownloads()`.**
- *Незмінне:* поведінка тестів `export.test.tsx` і `view.test.tsx`: той самий стаб `URL.createObjectURL`, той самий перехоплений `click` по `<a download>`, масив `saved` скидається перед кожним тестом, spy відновлюється після.
- *Змінюється в структурі:* 14 однакових рядків з двох файлів винесено в `src/test/downloads.ts`, обидва файли викликають `const saved = mockDownloads()`.
- *Доказ:* `export.test.tsx` і `view.test.tsx` (16 тестів) проходять до й після; вони перевіряють імена збережених файлів у `saved`.

**2. Extract Method: `configFixture(features)`.**
- *Незмінне:* JSON-відповідь `GET /config`: для dev-моків `saz_sync: true`, для тестів `false`, усі інші поля ті самі. Імпорти `configFixture` з `test/handlers` у ~20 тестах не змінились (ре-експорт).
- *Змінюється в структурі:* 23 дубльовані рядки замінено одним джерелом у `mocks/fixtures.ts`; `core.ts` викликає `configFixture({ saz_sync: true })`.
- *Доказ:* `mocks/core.test.ts`, `mocks/handlers.test.ts` і всі тести, що використовують `configHandler` (повний прогін: 49 файлів зелені).

**3. Parameterize Method: `it.each` у `login.test.ts`.**
- *Незмінне:* три сценарії відхилення (чужий `state`, `error` від Microsoft, немає `code`), очікувані коди `OAUTH_STATE_MISMATCH` / `OAUTH_ERROR` / `OAUTH_MISSING_CODE` і те, що запиту до API не було.
- *Змінюється в структурі:* три копії тіла тесту замінено таблицею випадків і одним тілом.
- *Доказ:* `login.test.ts`: 12 тестів зелені до й після; кожен випадок лишився окремим тестом.

**4. Substitute Algorithm: `with pytest.raises`.**
- *Незмінне:* перевіряється, що `free_elective_remaining(-1)` кидає `ValueError`.
- *Змінюється:* виклик у lambda замінено блоком `with`; це ідіоматична форма, яку вимагає правило Sonar.
- *Доказ:* `tests/test_free_elective_remaining.py` (4 тести) зелені.

**5. Replace Error Code with Exception: `multipart.ts`.**
- *Незмінне:* `readBytes` резолвить `Uint8Array`, на успішному шляху нічого не змінилось.
- *Змінюється:* у `reader.onerror` відхилення йде з `reader.error ?? new Error(...)`, а не з потенційним `null`.
- *Доказ:* `multipart.test.ts` і всі тести завантаження файлів (повний прогін зелений). Шлях помилки окремо тестом не покрито: ризик низький, бо змінено лише значення причини відхилення.

**6. Substitute Algorithm: regex.**
- *Незмінне:* результат `parseDispositionFilename` для всіх підтримуваних форм заголовка (`filename*=UTF-8''…`, `filename="…"`, `filename=…`, null) і результат `randomUrlSafe` (base64url без доповнення). У `download.ts` змінений regex розпізнає ту саму мову (`\s*` перед `[^']*` був зайвим, бо `[^']*` уже охоплює пробіли). У `pkce.ts` `=` у base64 бувають лише як кінцеве доповнення, тож `/=/g` дає той самий результат, що й `/=+$/`.
- *Змінюється:* складність обробки «поганого» входу з квадратичної до лінійної. Виміри: 32 000 пробілів у заголовку — було ≈ 1043 мс, стало ≈ 0,1 мс. Для `pkce.ts` ризик теоретичний (у base64 максимум два `=`), виправлення потрібне для відповідності правилу Sonar.
- *Доказ:* нові тести `download.test.ts` (граничні випадки `filename*` і тест лінійності: до виправлення падав на 1222 мс при порозі 100 мс, після — зелений) і `pkce.test.ts` (довжина й відсутність `=` для 1, 2, 3, 16, 31, 32 байтів; вектор RFC 7636).

**7. Виключення згенерованого звіту покриття.** Це не рефакторинг, а зміна області аналізу: `docs/testing/coverage/**` додано до `sonar.exclusions` і `sonar.cpd.exclusions` у `.sonarcloud.properties`. Дублювання й проблеми Reliability/Maintainability у цих файлах зникнуть через зміну налаштувань, а не через покращення коду.

**8. Security (CI/CD), не рефакторинг коду.** У `ci.yaml`, `deploy-api-docs.yml` і `mutation.yml` додано `pip install --only-binary :all:`, закріплено `ruff==0.17.0` і `bandit==1.9.4`, `npm ci --ignore-scripts`, `peaceiris/actions-gh-pages` закріплено за SHA (коміт `fde10e2`). Перевірено локально: усі залежності `requirements*.txt` мають готові manylinux-wheels для CPython 3.12 (`pip download --only-binary :all:` без помилок); `npm ci --ignore-scripts` на чистій копії проходить `gen:api`, `typecheck`, 452 тести й `build`. Не виправлено: пункти про незафіксовані версії для `requirements.txt` (потрібен lock-файл) і `POSTGRES_PASSWORD` (імовірний false positive). Робота CI на self-hosted runner підтвердиться лише прогоном PR.

#### Регресійне тестування на гілці `refactor/sonar-report-fixes`
- `pytest -q`: 389 passed, 1 skipped.
- `vitest run`: 452 passed (49 файлів); було 443 до додавання тестів у п. 6.
- `tsc --noEmit` і `eslint .`: без помилок.
- Збоїв, що потребують документування, не було.

---

### Рефакторинг за звітом SonarQube Cloud (Виконавець: Данило Савчук, аналітик коду та аналітик безпеки; PR #171 та гілка `refactor/ip-address-fix`, виконано з ШІ-агентом)

#### Запахи й техніки

| Категорія | Code Smell | Опис (джерело в звіті) | Рішення (Refactoring) | Коміт |
|---|---|---|---|---|
| Надійність (Reliability) | Архітектурна помилка конвеєра (Misplaced Middleware) | `CORSMiddleware` додано не останнім у ланцюжку Starlette (Reliability №1, Maintainability №1, Blocker) | Reorder Statements | `d263e9a` |
| Підтримуваність (Maintainability) | Неповне визначення типу (Incomplete Type Definition) | Опційне поле моделі без явного значення за замовчуванням (Reliability №3, Maintainability №3, High) | Introduce Default Parameter | `b35dcac` |
| Безпека (Security) / Надмірність | Захардкоджена IP-адреса / Magic Literal | Хардкод IP `10.0.0.15` у тестових хендлерах та моках (Security №15, №16, S1313) | Replace Magic Literal with Constant | гілка `refactor/ip-address-fix` |

#### Для кожного рефакторингу: що лишається незмінним, що змінюється, який тест це доводить

**1. Reorder Statements: порядок `CORSMiddleware` у `src/api/main.py`.**
- *Незмінне:* маршрутизація всіх ендпоінтів API, реєстрація обробників помилок `register_error_handlers`, логіка додавання `X-Request-ID` у `RequestIdMiddleware` та бізнес-поведінка застосунку.
- *Змінюється в структурі:* `CORSMiddleware` перенесено в кінець викликів `app.add_middleware()`, після `RequestIdMiddleware`. Оскільки в архітектурі Starlette middleware огортають застосунок за принципом цибулини (останній доданий виконується найпершим ззовні), `CORSMiddleware` стає найзовнішнім шаром, гарантуючи додавання заголовків `access-control-allow-*` навіть у разі падіння внутрішніх обробників з кодами 4xx/5xx.
- *Доказ:* `tests/test_api_smoke.py` та `tests/test_request_id.py` (усі тести зелені до й після); ручний HTTP-запит з заголовком `Origin` на неіснуючий маршрут підтверджує присутність CORS-заголовків на відповіді 404.

**2. Introduce Default Parameter: явне `= None` для `certificate_program_id` у `src/api/routes/preferences.py`.**
- *Незмінне:* семантика контракту API для ендпоінтів `GET` та `PUT /preferences/{academic_year}`, схема таблиць бази даних і логіка збереження побажань студента.
- *Змінюється в структурі:* у Pydantic-моделі `PreferencesResponse` визначення поля `certificate_program_id: Optional[int]` доповнено явним значенням за замовчуванням `= None`. Це запобігає валідаційним збоям під час серіалізації моделей без заповненого сертифіката та відповідає стандарту валідації Pydantic v2.
- *Доказ:* `tests/test_preferences.py` (2 тести) та `tests/test_ai.py` (5 тестів) проходять успішно; синхронізовано схему в `docs/api/openapi-generated.json` та `docs/api/openapi-generated.yaml`.

**3. Replace Magic Literal with Constant: `DEFAULT_MOCK_AUDIT_IP` у `frontend/src/mocks/fixtures.ts` та `frontend/src/test/handlers.ts`.**
- *Незмінне:* структура записів журналу аудиту `AuditLogEntry`, відображення IP-адреси на сторінці аудиту в UI `AuditPage` та поведінка моків/тестів.
- *Змінюється в структурі:* магічний рядок адреси приватної мережі `"10.0.0.15"` замінено на спільну константу `DEFAULT_MOCK_AUDIT_IP = "127.0.0.1"`, яка експортується з `mocks/fixtures.ts` і використовується в `handlers.ts` та тесті `audit.test.tsx`. Використання loopback-адреси відповідає виняткам правила Sonar S1313 і запобігає тригеру вразливості, одночасно прибираючи дублювання літерала.
- *Доказ:* `src/features/admin/audit/audit.test.tsx` (10 тестів зелені), повний прогін `vitest run` (452 тести зелені).

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
Статус «Fixed» для `deanery.py` (Reliability 2, Maintainability 2) додано за допомогою Claude Code; перевірка — перегляд диффу PR #170, нового аналізу SonarCloud ще не було. Статуси `Fixed` для CORS і `preferences.py` оновлено за допомогою Claude Code (перевірено в коді `main` і за мерджами PR #168, #170, #171; фактичної верифікації окремих issues у Sonar не виконувалось).
До розділу Maintainability та зведеної таблиці додано 9 проблем рівня Low (Number.isNaN та Number.parseInt у згенерованому JS-звіті покриття docs/testing/coverage/) за допомогою Gemini. Перевірено: звірка зі скриншотами панелі SonarCloud та розділом Reliability.
Секції 2.1 (стан «ДО», вибір 3 метрик і Security Rating зі зв'язком з Лаб 3 і 5), 7–9 (стан «ПІСЛЯ», порівняльна таблиця, регресійне тестування, детальний опис трьох рефакторингів Данила Савчука) та рефакторинг DEFAULT_MOCK_AUDIT_IP у fixtures.ts/handlers.ts додано та оновлено за допомогою Gemini. Перевірено: pytest, vitest run (452 тести зелені), tsc --noEmit, eslint, відповідність критеріям Лабораторної роботи 8.

### Рефакторинг із ШІ-агентом (Лаб 8)
- **Хто й що згенерував:** Claude Code (Anthropic) виконав рефакторинги 1–6 з розділу 8 у гілці `refactor/sonar-report-fixes`, змінив `.sonarcloud.properties`, додав тести (`download.test.ts`, `pkce.test.ts`) і посилив workflow CI (Security-зміни, п. 8 переліку в розділі 8: перевірено локально, роботу на runner підтвердить прогін PR).
- **Завдання агенту:** запах зі звіту → техніка → інваріант («зовнішня поведінка не змінюється, тести проходять після кожного кроку»); див. таблицю в розділі 8.
- **Як верифіковано:** кожен рефакторинг окремим комітом з повним прогоном тестів (результати в розділі 8); для regex — вимірювання часу на старому й новому коді та тест, що падав до виправлення (1222 мс при порозі 100 мс).
- **Перегляд людиною рядок за рядком:** виконано керівником рефакторингу на сторінці PR #197 (Files changed) до злиття.

## Бонуси

### Автоматизований реліз

Версію, запис у `CHANGELOG.md` і git-тег створює інструмент у CI, а не людина. Коміти й назви PR у форматі Conventional Commits, `refactor:` дає patch.

**Інструмент:** python-semantic-release. Release-please не використано, бо організація `ukma-fin-ssdm-2026` забороняє GitHub Actions створювати PR (API повертає `The organization does not allow GitHub Actions to create or approve pull requests`), а release-please працює через Release PR. Python-semantic-release працює без PR: бот комітить версію й журнал у `main` і ставить тег, для чого достатньо `contents: write`.

**Як працює:**
1. PR зливаємо squash-merge, тож назва PR стає комітом на `main`. Формат назви перевіряє `.github/workflows/pr-title.yml`.
2. На push у `main` стартує `.github/workflows/release.yml` і запускає `semantic-release version`.
3. Інструмент бере останній тег `vX.Y.Z` (базовий `v0.1.0`) і читає коміти після нього. Тип коміту визначає рівень: `fix:`, `perf:`, `refactor:` дають patch, `feat:` дає minor, `feat!:` або `BREAKING CHANGE` дає major (до 1.0.0 minor), `docs:`/`test:`/`ci:`/`build:`/`chore:`/`style:` реліз не створюють.
4. Бот оновлює `version` у `pyproject.toml`, дописує блок у `CHANGELOG.md`, комітить `chore(release): X.Y.Z`, ставить тег `vX.Y.Z` і створює GitHub Release.

**Налаштування «`refactor:` дає patch».** За замовчуванням інструмент рефакторинг не релізить. У `pyproject.toml`, розділ `[tool.semantic_release.commit_parser_options]`: `patch_tags = ["fix", "perf", "refactor"]`.

**Формат журналу.** Власні шаблони в `.github/changelog-templates/` дають заголовок `## [X.Y.Z] - РРРР-ММ-ДД` і секцію `### Refactoring`; службові коміти (`ci:`, `docs:`, `test:`, `chore:`, `build:`, `style:`) із журналу виключено.

**Правила команди:** `TeamCharter.md` (розділ 10.1) і `AGENTS.md` (розділ 9.1).

#### Докази

| Що | Посилання |
|---|---|
| PR з налаштуванням релізу | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/pull/198 |
| PR з рефакторингом (джерело `refactor:`-коміту) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/pull/197 |
| Базовий тег `v0.1.0` (стан `pre-refactor`, коміт `8bdc115`) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/releases/tag/v0.1.0 |
| **Прогін workflow `Release`, який створив реліз Лаб 8** (спроба 2; спроба 1 впала на `git push` з 403, бо токен ще не був схвалений організацією) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/actions/runs/42014996328 |
| Коміт `chore(release): 0.1.1` (автор: `semantic-release`; змінює `pyproject.toml` і `CHANGELOG.md`) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/commit/339f226 |
| Тег `v0.1.1` і GitHub Release | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/releases/tag/v0.1.1 |
| `CHANGELOG.md` із секцією `## [0.1.1] - 2026-11-05` / `### Refactoring` (6 записів `refactor:`) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/blob/v0.1.1/CHANGELOG.md |

#### Верифікація до першого прогону в CI

Повний прогін `semantic-release version` (без push і без GitHub Release) в одноразовому клоні репозиторію:
- `refactor:` після `v0.1.0` дає 0.1.1, потім `feat:` дає 0.2.0;
- створюються коміт `chore(release)`, теги `v0.1.1` / `v0.2.0` і оновлений `version` у `pyproject.toml`;
- заголовок журналу `## [0.1.1] - дата`, секція `### Refactoring`, службові коміти відсутні, повторний реліз не дублює записи;
- коли випускати нічого (лише `docs:`/`ci:`), інструмент виходить із кодом 0 і повідомленням `No release will be made`;
- залежності інструмента ставляться лише з wheel-ів для Linux (`pip install --only-binary :all:`).

Справжній прогін у GitHub Actions на self-hosted runner відбувся 2026-11-05 після злиття PR #198 і #197: версія в `pyproject.toml` (0.1.1), заголовок у `CHANGELOG.md` (`## [0.1.1]`) і git-тег (`v0.1.1`) збігаються. Перший прогін після #198 дав `No release will be made` (серед нових комітів не було `refactor:`/`fix:`/`feat:`), після #197 інструмент визначив `patch` і порахував 0.1.1.

**Що довелось налаштувати, і чому перші спроби впали.** Основна гілка захищена двома rulesets (зміни лише через PR, 3 схвалення, обов'язкові перевірки `frontend` і `build`), винятків не було, тож push релізного коміту ботом блокувався б. Тому: (1) у обидва rulesets додано виняток для ролі Repository admin (режим `always`); (2) для push використовується секрет `RELEASE_TOKEN` (fine-grained PAT з Contents: Read and write, схвалений організацією). Перший реліз-прогін впав двічі з очікуваних причин: `Upstream branch has changed` (поки він йшов, у `main` злили інший PR; інструмент свідомо не випускає реліз із застарілого коміту) і `403 Permission denied` (токен ще не був схвалений). Повторний прогін для актуального `main` завершився успішно.

#### Хто пояснює бонус у відео

Владислав Смирнов: https://www.loom.com/share/e2cdf412665e4de08e1192fed83080f2 (також у `Labs/Lab08/video_Vladyslav.txt`). У відео пояснено, що саме зроблено й як працює автоматичний реліз.

#### Використання ШІ

Налаштування релізу (конфіг у `pyproject.toml`, `.github/workflows/release.yml`, `pr-title.yml`, шаблони журналу, правила в `TeamCharter.md` і `AGENTS.md`) створено за допомогою Claude Code (Anthropic). Перевірка: локальний прогін інструмента та YAML, перегляд PR #198 виконано керівником рефакторингу до злиття; справжній прогін у CI після злиття.