# Тест-план — YourPathUkma

- Стан на 2026-10-23 (гілка `lab07/test-plan`, від `main`)
- Автор: команда SOLIDni
- Пов'язані документи: [стратегія тестування](../testing/testing-strategy.md), [RTM](../requirements/rtm.md), [вимоги](../requirements/requirements.md), [модель загроз](../architecture/threat-model.md)

**Обсяг.** Тестуємо реалізований код бекенду: правила плану (`src/services/plan_rules.py`), CRUD і валідацію планів (`src/api/routes/plans.py`), каталог дисциплін (`src/api/routes/disciplines.py`). Свідомо НЕ тестуємо: генерацію плану мовною моделлю (FR-009, PERF-001, REL-001), парсер САЗ і SyncJob (FR-008, FR-011, PERF-002) — ці частини ще реалізовані як заглушки; автентифікацію (Microsoft 365 SSO, FR-012) — у коді лише заглушка, що приймає будь-який токен; USE-001 (потрібні реальні користувачі).

**Критерії виходу.** Усі тести плану зелені в CI (завдання `build` і `frontend`); покриття `src/` не нижче 80 % (`--cov-fail-under=80`, мета зі [стратегії](../testing/testing-strategy.md), поточне значення 86 %); mutation score `plan_rules.py` не нижче 60 % (поточне 63 %); немає відкритих критичних дефектів і знахідок рівня High (bandit, `npm audit`).

**Ризики.** З них починається таблиця (за [моделлю загроз](../architecture/threat-model.md)):
- обхід лімітів кредитів 25 / 240 через API (R15) — найдорожча помилка для студента;
- доступ до чужого плану за ID (R3, SEC-001);
- студент 4 курсу обходить заборону ручного навантаження (FR-003, R15);
- редагування або видалення плану не в статусі `draft`.

## Тест-кейси

Таблицю відсортовано за власником.

| № | Компонент/функція | Рівень тесту | Тип | Очікуваний результат / критерій прийняття | Власник | Вимога |
|---|---|---|---|---|---|---|
| 1 | `plan_rules.check_free_elective_total` | модульний | позитивний | Рівно 25.0 кр. вільного вибору за 4 роки → помилок немає | Владислав | FR-010 |
| 2 | `plan_rules.check_free_elective_total` | модульний | негативний | Понад 25 кр. → `FREE_ELECTIVE_TOTAL_EXCEEDED`; межові значення 24 / 25 / 26 | Владислав | FR-010 |
| 3 | `plan_rules.check_load_levels` | модульний | позитивний | 2 і 3 курс з рівнями навантаження → помилок немає | Владислав | FR-001 |
| 4 | `plan_rules.check_load_levels` | модульний | негативний | 4 курс з надісланими рівнями → `LOAD_LEVELS_NOT_ALLOWED` | Владислав | FR-003 |
| 5 | `POST /api/v1/plans` (`create_plan`) | інтеграційний | позитивний | Валідний план → 201, статус `draft`, план у `GET /api/v1/plans` | Дар'я | FR-004 |
| 6 | `POST /api/v1/plans` (`create_plan`) | інтеграційний | негативний | Вільні вибіркові понад 25 кр. → відмова, план не збережено | Дар'я | FR-010 |
| 7 | `PUT /api/v1/plans/{id}` (`update_plan`) | інтеграційний | негативний | План не в статусі `draft` → 409 `PLAN_NOT_EDITABLE` | Дар'я | FR-004 |
| 8 | `DELETE /api/v1/plans/{id}` (`delete_plan`) | інтеграційний | негативний | План не в статусі `draft` → 409 `PLAN_NOT_DELETABLE` | Данило | FR-004 |
| 9 | `GET /api/v1/plans/{id}` (`get_plan`, `_find_plan`), запит від іншого студента | інтеграційний | негативний | NFR: чужий план → 403 `PLAN_FORBIDDEN` у 100 % спроб | Данило | SEC-001 |
| 10 | `POST /api/v1/plans/validate` (`validate_plan`) | інтеграційний | негативний | Порушення правила → 200 зі списком помилок; без токена 401; невалідна схема 422 | Оксана | FR-010 |
| 11 | `GET /api/v1/disciplines` (`list_disciplines`) | інтеграційний | позитивний | Каталог лише на читання: з токеном 200 з пагінацією, без токена 401 | Оксана | FR-013 |
| 12 | `GET /api/v1/disciplines/{id}` (`get_discipline`) | інтеграційний | негативний | Неіснуючий ID → 404 `DISCIPLINE_NOT_FOUND` у форматі `ErrorResponse` | Оксана | FR-013 |

Нефункціональна вимога SEC-001 покрита рядком 9 з вимірюваним порогом: 100 % спроб доступу до чужого плану завершуються кодом 403. Другу частину вимоги («кожна спроба журналюється») ще не реалізовано, тому її в плані немає.

## Поточний стан кейсів

