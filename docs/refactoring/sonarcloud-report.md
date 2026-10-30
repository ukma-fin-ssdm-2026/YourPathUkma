# Звіт про аналіз якості коду в SonarCloud (YourPathUkma)

**Проєкт:** YourPathUkma (REST API + вебфронтенд)
**Відповідальні ролі:** Quality Lead
**Інструмент:** SonarCloud (проєкт `ukma-fin-ssdm-2026_YourPathUkma`)
**Станом на:** TODO
**Версія / коміт аналізу:** TODO

> Шаблон звіту. Значення `TODO` потрібно заповнити за даними з SonarCloud;
> у цьому файлі їх не вигадано.

## 1. Загальна інформація

| Параметр | Значення |
|---|---|
| Репозиторій | ukma-fin-ssdm-2026/YourPathUkma |
| Гілка / PR аналізу | TODO |
| Дата аналізу | TODO |
| Quality Gate | TODO (Passed / Failed) |
| Кількість рядків коду (LoC) | TODO |

## 2. Підсумок за категоріями

| Категорія | Кількість проблем | Рейтинг (A–E) | Висновок |
|---|---|---|---|
| Security | 14 | TODO | Усі проблеми в CI/CD workflow; 1 Blocker (script injection) |
| Reliability | 28 | TODO | 1 Blocker (CORS); 21 проблема у згенерованому звіті покриття |
| Maintainability | 7 | TODO | 4 Blocker; 3 з них у згенерованому JS-звіті покриття |
| Duplications | TODO % | — | TODO |

Додатково: Security Hotspots — TODO, Coverage — TODO %, Technical Debt — TODO.

## 3. Security

**Показники:** проблем Security — 14 (Blocker 1, High 1, Medium 12); Vulnerabilities — TODO; Security Hotspots (переглянуто / усього) — TODO; рейтинг — TODO.

**Результати аналізу:**

Усі 14 проблем категорії Security стосуються CI/CD-конфігурації (`.github/workflows/`), коду застосунку вони не зачіпають. За severity: Blocker — 1, High — 1, Medium — 12. Найкритичніша — ін'єкція скрипта через `inputs.paths` у `mutation.yml`. Решта — незафіксовані версії залежностей, встановлення без `--only-binary :all:` / `--ignore-scripts` та action без фіксації за SHA. Орієнтовна трудомісткість за оцінкою Sonar: 1 год на ін'єкцію, по 30 хв на SHA, PASSWORD і `--ignore-scripts`, по 1 год на кожну з решти.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `.github/workflows/mutation.yml` L36 | script injection (CWE) | Blocker | `inputs.paths` потрапляє напряму в `run`; значення задає той, хто запускає workflow | Передати вираз через змінну середовища (`env:`) і використовувати її в `run` | Open |
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

## 4. Reliability

**Показники:** проблем Reliability — 28 (Blocker 1, High 2, Medium 25); Bugs — TODO; рейтинг — TODO.

**Результати аналізу:**

Знайдено 28 проблем Reliability: Blocker — 1, High — 2, Medium — 25. Три найсерйозніші — у коді бекенда (`main.py`, `deanery.py`, `preferences.py`), вони також враховані в Maintainability. Ще 21 проблема (доступність `<label>`/`<th>`, `isNaN`, `parseInt`) стосується згенерованого звіту покриття в `docs/testing/coverage/`, який краще виключити з аналізу Sonar. Решта: регулярні вирази з backtracking у `pkce.ts` і `download.ts` (по 20 хв), `multipart.ts` та `pytest.raises` у тесті. Схожі проблеми в таблиці згруповано за файлом; кількість окремих проблем вказано в описі.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `src/api/main.py` L113 | cors, configuration | Blocker | `CORSMiddleware` додано не останнім у ланцюжку middleware (також Maintainability, Blocker) | Додавати `CORSMiddleware` останнім | Open |
| 2 | `src/api/routes/deanery.py` L49 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Maintainability, High) | Додати `= None` | Open |
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

**Показники:** проблем Maintainability — 7 (Blocker 4, High 2, Medium 1); Code Smells — TODO; Technical Debt — TODO; Debt Ratio — TODO %; рейтинг — TODO.

**Результати аналізу:**

Знайдено 7 проблем Maintainability: Blocker — 4, High — 2, Medium — 1. Чотири з них (CORS у `main.py`, значення за замовчуванням у `deanery.py` і `preferences.py`, `pytest.raises`) одночасно належать до Reliability. Ще три Blocker — неоголошені змінні в згенерованому `coverage_html_cb_*.js` (звіт покриття в `docs/testing/coverage/`); цей файл генерується інструментом покриття, тож його краще виключити з аналізу Sonar, а не правити вручну. Усі проблеми мають оцінку трудомісткості 2–5 хв.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `src/api/main.py` L113 | cors, configuration | Blocker | `CORSMiddleware` додано не останнім у ланцюжку middleware (також Reliability, Blocker) | Додавати `CORSMiddleware` останнім | Open |
| 2 | `src/api/routes/deanery.py` L49 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Reliability, High) | Додати явне значення за замовчуванням (`= None`) | Open |
| 3 | `src/api/routes/preferences.py` L59 | pydantic, type-hint | High | Необов'язкове поле без явного значення за замовчуванням (також Reliability, High) | Додати явне значення за замовчуванням (`= None`) | Open |
| 4 | `tests/test_free_elective_remaining.py` L19 | pytest, tests | Medium | Виняток перевіряється не через контекстний менеджер (також Reliability, Medium) | Обгорнути код, що кидає виняток, у `with pytest.raises(...)` | Open |
| 5 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L166 | pitfall | Blocker | Змінна `cell` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Open |
| 6 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` L358 | pitfall | Blocker | Змінна `cls` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Open |
| 7 | `docs/testing/coverage/coverage_html_cb_c6c441fc.js` (рядок не вказано) | pitfall | Blocker | Змінна `key` оголошена без `let`/`const`/`var` | Додати `let` / `const` / `var` | Open |

## 6. Duplications

**Показники:** Duplicated Lines Density — TODO %; Duplicated Blocks — TODO; Duplicated Files — TODO.

**Результати аналізу:**

TODO

| # | Файли з дублюванням | Кількість рядків | Опис | План усунення | Статус |
|---|---|---|---|---|---|
| 1 | TODO | TODO | TODO | TODO | TODO |

## 7. Висновки та план рефакторингу

TODO

## Використання ШІ

Структуру шаблону (шапка, розділи за категоріями) створено за допомогою Claude Code.
Фактичних даних SonarCloud файл не містить; перевірка — лише перегляд структури.
