# Тест-план — YourPathUkma

- Стан на 2026-10-23 (гілка `lab07/test-plan`, від `main`)
- Автор: команда SOLIDni
- Пов'язані документи: [стратегія тестування](../testing/testing-strategy.md), [RTM](../requirements/rtm.md), [вимоги](../requirements/requirements.md), [модель загроз](../architecture/threat-model.md)

**Обсяг.** Тестуємо реалізований код бекенду: правила плану (`src/services/plan_rules.py`), CRUD і валідацію планів (`src/api/routes/plans.py`), каталог дисциплін (`src/api/routes/disciplines.py`). Свідомо НЕ тестуємо: генерацію плану мовною моделлю (FR-009, PERF-001, REL-001), парсер САЗ і SyncJob (FR-008, FR-011, PERF-002) — ці частини ще реалізовані як заглушки; автентифікацію (Microsoft 365 SSO, FR-012) — у коді лише заглушка, що приймає будь-який токен; USE-001 (потрібні реальні користувачі).

**Критерії виходу.** Усі тести плану зелені в CI (завдання `build` і `frontend`); покриття `src/` не нижче 80 % (`--cov-fail-under=80`, мета зі [стратегії](../testing/testing-strategy.md), поточне значення 85 %); mutation score `plan_rules.py` не нижче 60 % (поточне 63 %); немає відкритих критичних дефектів і знахідок рівня High (bandit, `npm audit`).

**Ризики.** З них починається таблиця (за [моделлю загроз](../architecture/threat-model.md)):
- обхід лімітів кредитів 25 / 240 через API (R15) — найдорожча помилка для студента;
- доступ до чужого плану за ID (R3, SEC-001);
- студент 4 курсу обходить заборону ручного навантаження (FR-003, R15);
- редагування або видалення плану не в статусі `draft`.

## Тест-кейси

Один рядок — один тест-кейс. Таблицю згруповано за модулями; для кожного з трьох модулів є кейси двох рівнів (модульний та інтеграційний).

| № | Компонент/функція | Рівень тесту | Тип | Очікуваний результат / критерій прийняття | Власник | Вимога |
|---|---|---|---|---|---|---|
| TP-01 | `plan_rules.check_free_elective_total` | модульний | позитивний | Рівно 25.0 кр. вільного вибору за 4 роки → помилок немає | Владислав | FR-010 |
| TP-02 | `plan_rules.check_free_elective_total` | модульний | негативний | Понад 25 кр. → `FREE_ELECTIVE_TOTAL_EXCEEDED`; межові значення 24 / 25 / 26 | Владислав | FR-010 |
| TP-03 | `plan_rules.check_load_levels` | модульний | позитивний | 2 і 3 курс з рівнями навантаження → помилок немає | Владислав | FR-001 |
| TP-04 | `plan_rules.check_load_levels` | модульний | негативний | 4 курс з надісланими рівнями → `LOAD_LEVELS_NOT_ALLOWED` | Владислав | FR-003 |
| TP-05 | `POST /api/v1/plans`: правило `check_load_levels` через API | інтеграційний | негативний | 4 курс з `load_levels` → 422, у `details` є `LOAD_LEVELS_NOT_ALLOWED` | Владислав | FR-003 |
| TP-06 | `POST /api/v1/plans` (`create_plan`) | інтеграційний | позитивний | Валідний план → 201, статус `draft`, план у `GET /api/v1/plans` | Дар'я | FR-004 |
| TP-07 | `POST /api/v1/plans` (`create_plan`) | інтеграційний | негативний | Вільні вибіркові понад ліміт → 422 `FREE_ELECTIVE_LIMIT_EXCEEDED`, план не збережено | Дар'я | FR-010 |
| TP-08 | `plans.collect_rule_errors` | модульний | негативний | Без HTTP і БД: дублікат → `DUPLICATE_COURSE`; лише вільні → `ONLY_FREE_ELECTIVES`; вільні понад 25 → `FREE_ELECTIVE_LIMIT_EXCEEDED`; валідний набір → порожній список | Дар'я (**ще не реалізовано**) | FR-010 |
| TP-09 | `PUT /api/v1/plans/{id}` (`update_plan`) | інтеграційний | негативний | План не в статусі `draft` → 409 `PLAN_NOT_EDITABLE` | Дар'я | FR-004 |
| TP-10 | `DELETE /api/v1/plans/{id}` (`delete_plan`) | інтеграційний | негативний | План не в статусі `draft` → 409 `PLAN_NOT_DELETABLE` | Данило | FR-004 |
| TP-11 | `GET /api/v1/plans/{id}` (`get_plan`, `_find_plan`), запит від іншого студента | інтеграційний | негативний | NFR: чужий план → 403 `PLAN_FORBIDDEN` у 100 % спроб | Данило | SEC-001 |
| TP-12 | `POST /api/v1/plans/validate` (`validate_plan`) | інтеграційний | негативний | Порушення правила → 200, `valid: false`, список помилок | Оксана | FR-010 |
| TP-13 | `POST /api/v1/plans/validate` (`validate_plan`) | інтеграційний | негативний | Без токена → 401 | Оксана | FR-010 |
| TP-14 | `POST /api/v1/plans/validate` (`validate_plan`) | інтеграційний | негативний | Невалідна схема (триместр 5) → 422 | Оксана | FR-010 |
| TP-15 | `GET /api/v1/disciplines` (`list_disciplines`) | інтеграційний | позитивний | З токеном → 200 з `disciplines` і `pagination` (limit, offset, total, has_more) | Оксана | FR-013 |
| TP-16 | `GET /api/v1/disciplines` (`list_disciplines`) | інтеграційний | негативний | Без токена → 401 | Оксана | FR-013 |
| TP-17 | `GET /api/v1/disciplines/{id}` (`get_discipline`) | інтеграційний | негативний | Неіснуючий ID → 404 `DISCIPLINE_NOT_FOUND` у форматі `ErrorResponse` | Оксана (**окремий тест ще не реалізовано**) | FR-013 |
| TP-18 | `disciplines.to_discipline` | модульний | позитивний | Без HTTP і БД: поля курсу відображаються на модель API; кілька викладачів об'єднуються через кому; вільний вибір має порожні `directions` | Оксана (**ще не реалізовано**) | FR-013 |