Вже автоматизовано (CI): 1–2, 4 (`tests/test_plan_rules.py`), 3 (`test_load_levels_allowed_otherwise`), 5–8 (`tests/test_db_plans.py`, `tests/test_plan_validation.py`, у т. ч. `test_submitted_plan_is_read_only`), 9 (`test_foreign_plan_is_forbidden`), 10 (`tests/test_plan_validation.py`), 11 (`test_disciplines_pagination`, `test_discipline_by_id` у `tests/test_db_plans.py`). Ще не автоматизовано: 12 (404 для неіснуючої дисципліни) — потрібно дописати. Перед здачею кожен власник перевіряє, що його рядки справді відповідають існуючим тестам, і дописує відсутні.

## Поза обсягом цього плану

- FR-002, FR-005, FR-006, FR-007, FR-009 — ще немає реалізації (AI-модуль, обмеження викладачів, напрямки).
- FR-008, FR-011 — парсер САЗ і SyncJob працюють як заглушка.
- FR-012 (автентифікація лише через Microsoft 365 SSO, перевірка домену пошти) — SSO ще не реалізовано, кейси додати після його появи.
- NFR PERF-001, PERF-002, REL-001, USE-001 — залежать від непідключених компонентів.

## Використання ШІ

- **Що створено/змінено:** чернетку цього тест-плану (структуру, формулювання кейсів, розподіл за власниками) підготовлено за допомогою Claude Code.
- **Як перевірено:** ID вимог звірено з `docs/requirements/requirements.md` і `rtm.md`; назви функцій, коди помилок і наявні автотести звірено з вихідним кодом у `src/` та `tests/`. Тести повторно не запускалися. Розподіл власників — пропозиція, команда має її підтвердити.

## Бонуси

### Тести з техніки тест-дизайну: таблиця переходів між станами плану

**Ділянка логіки.** Життєвий цикл статусу індивідуального плану (`PlanStatus`: `draft`, `submitted`, `awaiting_deanery`, `approved`) і три події API: редагування `PUT /plans/{id}`, видалення `DELETE /plans/{id}` та подання `POST /plans/{id}/submit`. Правило з FR-004 та AGENTS.md: редагувати, видаляти й подавати можна лише план у статусі `draft`, в інших статусах сервер відповідає 409. Подання валідного `draft` переводить його в `submitted`.

**Чому ця техніка.** Поведінка залежить від поточного стану й події, тому таблиця «стан × подія» гарантує, що жодне з 12 сполучень не пропущено. Раніше окремі приклади перевіряли лише частину з них (наприклад, `submitted` + PUT/DELETE у `test_submitted_plan_is_read_only`).

| ID | Стан до | Подія | Результат | Стан після |
|---|---|---|---|---|
| ST-01 | draft | PUT | 200 | draft |
| ST-02 | draft | DELETE | 204 | план видалено |
| ST-03 | draft | submit (валідний план) | 200 | submitted |
| ST-04 | submitted | PUT | 409 `PLAN_NOT_EDITABLE` | submitted |
| ST-05 | submitted | DELETE | 409 `PLAN_NOT_DELETABLE` | submitted |
| ST-06 | submitted | submit | 409 `PLAN_NOT_SUBMITTABLE` | submitted |
| ST-07 | awaiting_deanery | PUT | 409 `PLAN_NOT_EDITABLE` | awaiting_deanery |
| ST-08 | awaiting_deanery | DELETE | 409 `PLAN_NOT_DELETABLE` | awaiting_deanery |
| ST-09 | awaiting_deanery | submit | 409 `PLAN_NOT_SUBMITTABLE` | awaiting_deanery |
| ST-10 | approved | PUT | 409 `PLAN_NOT_EDITABLE` | approved |
| ST-11 | approved | DELETE | 409 `PLAN_NOT_DELETABLE` | approved |
| ST-12 | approved | submit | 409 `PLAN_NOT_SUBMITTABLE` | approved |
| ST-13 | draft | submit (план порушує правила) | 422 `PLAN_VALIDATION_FAILED` | draft |

**Відповідність тестів рядкам таблиці.** Файл `tests/test_plan_status_transitions.py`. ST-01…ST-12 — це один параметризований тест `test_plan_status_transition`, де ID параметра збігається з ID рядка (`test_plan_status_transition[ST-04]` тощо). ST-13 — `test_submit_with_rule_violation_keeps_draft`. Один рядок таблиці дає один випадок.

**Примітка.** Стани `awaiting_deanery` та `approved` API не встановлює (їх виставлятиме деканат), тому в тесті вони задаються напряму в БД. Переходи `submitted` → `awaiting_deanery` → `approved` ще не реалізовані й у таблицю не входять.

**Запуск.** `pytest tests/test_plan_status_transitions.py -v` (13 випадків). Повний набір: `pytest -q --cov=src --cov-branch`, 297 passed, покриття 86 %. Перевірка чутливості: після тимчасового вимкнення перевірки статусу в `update_plan` падають ST-04, ST-07, ST-10.

**Використання ШІ.** Таблицю й тести створено за допомогою Claude Code; перевірено запуском pytest і ручним «вбиванням» перевірки статусу в обробнику (див. вище). Код має прочитати й зрозуміти учасник, який пояснюватиме бонус у відео.