Нефункціональна вимога SEC-001 покрита рядком TP-11 з вимірюваним порогом: 100 % спроб доступу до чужого плану завершуються кодом 403. Другу частину вимоги («кожна спроба журналюється») ще не реалізовано, тому її в плані немає.

## Поточний стан кейсів

Автоматизовано 15 із 18 кейсів. Кейси TP-08, TP-17, TP-18 позначено «ще не реалізовано»: їх мають написати власники, указані в таблиці. Прогін 2026-10-29 на гілці після злиття `main`: `pytest --cov=src --cov-branch` → усі тести пройшли, покриття `src/` 85 %.

| Кейс | Тест |
|---|---|
| TP-01, TP-02 | `tests/test_plan_rules.py::test_check_free_elective_total_with_previous_years` |
| TP-03, TP-04 | `tests/test_plan_rules.py::test_load_levels_allowed_otherwise`, `test_load_levels_forbidden_on_fourth_course` |
| TP-05 | `tests/test_plan_validation.py::test_create_plan_fourth_course_with_load_levels_is_rejected` |
| TP-06 | `tests/test_db_plans.py::test_create_plan_is_persisted` |
| TP-07 | `tests/test_plan_validation.py::test_create_plan_still_rejects_business_rule_violation` |
| TP-08 | **не реалізовано** (власник: Дар'я) |
| TP-09, TP-10 | `tests/test_db_plans.py::test_submitted_plan_is_read_only` |
| TP-11 | `tests/test_db_plans.py::test_foreign_plan_is_forbidden` |
| TP-12 | `tests/test_plan_validation.py::test_validate_returns_200_with_errors_for_business_rule_violation` |
| TP-13 | `tests/test_plan_validation.py::test_validate_requires_token` |
| TP-14 | `tests/test_plan_validation.py::test_validate_schema_violation_is_422` |
| TP-15 | `tests/test_db_plans.py::test_disciplines_pagination`, `tests/test_api_smoke.py::test_disciplines_list_ok` |
| TP-16 | `tests/test_api_smoke.py::test_disciplines_requires_auth` |
| TP-17 | 404 `DISCIPLINE_NOT_FOUND` частково перевіряє `tests/test_db_plans.py::test_discipline_by_id`; окремий тест зі статусом 404 **не реалізовано** (власник: Оксана) |
| TP-18 | **не реалізовано** (власник: Оксана) |

Зелений прогін у GitHub Actions для цього PR додамо після пушу.

## Поза обсягом цього плану

- FR-002, FR-005, FR-006, FR-007, FR-009 — ще немає реалізації (AI-модуль, обмеження викладачів, напрямки).
- FR-008, FR-011 — парсер САЗ і SyncJob працюють як заглушка.
- FR-012 (автентифікація лише через Microsoft 365 SSO, перевірка домену пошти) — SSO ще не реалізовано, кейси додати після його появи.
- NFR PERF-001, PERF-002, REL-001, USE-001 — залежать від непідключених компонентів.

## Використання ШІ

- **Що створено/змінено:** чернетку цього тест-плану (структуру, формулювання кейсів, розподіл за власниками) підготовлено за допомогою Claude Code.
- **Як перевірено:** ID вимог звірено з `docs/requirements/requirements.md` і `rtm.md`; назви функцій, коди помилок і наявні автотести звірено з вихідним кодом у `src/` та `tests/`. Після відгуку команди Rehab (PR #131) за допомогою Claude Code додано кейси TP-05, TP-08, TP-17, TP-18 (тест для TP-05 написано, інші три призначено власникам і поки не реалізовано), розділено кейси `/plans/validate` і `GET /disciplines`, оновлено ID на `TP-NN` (щоб не збігатися з `Test-NN` у RTM). Повний `pytest --cov=src --cov-branch` запущено локально після злиття `main`: усі тести пройшли, покриття 85 %. Mutation score (63 %) повторно не вимірювали. Розподіл власників — пропозиція, команда має її підтвердити.
