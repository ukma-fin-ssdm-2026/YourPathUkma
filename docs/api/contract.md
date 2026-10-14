# API-контракт фронтенду і бекенду: YourPathUkma (v1)

Мета документа: дати фронтенду і бекенду один контракт, щоб обидві частини можна було розробляти паралельно. Фронтенд працює проти моків, що відповідають цьому документу; бекенд реалізує саме ці форми запитів і відповідей.

Джерела: код `src/api/` (реалізовані кінцеві точки), [`api-design.md`](api-design.md), [`quality-attributes.md`](quality-attributes.md), [`../requirements/requirements.md`](../requirements/requirements.md), [`../requirements/user-stories.md`](../requirements/user-stories.md), [`../architecture/data-model.md`](../architecture/data-model.md), [`../architecture/threat-model.md`](../architecture/threat-model.md), `AGENTS.md`, `Project-Description.md`.

## 0. Як читати цей документ

| Позначка | Значення |
|---|---|
| ✅ **Реалізовано** | Є в коді (`src/api/routes/`) і в `openapi-generated.yaml`. Форма зафіксована; змінювати її можна лише сумісно (див. §1.7). |
| 🟡 **MVP, запропоновано** | Потрібно для екранів MVP, у коді ще немає. Форма — пропозиція цього документа; бекенд реалізує саме її, якщо команда не домовиться інакше. |
| 🔵 **Етап 2, запропоновано** | AI, альтернативи, сертифікатні програми (`AGENTS.md` §8). |
| ⛔ **Заблоковано** | Немає рішення по архітектурі або безпеці; не реалізовувати. |

**Джерело правди:** для ✅-кінцевих точок — згенерована специфікація [`openapi-generated.yaml`](openapi-generated.yaml) (Swagger UI: `/api-docs`). Якщо цей документ і специфікація розходяться, правильна специфікація, а документ треба виправити. Для 🟡/🔵 джерело правди — цей документ, доки кінцева точка не з'явиться в коді.

---

## 1. Загальні правила (для всіх кінцевих точок)

### 1.1. Базова адреса і формат

- Базова адреса: `http://localhost:3000/api/v1` (локально). Виняток: `/health`, він без префікса.
- Формат: JSON, `Content-Type: application/json; charset=utf-8`. Виняток: завантаження документа деканату (`multipart/form-data`, §3.6).
- Назви полів: `snake_case`. Фронтенд не перейменовує їх у camelCase на рівні API-клієнта, щоб типи збігалися зі специфікацією.
- Дати і час: ISO 8601 в UTC, наприклад `"2026-10-08T10:00:00Z"`.
- Кредити: `number` (ECTS, може бути дробовим, напр. `4.5`).
- Ідентифікатори: `integer` (у БД `bigint`, послідовні; див. §1.4 про доступ до чужих ресурсів).
- Порожні колекції повертаються як `[]`, не `null`. Відсутнє необов'язкове значення повертається як `null`.

### 1.2. Заголовки

| Заголовок | Напрямок | Обов'язковий | Опис |
|---|---|---|---|
| `Authorization: Bearer <access_token>` | запит | так, для всіх кінцевих точок, крім `/health` і `/auth/*` | Access-токен після входу через Google SSO (§3.1). **Зараз (заглушка):** приймається будь-який непорожній рядок, напр. `Bearer test`. |
| `Content-Type: application/json` | запит | для POST/PUT з тілом | |
| `Accept-Language` | запит | ні | Не використовується: усі повідомлення `message` зараз українською. |
| `X-Request-ID` | відповідь | 🟡 запропоновано | Унікальний id запиту для логів (`quality-attributes.md`: `request_id` / `correlation_id`). Фронтенд показує його в повідомленні про помилку 5xx («Код помилки: …»). Якщо клієнт сам надіслав `X-Request-ID`, сервер повертає той самий. |
| `Retry-After` | відповідь | разом з 429 | Секунди до повторної спроби (§1.6). |
| `Location` | відповідь | 🟡 разом з 201/202 | URL створеного ресурсу або статусу генерації. |

Cookie: refresh-токен живе в cookie `HttpOnly; Secure; SameSite=Strict` (threat model R7). Фронтенд його не читає і не надсилає вручну. Для запитів до `/auth/refresh` і `/auth/logout` потрібен `credentials: "include"`.

### 1.3. Формат помилки ✅

Усі відповіді 4xx/5xx мають одну форму (`ErrorResponse`, `src/api/common.py`):

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Невалідні вхідні дані",
  "details": [
    { "field": "items.0.credits", "message": "Input should be greater than 0" }
  ]
}
```

| Поле | Тип | Опис |
|---|---|---|
| `code` | string | Машинозчитуваний код (таблиця нижче). **Фронтенд розгалужує логіку лише за `code` і HTTP-статусом**, не за текстом `message`. |
| `message` | string | Текст українською, можна показати користувачу як є. |
| `details` | `ErrorDetail[]` | Для 422: по одному елементу на поле. Інакше `[]`. |
| `details[].field` | string | Шлях до поля через крапку: `items.0.credits`, `academic_year`, `min_credits`. Для бізнес-правил на рівні всього тіла запиту (напр. ліміт вільного вибору) — шлях без конкретного поля (див. нижче). |
| `details[].message` | string | Опис проблеми з полем. |

**Як прив'язати 422 до полів форми:** `field` відповідає шляху в тілі запиту або назві query-параметра. Порушення бізнес-правил з валідатора `CreatePlanRequest` (дублікати, «лише вільний вибір», ліміт 25 кредитів) зараз приходять з `field`, що вказує на тіло запиту загалом, а `message` починається з `Value error, …`. Фронтенд показує такі помилки над формою, а не біля конкретного поля.

**Коди помилок:**

| `code` | HTTP | Коли | Статус |
|---|---|---|---|
| `UNAUTHORIZED` | 401 | Немає токена, порожній або невалідний токен, токен прострочено | ✅ |
| `PLAN_FORBIDDEN` | 403 | План належить іншому студенту | ✅ (див. §6, розбіжність 1) |
| `PLAN_NOT_FOUND` | 404 | Плану не існує | ✅ |
| `DISCIPLINE_NOT_FOUND` | 404 | Дисципліни немає в каталозі | ✅ |
| `PLAN_NOT_EDITABLE` | 409 | PUT плану не в статусі `draft` | ✅ |
| `PLAN_NOT_DELETABLE` | 409 | DELETE плану не в статусі `draft` | ✅ |
| `VALIDATION_ERROR` | 422 | Невалідне тіло або query-параметри, порушення бізнес-правил плану | ✅ |
| `INTERNAL_ERROR` | 500 | Неочікувана помилка сервера (без stack trace у відповіді) | ✅ |
| `HTTP_<код>` | будь-який | Технічна помилка маршрутизації, напр. `HTTP_404` для неіснуючого шляху, `HTTP_405` для неправильного методу | ✅ |
| `FORBIDDEN_ROLE` | 403 | Студент викликає `/admin/*` | 🟡 |
| `DOMAIN_NOT_ALLOWED` | 403 | Вхід з пошти не домену `ukma.edu.ua` (FR-012) | 🟡 |
| `COURSE_NOT_ELIGIBLE` | 409 | Дія недоступна для курсу студента (1 курс; ручний вибір навантаження на 4 курсі) | 🟡 |
| `PLAN_NOT_SUBMITTABLE` | 409 | Подання плану не в статусі `draft` | 🟡 |
| `PLAN_VALIDATION_FAILED` | 422 | План не проходить перевірку нормативів при поданні (§2.4) | 🟡 |
| `NORMATIVE_CONFLICT` | 422 | У плані є дисципліна, на яку вже записав деканат | 🟡 |
| `DOCUMENT_NOT_FOUND` | 404 | Документа деканату немає | 🟡 |
| `FILE_TOO_LARGE` | 413 | Файл > 10 МБ | 🟡 |
| `UNSUPPORTED_FILE_TYPE` | 415 | Не PDF і не DOCX (перевірка за вмістом, не за розширенням) | 🟡 |
| `GENERATION_IN_PROGRESS` | 429 | Студент уже має активну AI-генерацію (R10) | 🔵 |
| `RATE_LIMITED` | 429 | Перевищено ліміт запитів (§1.6) | 🟡 |
| `SYNC_JOB_ALREADY_RUNNING` | 409 | Для цього джерела вже йде `SyncJob` (R4) | 🟡 |
| `MODERATION_ITEM_ALREADY_REVIEWED` | 409 | Елемент модерації вже схвалено або відхилено | 🟡 |
| `AI_UNAVAILABLE` | 503 | LLM недоступна після всіх повторних спроб (REL-001) | 🔵 |
| `ONBOARDING_REQUIRED` | 409 | Студент ще не вказав курс і спеціальність (§3.2.1) | 🟡 |
| `ALREADY_ONBOARDED` | 409 | Повторний онбординг | 🟡 |
| `RECORD_NOT_DELETABLE` | 409 | Запис історії не `self_declared` або вже підтверджений | 🟡 |
| `PREFERENCES_NOT_FOUND` | 404 | Побажань на цей рік ще не збережено | 🟡 |
| `DOCUMENT_IN_USE` | 409 | Документ деканату прив'язаний до плану не в статусі `draft` | 🟡 |
| `USER_NOT_FOUND` | 404 | Користувача немає | 🟡 |
| `CANNOT_CHANGE_OWN_ROLE` | 409 | Адмін змінює роль сам собі | 🟡 |
| `DIRECTION_NOT_FOUND` | 404 | Напрямку немає | 🟡 |
| `DIRECTION_NAME_TAKEN` | 409 | Напрямок з такою назвою вже є | 🟡 |
| `DIRECTION_IN_USE` | 409 | Напрямок використовується, видалити не можна | 🟡 |
| `CERTIFICATE_PROGRAM_NOT_FOUND` | 404 | Сертифікатної програми немає | 🔵 |
| `GENERATION_NOT_FOUND` | 404 | AI-генерації немає | 🔵 |
| `SYNC_JOB_NOT_FOUND` | 404 | `SyncJob` немає | 🟡 |
| `MODERATION_ITEM_NOT_FOUND` | 404 | Елемента модерації немає | 🟡 |

Нові коди можна додавати без нової версії API. Фронтенд для невідомого `code` показує `message` і поводиться за HTTP-статусом.

### 1.4. Автентифікація і доступ

- Студент бачить і змінює **лише власні** плани, побажання, документи. Ідентичність береться з токена, **ніколи з тіла запиту**. У тілі запиту немає `student_id`, і сервер ігнорує таке поле, якщо воно є.
- Роль (`student` / `admin`) береться з БД, не з клієнта. Усі `/admin/*` вимагають роль `admin` (R2).
- Поля, які **сервер обчислює і клієнт ніколи не надсилає**: `student_id`, `status`, `total_credits`, `free_elective_credits`, лічильники кредитів профілю, `course_year`, `created_at`, `updated_at` (R15). Якщо клієнт їх надсилає, сервер їх ігнорує.
- **Поведінка фронтенду на 401:** один раз викликати `POST /auth/refresh`, повторити запит; якщо знову 401, перейти на сторінку входу.
- **Поведінка фронтенду на 403/404 для чужого або відсутнього плану:** показувати однаково («План не знайдено»). Див. §6, розбіжність 1.

### 1.5. Пагінація ✅

Усі списки, що можуть рости (плани, каталог, журнал `SyncJob`, черга модерації), використовують **offset-пагінацію**.

Query-параметри:

| Параметр | Тип | За замовчуванням | Обмеження |
|---|---|---|---|
| `limit` | integer | `20` | 1–100. Значення поза межами → 422 (не обрізається мовчки). |
| `offset` | integer | `0` | ≥ 0. Offset за межами списку → 200 з порожнім масивом. |

Форма відповіді: масив під **назвою ресурсу** (`plans`, `disciplines`, `sync_jobs`, …) + об'єкт `pagination`:

```json
{
  "disciplines": [ /* ... */ ],
  "pagination": { "limit": 20, "offset": 0, "total": 57, "has_more": true }
}
```

| Поле `pagination` | Тип | Опис |
|---|---|---|
| `limit` | integer | Застосований `limit` |
| `offset` | integer | Застосований `offset` |
| `total` | integer | Кількість записів **після фільтрів**, до пагінації |
| `has_more` | boolean | `offset + limit < total` |

Номер сторінки на фронтенді: `page = offset / limit + 1`, кількість сторінок: `ceil(total / limit)`. Фільтри комбінуються через AND. Зміна фільтра скидає `offset` у `0`.

Невеликі довідники (`/directions`, `/certificate-programs`) повертаються без пагінації, простим масивом у полі за назвою ресурсу.

### 1.6. Обмеження частоти запитів 🟡

Із `quality-attributes.md` і threat model (R4, R10, R14):

| Що | Ліміт | Відповідь |
|---|---|---|
| Усі запити | 100 / хв на користувача | 429 `RATE_LIMITED` + `Retry-After` |
| Завантаження документа деканату | 5 / 10 хв | 429 `RATE_LIMITED` |
| AI-генерація | 1 активна на студента, 20 / добу | 429 `GENERATION_IN_PROGRESS` / `RATE_LIMITED` |

Фронтенд для пошуку в каталозі використовує debounce 300–500 мс (`quality-attributes.md`, рядок «Живий пошук»).

### 1.7. Версіонування і зміни контракту

- Версія в шляху: `/api/v1`. Ламаючі зміни (видалення або перейменування поля, зміна типу, зміна значення статус-коду) лише в `/api/v2`.
- **Сумісні зміни без нової версії:** нове необов'язкове поле у відповіді, новий необов'язковий query-параметр, нова кінцева точка, нове значення `code` помилки.
- Наслідок для фронтенду: **ігнорувати невідомі поля** у відповідях (не валідувати відповідь строгою схемою, що падає на зайвих полях).
- Наслідок для бекенду: зміна схеми Pydantic → перегенерувати `docs/api/openapi-generated.*` (`python scripts/generate_openapi.py`) і закомітити, інакше CI впаде.

---

## 2. Спільні типи і бізнес-правила

### 2.1. Перелічення (enum)

| Тип | Значення | Статус | Примітка |
|---|---|---|---|
| `PlanStatus` | `draft`, `submitted`, `awaiting_deanery`, `approved` | ✅ | Редагувати й видаляти можна лише `draft` |
| `LoadLevel` | `low`, `medium`, `high` | ✅ | |
| `DisciplineType` | `normative`, `elective` | ✅ | |
| Триместр | `1` (осінь), `2` (весна), `3` (літо) | ✅ | **Число** в `PlanItem.trimester`, `Discipline.trimester`, фільтрі каталогу |
| Ключі навантаження | `autumn`, `spring`, `summer` | ✅ | **Рядок** лише як ключі в `load_levels` |
| `PlanOrigin` | `manual`, `ai_generated`, `saz_sync` | 🟡 | |
| `UserRole` | `student`, `admin` | 🟡 | |
| `DocumentParseStatus` | `pending`, `parsed`, `failed` | 🟡 | |
| `GenerationStatus` | `pending`, `succeeded`, `failed` | 🔵 | |
| `SyncSource` | `saz_catalog`, `faculty_certificates` | 🟡 | |
| `SyncJobStatus` | `queued`, `running`, `succeeded`, `failed` | 🟡 | |
| `ModerationChangeType` | `add`, `update`, `remove` | 🟡 | |
| `ModerationStatus` | `pending`, `approved`, `rejected` | 🟡 | |
| `CertificateAvailability` | `available`, `unavailable_this_year` | 🔵 | |
| `CourseYearSource` | `self_declared`, `admin`, `saz_sync` | 🟡 | `saz_sync` поки не використовується (R14) |
| `AcademicCategory` | `normative`, `professional`, `free_choice` | 🟡 | Також значення `Discipline.category_for_me` |
| `RecordSource` | `self_declared`, `deanery_document`, `approved_plan`, `admin`, `saz_sync` | 🟡 | |
| `AuditOutcome` | `allowed`, `denied` | 🟡 | |

Відповідність триместрів: `1 ↔ autumn`, `2 ↔ spring`, `3 ↔ summer`. Фронтенд тримає одну функцію-мапер.

### 2.2. Константи нормативів

Фронтенд може використовувати їх для підказок у UI, але **остаточна перевірка завжди на сервері** (`requirements.md`, «Припущення та обмеження»).

| Константа | Значення | Де перевіряється |
|---|---|---|
| Загалом за програму | 240 кредитів / 4 роки | сервер, при поданні плану 🟡 |
| Мінімум на рік | 57 кредитів (орієнтир 57–60) | сервер, при поданні плану 🟡 |
| Вільний вибір, за всі 4 роки | ≤ 25 кредитів | ✅ зараз у межах одного плану; 🟡 сумарно з попередніми роками |
| Профорієнтовні (лічильник профілю) | …/54 | лише відображення |
| Напрямки розвитку | 1–3 | сервер (FR-007) 🔵 |
| Дисциплін у плані | 1–30 | ✅ |
| Кредити однієї дисципліни | > 0 і ≤ 30 | ✅ |
| Навчальний рік | 2024–2030 | ✅ |
| Курс для плану | 2–4 (1 курс: план формує деканат) | ✅ |
| Розмір документа деканату | ≤ 10 МБ, PDF або DOCX | 🟡 |
| Альтернатив на слот | 2–3 | 🔵 (FR-009) |

### 2.3. Правила навантаження за курсом

| Курс | Ручний вибір `load_levels` | Поведінка сервера |
|---|---|---|
| 1 | — | Створити план не можна: `course` поза межами 2–4 → 422 ✅. `GET /me` поверне `can_create_plan: false` 🟡 |
| 2–3 | так, окремо на `autumn` / `spring` / `summer` | Зберігає надіслане |
| 4 | **ні** (FR-003) | 🟡 Сервер **ігнорує** надіслані `load_levels`, розраховує їх із залишку до 240 і повертає в відповіді з `load_levels_mode: "auto"`. Фронтенд показує селектор заблокованим. Зараз (✅) сервер зберігає надіслане як є. |

### 2.4. Перевірки плану: що є помилкою, а що попередженням

| Правило | Чернетка (`POST`/`PUT /plans`) | Подання (`POST /plans/{id}/submit`) |
|---|---|---|
| `course_id` не повторюються | 422 ✅ | 422 |
| План не складається лише з вільного вибору | 422 ✅ | 422 |
| Вільний вибір у плані ≤ 25 | 422 ✅ | 422 |
| Вільний вибір сумарно з попередніми роками ≤ 25 | 422 🟡 | 422 |
| Нормативна дисципліна (`discipline_type = normative`) у плані | 422 ✅ (`NORMATIVE_NOT_ALLOWED` у `details[].message`) | 422 |
| Конфлікт з документом деканату на цей рік | 422 `NORMATIVE_CONFLICT` 🟡 | 422 |
| `course_id` існує в каталозі, `credits`/`trimester` збігаються з каталогом | 422 ✅ (`COURSE_NOT_FOUND` / `COURSE_DATA_MISMATCH` у `details[].message`, `field = items.N.course_id`) | 422 |
| Сума за рік (вибіркові + нормативні) < 57 | **попередження** 🟡 | 422 `PLAN_VALIDATION_FAILED` |
| Обрано `low` хоча б на один триместр, а рік ≥ 57 | **попередження** `LOW_LOAD_FUTURE_INCREASE` (FR-002) 🟡 | попередження |

Чернетку можна зберегти неповною, щоб студент міг повернутися до неї пізніше. Подання вимагає, щоб усі нормативи виконувались.

Попередження повертаються в полі `warnings` плану (§3.4) і з `POST /plans/validate` (§3.4.7):

```json
{ "code": "LOW_LOAD_FUTURE_INCREASE", "message": "Обрано низьке навантаження: навантаження наступних років зросте" }
```

Коди попереджень 🟡: `LOW_LOAD_FUTURE_INCREASE`, `YEAR_CREDITS_BELOW_MIN`, `CERTIFICATE_COURSE_HINT` (🔵, дисципліна входить у сертифікатну програму; `message`: «Ця дисципліна входить у сертифікат X»).

---

## 3. Кінцеві точки

### Зведена таблиця

| Метод | Шлях | Призначення | Статус | Екран |
|---|---|---|---|---|
| GET | `/health` | Стан сервера | ✅ | — |
| GET | `/config` | Публічна конфігурація для фронтенду (ліміти, `client_id`, прапорці) | 🟡 | старт застосунку |
| POST | `/auth/google` | Вхід: обмін коду Google на токени | 🟡 | Вхід |
| POST | `/auth/refresh` | Новий access-токен | 🟡 | усі |
| POST | `/auth/logout` | Вихід | 🟡 | усі |
| GET | `/me` | Профіль і лічильники кредитів | 🟡 | Профіль |
| POST | `/me/onboarding` | Першочергове заповнення курсу і спеціальності | 🟡 | Онбординг |
| GET | `/me/academic-history` | Пройдені дисципліни за попередні роки | 🟡 | Профіль, Індивідуальний план |
| POST | `/me/academic-history` | Додати пройдені дисципліни | 🟡 | Онбординг, Профіль |
| DELETE | `/me/academic-history/{record_id}` | Видалити власний запис історії | 🟡 | Профіль |
| GET | `/preferences/{academic_year}` | Збережені побажання на рік | 🟡 | Створити план |
| PUT | `/preferences/{academic_year}` | Зберегти побажання на рік | 🟡 | Створити план |
| GET | `/plans` | Список планів студента | ✅ | Індивідуальний план, Збережені плани |
| POST | `/plans` | Створити чернетку | ✅ | Створити план |
| GET | `/plans/{plan_id}` | План за id | ✅ | Перегляд плану |
| PUT | `/plans/{plan_id}` | Оновити чернетку (повна заміна) | ✅ | Створити план |
| DELETE | `/plans/{plan_id}` | Видалити чернетку | ✅ | Збережені плани |
| POST | `/plans/validate` | Перевірити план без збереження | 🟡 | Створити план |
| POST | `/plans/{plan_id}/submit` | `draft` → `submitted` | 🟡 | Перегляд плану |
| GET | `/plans/{plan_id}/export` | Експорт плану в PDF | 🟡 | Перегляд плану |
| POST | `/plans/sync-saz` | «Оновити» з САЗ | ⛔ | Індивідуальний план |
| GET | `/disciplines` | Каталог з фільтрами | ✅ | Каталог, Створити план |
| GET | `/disciplines/{discipline_id}` | Дисципліна за id | ✅ | Каталог |
| GET | `/directions` | Довідник напрямків | 🟡 | Побажання, фільтр каталогу |
| GET | `/instructors` | Довідник викладачів | 🟡 | Побажання, фільтр каталогу |
| POST | `/deanery-documents` | Завантажити документ деканату | 🟡 | Створити план |
| GET | `/deanery-documents` | Документи студента | 🟡 | Створити план |
| GET | `/deanery-documents/{document_id}` | Документ + розпізнані нормативні | 🟡 | Створити план |
| GET | `/deanery-documents/{document_id}/file` | Завантажити власний файл | 🟡 | Створити план |
| DELETE | `/deanery-documents/{document_id}` | Видалити документ | 🟡 | Створити план |
| POST | `/plan-generations` | Запустити AI-генерацію | 🔵 | Створити план |
| GET | `/plan-generations/{generation_id}` | Статус AI-генерації | 🔵 | Створити план |
| GET | `/certificate-programs` | Сертифікатні програми | 🔵 | Каталог, Побажання |
| GET | `/certificate-programs/{program_id}` | Програма + звірка дисциплін | 🔵 | Каталог |
| POST | `/admin/sync-jobs` | Запустити парсинг | 🟡 | Адмінка |
| GET | `/admin/sync-jobs` | Журнал `SyncJob` | 🟡 | Адмінка |
| GET | `/admin/sync-jobs/{job_id}` | Деталі `SyncJob` | 🟡 | Адмінка |
| GET | `/admin/moderation-items` | Черга модерації | 🟡 | Адмінка |
| POST | `/admin/moderation-items/{item_id}/approve` | Схвалити зміну | 🟡 | Адмінка |
| POST | `/admin/moderation-items/{item_id}/reject` | Відхилити зміну | 🟡 | Адмінка |
| POST | `/admin/moderation-items/bulk-review` | Масово схвалити/відхилити | 🟡 | Адмінка |
| GET | `/admin/users` | Користувачі (студенти й адміни) | 🟡 | Адмінка |
| GET | `/admin/users/{user_id}` | Користувач + профіль студента | 🟡 | Адмінка |
| PATCH | `/admin/users/{user_id}` | Змінити роль, курс, спеціальність | 🟡 | Адмінка |
| GET | `/admin/users/{user_id}/academic-history` | Історія студента | 🟡 | Адмінка |
| POST | `/admin/users/{user_id}/academic-history/verify` | Підтвердити записи історії | 🟡 | Адмінка |
| POST | `/admin/directions` | Створити напрямок | 🟡 | Адмінка |
| PATCH | `/admin/directions/{direction_id}` | Змінити напрямок | 🟡 | Адмінка |
| DELETE | `/admin/directions/{direction_id}` | Видалити напрямок | 🟡 | Адмінка |
| PUT | `/admin/disciplines/{discipline_id}/directions` | Прив'язати дисципліну до напрямків (профорієнтовність) | 🟡 | Адмінка |
| PATCH | `/admin/certificate-programs/{program_id}` | Прив'язати програму до напрямків, приховати | 🔵 | Адмінка |
| PUT | `/admin/certificate-programs/{program_id}/courses/{entry_id}` | Вручну звірити дисципліну програми з каталогом | 🔵 | Адмінка |
| GET | `/admin/audit-log` | Журнал доступу і змін | 🟡 | Адмінка |
| GET | `/admin/audit-log/{entry_id}` | Запис журналу з `old_value`/`new_value` | 🟡 | Адмінка |

---

### 3.0. Система

#### `GET /health` ✅

Без автентифікації. Для моніторингу (Uptime Robot). Відповідь `200`:

```json
{ "status": "ok", "version": "1.0.0", "message": "All systems operational" }
```

#### `GET /config` 🟡

Без автентифікації. Фронтенд викликає один раз при старті і бере звідси ліміти й налаштування, а не дублює їх у своєму коді. Значення в §2.2 — ті самі, що повертає ця кінцева точка.

Відповідь `200` (можна кешувати, `Cache-Control: max-age=300`):

```json
{
  "api_version": "1.0.0",
  "google_client_id": "1234567890-abc.apps.googleusercontent.com",
  "allowed_email_domain": "ukma.edu.ua",
  "reviews_url": "https://example.ukma.edu.ua/reviews",
  "limits": {
    "total_credits": 240,
    "free_choice_credits": 25,
    "professional_credits": 54,
    "min_year_credits": 57,
    "max_directions": 3,
    "max_plan_items": 30,
    "max_item_credits": 30,
    "academic_year_min": 2024,
    "academic_year_max": 2030,
    "max_upload_bytes": 10485760
  },
  "load_levels": {
    "low": { "max_hours_per_week": 20 },
    "medium": { "min_hours_per_week": 20, "max_hours_per_week": 23 },
    "high": { "min_hours_per_week": 23, "max_hours_per_week": 25 }
  },
  "features": {
    "ai_generation": false,
    "certificate_programs": false,
    "saz_sync": false,
    "plan_export": true
  }
}
```

`features` вмикає частини UI етапу 2 без нового релізу фронтенду: поки прапорець `false`, фронтенд приховує відповідну кнопку або вкладку. `saz_sync` залишається `false`, доки не вирішено R14.

---

### 3.1. Автентифікація 🟡

Потік: SPA перенаправляє на Google (OAuth2 Authorization Code + PKCE, scopes `openid email profile`, параметр `hd=ukma.edu.ua`). Google повертає `code` на сторінку SPA. SPA надсилає `code` на бекенд. Бекенд перевіряє ID-токен (`iss`, `aud`, `exp`, `email_verified`, точний `hd == "ukma.edu.ua"`), створює або знаходить користувача і повертає access-токен (R6, R7).

Конфігурація, яку бекенд і фронтенд мають узгодити: Google OAuth `client_id` (публічний, потрібен фронтенду), дозволений `redirect_uri`, дозволений origin фронтенду для CORS.

#### `POST /auth/google`

Запит:

```json
{
  "code": "4/0AX4XfWh...",
  "code_verifier": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
  "redirect_uri": "http://localhost:5173/auth/callback"
}
```

Відповідь `200` + `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": { "id": 42, "email": "vl.smyrnov@ukma.edu.ua", "full_name": "Владислав Смирнов", "role": "student" }
}
```

Помилки: `401 UNAUTHORIZED` (невалідний або прострочений `code`), `403 DOMAIN_NOT_ALLOWED` (пошта не з `ukma.edu.ua`), `422`.

Access-токен: живе 15 хв, фронтенд тримає його **лише в пам'яті** (не в `localStorage`, R7).

#### `POST /auth/refresh`

Без тіла, з cookie (`credentials: "include"`). Відповідь `200`: та сама форма, що й `/auth/google`, з новим access-токеном (refresh-токен ротується). Помилка: `401 UNAUTHORIZED` → перейти на сторінку входу. Фронтенд викликає його при старті застосунку (щоб відновити сесію після перезавантаження сторінки) і після 401.

#### `POST /auth/logout`

Без тіла, з cookie. Відкликає refresh-токен, очищає cookie. Відповідь `204`.

---

### 3.2. Профіль студента 🟡

#### `GET /me`

Дані для екрана «Профіль студента» і для логіки конструктора (чи можна створювати план, чи заблоковано вибір навантаження).

Відповідь `200`:

```json
{
  "id": 42,
  "email": "vl.smyrnov@ukma.edu.ua",
  "full_name": "Владислав Смирнов",
  "role": "student",
  "student": {
    "faculty": "ФІ",
    "specialty": "Інженерія програмного забезпечення",
    "course_year": 3,
    "course_year_source": "self_declared",
    "onboarding_required": false,
    "can_create_plan": true,
    "load_levels_mode": "manual",
    "credits": {
      "total_used": 118.5,
      "total_limit": 240,
      "free_choice_used": 9.0,
      "free_choice_limit": 25,
      "professional_used": 27.0,
      "professional_limit": 54
    },
    "saz_synced_at": null
  }
}
```

| Поле | Опис |
|---|---|
| `student` | `null` для адміністратора без студентського профілю |
| `course_year` | `null`, доки студент не пройшов онбординг |
| `course_year_source` | `self_declared` (вказав студент при онбордингу), `admin` (виправив адмін), `saz_sync` (⛔, у майбутньому) |
| `onboarding_required` | `true`, якщо `course_year` або `specialty` ще не заповнені. Фронтенд після входу перенаправляє на екран онбордингу, і поки прапорець `true`, кінцеві точки планів, побажань і генерації повертають `409 ONBOARDING_REQUIRED` |
| `can_create_plan` | `false` для 1 курсу і до онбордингу |
| `load_levels_mode` | `manual` (2–3 курс) або `auto` (4 курс, FR-003) |
| `credits.*_used` | Похідні: сервер рахує з академічної історії (§3.2.2) і планів у статусі `approved`. Клієнт їх ніколи не надсилає (R15). |

Немає `PATCH /me`: після онбордингу `course_year` і `specialty` змінює лише адмін (`PATCH /admin/users/{id}`) або синхронізація (R15).

#### 3.2.1. `POST /me/onboarding`

Одноразове заповнення профілю після першого входу. Потрібне, бо синхронізація з САЗ заблокована (R14), а без курсу система не знає, чи можна створювати план і чи навантаження розраховується автоматично.

Запит:

```json
{ "course_year": 3, "specialty": "Інженерія програмного забезпечення" }
```

| Поле | Обов'язкове | Обмеження |
|---|---|---|
| `course_year` | так | 1–4 |
| `specialty` | так | 2–150 символів |

Відповідь `200`: оновлений об'єкт `GET /me` з `course_year_source: "self_declared"`, `onboarding_required: false`. Помилки: `401`, `409 ALREADY_ONBOARDED` (повторний виклик, змінити може лише адмін), `422`.

Записи `course_year_source = self_declared` бачить адмін і може виправити. Ризик того, що студент вкаже неправильний курс, обмежений: платформа лише планує, а запис і затвердження відбуваються в САЗ і деканаті (та сама логіка, що й у прийнятому ризику R8).

#### 3.2.2. Академічна історія: `/me/academic-history`

Пройдені дисципліни за попередні роки, зокрема 1 курс (план першого курсу формує деканат, але він має з'являтись у вкладці «Індивідуальний план»). Від історії залежать лічильники `/me`, ліміт 25 кредитів вільного вибору за всі роки, перевірка 240 кредитів і вхід AI-генерації (історія власних планів студента, `AGENTS.md` §5).

Модель `AcademicRecord`:

```json
{
  "id": 310,
  "academic_year": 2024,
  "course_year": 1,
  "course_id": 301,
  "title": "Алгоритми та структури даних",
  "trimester": 1,
  "credits": 6.0,
  "category": "normative",
  "source": "self_declared",
  "verified": false,
  "created_at": "2026-10-08T10:00:00Z"
}
```

| Поле | Тип | Опис |
|---|---|---|
| `academic_year` | integer | Рік початку навчального року |
| `course_year` | integer 1–4 | На якому курсі пройдено |
| `course_id` | integer \| null | Дисципліна з каталогу; `null`, якщо її вже немає в каталозі (тоді обов'язкові `title` і `credits`) |
| `category` | `AcademicCategory` | `normative`, `professional`, `free_choice` |
| `source` | `RecordSource` | `self_declared`, `deanery_document`, `approved_plan`, `admin`, `saz_sync` (⛔) |
| `verified` | boolean | Підтверджено адміністратором |

**`GET /me/academic-history`** — query: `academic_year` (необов'язковий). Відповідь `200`, згруповано за роками (для вкладки «Індивідуальний план»), без пагінації:

```json
{
  "years": [
    {
      "academic_year": 2024,
      "course_year": 1,
      "total_credits": 60.0,
      "records": [ { "id": 310, "...": "..." } ]
    }
  ]
}
```

Записи з `source = approved_plan` сервер створює сам, коли план отримує статус `approved`. Записи з `source = deanery_document` — з розпізнаних нормативних дисциплін документа деканату за минулий рік (§3.6).

**`POST /me/academic-history`** — додати кілька записів одним запитом:

```json
{
  "records": [
    { "academic_year": 2024, "course_year": 1, "course_id": 301, "trimester": 1, "category": "normative" },
    { "academic_year": 2025, "course_year": 2, "course_id": null, "title": "Архівний курс", "trimester": 2, "credits": 3.0, "category": "free_choice" }
  ]
}
```

`records`: 1–60. Якщо `course_id` задано, `title` і `credits` береться з каталогу і надіслані значення ігноруються. `course_year` записів не може бути більшим за `course_year` студента. Відповідь `201`: `{ "records": [AcademicRecord, ...] }`. Помилки: `401`, `409 ONBOARDING_REQUIRED`, `422` (напр. дублікат `course_id` в історії, перевищення 25 кредитів `free_choice` сумарно).

**`DELETE /me/academic-history/{record_id}`** — лише записи `source = self_declared` і `verified = false`. Відповідь `204`. Помилки: `401`, `404`, `409 RECORD_NOT_DELETABLE`.

#### 3.2.3. Побажання: `/preferences/{academic_year}`

Зберігає налаштування конструктора на рік (use-case 6, сутність `PlanPreferences`), щоб студент не вводив їх повторно. AI-генерація (§3.7) приймає ті самі поля.

**`GET /preferences/{academic_year}`** — відповідь `200`: `Preferences`; `404 PREFERENCES_NOT_FOUND`, якщо ще не збережено (фронтенд показує порожню форму).

**`PUT /preferences/{academic_year}`** — створює або повністю замінює. Тіло і відповідь `200`:

```json
{
  "academic_year": 2026,
  "load_levels": { "autumn": "low", "spring": "medium", "summer": "medium" },
  "direction_ids": [1, 2],
  "include_free_electives": true,
  "preferred_instructor_ids": [7],
  "unwanted_instructor_ids": [12],
  "wants_certificate": true,
  "certificate_program_id": null,
  "updated_at": "2026-10-08T10:00:00Z"
}
```

| Поле | Обмеження |
|---|---|
| `direction_ids` | 0–3 (FR-007); 4 → 422 з `details[0].field = "direction_ids"` |
| `preferred_instructor_ids`, `unwanted_instructor_ids` | Не перетинаються; id мають існувати |
| `load_levels` | Для 4 курсу ігнорується, у відповіді повертається розраховане значення |

Помилки: `401`, `409 ONBOARDING_REQUIRED`, `422`. Список небажаних викладачів чутливий (R1): він доступний лише власнику і ніколи не передається в LLM.

---

### 3.3. Каталог дисциплін ✅

Усі кінцеві точки вимагають автентифікації.

#### Модель `Discipline` ✅

```json
{
  "id": 101,
  "title": "Функціональне програмування",
  "description": "Основи функціональної парадигми.",
  "discipline_type": "elective",
  "instructor": "Петренко І. М.",
  "recommended_year": 2,
  "trimester": 1,
  "credits": 5.0,
  "directions": ["Software Engineering", "Data Science"]
}
```

| Поле | Тип | Опис |
|---|---|---|
| `id` | integer | ID дисципліни (як у каталозі САЗ); те саме значення, що `PlanItem.course_id` |
| `title` | string | Назва |
| `description` | string | Опис. **Рендерити як текст**, не як HTML (вміст із САЗ недовірений, R7) |
| `discipline_type` | `normative` \| `elective` | Нормативні не можна додавати в план |
| `instructor` | string | ПІБ викладача |
| `recommended_year` | integer 1–4 | |
| `trimester` | integer 1–3 | |
| `credits` | number > 0 | |
| `directions` | string[] | Напрямки, для яких дисципліна профорієнтовна. **Порожній масив = дисципліна вільного вибору** для всіх |

**Як фронтенд визначає `is_free_elective` при додаванні в план:** з поля `category_for_me` (нижче). Поки його немає (✅-заглушка), дисципліна вважається вільним вибором, якщо жоден із напрямків студента не входить у `directions` (порівняння без урахування регістру). Остаточно це перевіряє сервер.

Сумісні розширення 🟡 (додаються без нової версії; поле `instructor` залишається):

| Поле | Тип | Опис |
|---|---|---|
| `instructors` | `{ id, full_name }[]` | Потрібно для фільтра небажаних викладачів за id |
| `category_for_me` | `normative` \| `professional` \| `free_choice` | Категорія **для поточного студента**: `professional`, якщо дисципліна профорієнтовна для його спеціальності або обраних напрямків (§3.2.3); інакше `free_choice`. Рахує сервер |
| `already_taken` | boolean | Дисципліна вже є в академічній історії студента (§3.2.2) або в документі деканату на цей рік. Конструктор показує її неактивною |
| `certificate_program_ids` | integer[] | 🔵 Програми, до яких входить дисципліна (підказка «входить у сертифікат X») |

Сумісні query-параметри 🟡 для `GET /disciplines`: `category_for_me` (фільтр за категорією), `exclude_taken=true`.

#### `GET /disciplines` ✅

Query-параметри (усі необов'язкові, комбінуються через AND):

| Параметр | Тип | Обмеження | Поведінка |
|---|---|---|---|
| `limit`, `offset` | integer | §1.5 | |
| `direction` | string | 2–50 символів | Точний збіг з одним із `directions`, без урахування регістру |
| `trimester` | integer | 1–3 | |
| `instructor` | string | 2–100 символів | Підрядок у `instructor`, без урахування регістру |
| `min_credits` | number | ≥ 0 | `credits >= min_credits` |
| `max_credits` | number | ≥ 0 | `credits <= max_credits`; якщо `min_credits > max_credits` → 422, `details[0].field = "min_credits"` |
| `recommended_year` | integer | 1–4 | |
| `discipline_type` | `normative` \| `elective` | | Для каталогу вибіркових фронтенд передає `elective` |

Сумісні розширення 🟡: `q` (пошук за назвою, debounce на фронтенді), `exclude_instructor_ids` (масив, для конструктора).

Приклад: `GET /api/v1/disciplines?direction=Data%20Science&trimester=1&limit=20&offset=0`

Відповідь `200`:

```json
{
  "disciplines": [ { "id": 101, "title": "Функціональне програмування", "...": "..." } ],
  "pagination": { "limit": 20, "offset": 0, "total": 1, "has_more": false }
}
```

Помилки: `401`, `422`.

#### `GET /disciplines/{discipline_id}` ✅

`discipline_id`: integer > 0. Відповідь `200`: об'єкт `Discipline`. Помилки: `401`, `404 DISCIPLINE_NOT_FOUND`, `422` (напр. `discipline_id = 0`).

---

### 3.4. Індивідуальні плани

Розподіл по вкладках «Науковий шлях» (фронтенд використовує фільтр `status`):

| Вкладка | Запит |
|---|---|
| Індивідуальний план (затверджені за всі роки) | `GET /plans?status=approved` |
| Збережені плани | `GET /plans?status=draft` (і окремо `submitted` / `awaiting_deanery`, якщо їх показувати там же) |
| Створити план | `POST /plans`, `PUT /plans/{id}`, `POST /plans/validate`, `POST /plan-generations` |

#### Модель `PlanItem` ✅ (запит і відповідь)

```json
{
  "course_id": 101,
  "title": "Функціональне програмування",
  "trimester": 1,
  "credits": 5.0,
  "is_free_elective": false
}
```

| Поле | Тип | Обов'язкове | Обмеження |
|---|---|---|---|
| `course_id` | integer | так | `Discipline.id`; унікальне в межах плану |
| `title` | string | так | 2–150 символів |
| `trimester` | integer | так | 1–3 |
| `credits` | number | так | > 0 і ≤ 30 |
| `is_free_elective` | boolean | ні, `false` | |

Зараз (✅) фронтенд надсилає `title`, `credits`, `is_free_elective`, копіюючи їх з `Discipline`. 🟡 Коли з'явиться БД, сервер перевіряє їх за каталогом (розбіжність → 422) і сам визначає `is_free_elective`. Поля залишаються в запиті для сумісності.

Сумісні розширення у **відповіді** 🔵 (лише для AI-планів):

```json
{
  "course_id": 101,
  "...": "...",
  "ai_explanation": "Дає основу для курсів напрямку Data Science.",
  "alternatives": [
    { "course_id": 118, "title": "Мова Haskell", "trimester": 1, "credits": 5.0, "is_free_elective": false, "rank": 1, "ai_explanation": "..." }
  ]
}
```

Заміна дисципліни на альтернативу (US-006): фронтенд підставляє альтернативу в `items` і викликає `PUT /plans/{id}`. Ліміти (зокрема 25 кредитів вільного вибору, FR-010) перевіряються тим самим PUT. Окремої кінцевої точки для заміни немає.

#### Модель `LoadLevels` ✅

```json
{ "autumn": "medium", "spring": "high", "summer": "low" }
```

Кожен ключ необов'язковий у запиті, за замовчуванням `medium`. Для 4 курсу див. §2.3.

#### Модель `PlanResponse` ✅

```json
{
  "id": 1,
  "student_id": 42,
  "academic_year": 2026,
  "course": 2,
  "load_levels": { "autumn": "medium", "spring": "high", "summer": "low" },
  "items": [
    { "course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0, "is_free_elective": false }
  ],
  "status": "draft",
  "total_credits": 5.0,
  "free_elective_credits": 0.0,
  "created_at": "2026-10-08T10:00:00Z"
}
```

| Поле | Тип | Опис |
|---|---|---|
| `id` | integer | |
| `student_id` | integer | Власник (з токена) |
| `academic_year` | integer | **Рік початку** навчального року: `2026` означає 2026/2027 |
| `course` | integer 2–4 | |
| `load_levels` | `LoadLevels` | |
| `items` | `PlanItem[]` | Лише вибіркові дисципліни |
| `status` | `PlanStatus` | |
| `total_credits` | number | Сума `items[].credits`, рахує сервер |
| `free_elective_credits` | number | Сума кредитів з `is_free_elective = true`, рахує сервер |
| `created_at` | datetime | |

Сумісні розширення 🟡 (додаються у відповідь без нової версії):

| Поле | Тип | Опис |
|---|---|---|
| `title` | string | Назва плану, напр. «План на 2026/2027 (варіант 2)». Необов'язкове і в запиті |
| `origin` | `PlanOrigin` | Як створено план |
| `updated_at` | datetime | |
| `load_levels_mode` | `manual` \| `auto` | `auto` для 4 курсу |
| `deanery_document_id` | integer \| null | Документ деканату, з яким звірено план. Необов'язкове і в запиті |
| `normative_items` | `NormativeCourse[]` | Нормативні дисципліни на цей рік з документа деканату, **лише для читання** (§3.6) |
| `year_total_credits` | number | `total_credits` + кредити нормативних |
| `credits_by_trimester` | `{ "1": number, "2": number, "3": number }` | Вибіркові + нормативні по триместрах, для індикатора навантаження |
| `warnings` | `Warning[]` | Попередження (§2.4) |
| `reviews_url` | string | Посилання «Почитати відгуки» на зовнішню платформу (`AGENTS.md` §4) |

#### `POST /plans` ✅

Створює чернетку. Тіло `CreatePlanRequest`:

```json
{
  "academic_year": 2026,
  "course": 2,
  "load_levels": { "autumn": "medium", "spring": "medium", "summer": "medium" },
  "items": [
    { "course_id": 101, "title": "Функціональне програмування", "trimester": 1, "credits": 5.0 },
    { "course_id": 205, "title": "Управління цифровим продуктом", "trimester": 2, "credits": 3.0, "is_free_elective": true }
  ]
}
```

| Поле | Тип | Обов'язкове | Обмеження |
|---|---|---|---|
| `academic_year` | integer | так | 2024–2030 |
| `course` | integer | так | 2–4 |
| `load_levels` | `LoadLevels` | ні | За замовчуванням усі `medium` |
| `items` | `PlanItem[]` | так | 1–30 елементів; правила з §2.4 |

Відповідь `201` + `PlanResponse` зі `status: "draft"` (🟡 + заголовок `Location: /api/v1/plans/{id}`). Помилки: `401`, `422`.

Приклад 422 (ліміт вільного вибору):

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Невалідні вхідні дані",
  "details": [ { "field": "body", "message": "Value error, Перевищено ліміт вільного вибору: 28.0 > 25 кредитів" } ]
}
```

#### `GET /plans` ✅

Query-параметри: `limit`, `offset` (§1.5), `status` (`PlanStatus`), `academic_year` (2024–2030).

Відповідь `200`:

```json
{
  "plans": [ { "id": 1, "status": "draft", "...": "..." } ],
  "pagination": { "limit": 20, "offset": 0, "total": 2, "has_more": false }
}
```

Повертаються лише плани поточного студента. Порядок 🟡: `created_at` за спаданням (зараз — порядок заглушки). Помилки: `401`, `422`.

#### `GET /plans/{plan_id}` ✅

Відповідь `200`: `PlanResponse`. Помилки: `401`, `403 PLAN_FORBIDDEN`, `404 PLAN_NOT_FOUND`, `422`.

#### `PUT /plans/{plan_id}` ✅

**Повна заміна** плану: тіло — той самий `CreatePlanRequest`, що для POST. Фронтенд надсилає весь план, не лише змінені поля. Дозволено лише для `draft`.

Відповідь `200`: оновлений `PlanResponse`. Помилки: `401`, `403`, `404`, `409 PLAN_NOT_EDITABLE`, `422`.

#### `DELETE /plans/{plan_id}` ✅

Лише для `draft`. Відповідь `204` без тіла. Помилки: `401`, `403`, `404`, `409 PLAN_NOT_DELETABLE`, `422`.

#### `POST /plans/validate` 🟡

Перевіряє план **без збереження**: для живих попереджень у конструкторі (індикатор кредитів, попередження про низьке навантаження) без створення чернетки на кожну дію. Тіло: `CreatePlanRequest`.

Відповідь `200` (завжди 200, якщо тіло синтаксично коректне; порушення правил повертаються в `errors`):

```json
{
  "valid": false,
  "errors": [
    { "code": "FREE_ELECTIVE_LIMIT_EXCEEDED", "message": "Перевищено ліміт вільного вибору: 28.0 > 25 кредитів", "field": null }
  ],
  "warnings": [
    { "code": "LOW_LOAD_FUTURE_INCREASE", "message": "Обрано низьке навантаження: навантаження наступних років зросте" }
  ],
  "summary": {
    "total_credits": 31.0,
    "free_elective_credits": 28.0,
    "free_elective_used_all_years": 9.0,
    "free_elective_remaining": 16.0,
    "year_total_credits": 58.0,
    "credits_by_trimester": { "1": 20.0, "2": 22.0, "3": 16.0 }
  }
}
```

Коди `errors`: `DUPLICATE_COURSE`, `ONLY_FREE_ELECTIVES`, `FREE_ELECTIVE_LIMIT_EXCEEDED`, `NORMATIVE_CONFLICT`, `NORMATIVE_NOT_ALLOWED`, `COURSE_NOT_FOUND`, `COURSE_DATA_MISMATCH`, `YEAR_CREDITS_BELOW_MIN`. Помилки HTTP: `401`, `422` (лише якщо тіло не відповідає схемі, напр. `trimester: 5`).

#### `POST /plans/{plan_id}/submit` 🟡

Перехід `draft` → `submitted` (запланований у `api-design.md`). Без тіла. Перевіряє всі правила з колонки «Подання» §2.4.

Відповідь `200`: `PlanResponse` зі `status: "submitted"`. Помилки: `401`, `403`/`404`, `409 PLAN_NOT_SUBMITTABLE`, `422 PLAN_VALIDATION_FAILED` (порушення в `details`).

Подальші переходи `submitted` → `awaiting_deanery` → `approved` робить не студент: їх ставить синхронізація з САЗ (⛔, див. нижче). Фронтенд лише відображає ці статуси.

#### `GET /plans/{plan_id}/export` 🟡

Фіксація і експорт плану (use-case 16). Query: `format=pdf` (поки єдине значення). Відповідь `200`, `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="plan-2026.pdf"`. PDF містить вибіркові й нормативні дисципліни по триместрах, кредити, рівні навантаження і посилання «Почитати відгуки» (`reviews_url`). Фронтенд завантажує файл через `fetch` з `Authorization` і зберігає як blob (простий `<a href>` не надішле Bearer-токен).

Помилки: `401`, `403`/`404`, `422` (невідомий `format`). Доступний для плану в будь-якому статусі.

Якщо команда вирішить, що достатньо друку зі сторінки браузера, кінцеву точку не реалізовують, а `features.plan_export = false` (§3.0).

#### `POST /plans/sync-saz` ⛔

Кнопка «Оновити» (підтягнути затверджений деканатом план із САЗ). **Не реалізовувати**: відкрите питання R14 (як отримати дані САЗ без зберігання облікових даних студента). Фронтенд показує кнопку неактивною або приховує її.

---

### 3.5. Довідники 🟡

#### `GET /directions`

Відповідь `200`, без пагінації:

```json
{
  "directions": [
    { "id": 1, "name": "Data Science", "description": "..." },
    { "id": 2, "name": "Cybersecurity", "description": null }
  ]
}
```

`name` — те саме значення, що в `Discipline.directions` і фільтрі `GET /disciplines?direction=`.

#### `GET /instructors`

Для вибору бажаних і небажаних викладачів (US-003) і фільтра каталогу. Query: `q` (підрядок ПІБ, ≥ 2 символи), `limit`, `offset`.

```json
{
  "instructors": [ { "id": 7, "full_name": "Петренко І. М." } ],
  "pagination": { "limit": 20, "offset": 0, "total": 1, "has_more": false }
}
```

---

### 3.6. Документ деканату 🟡

Перед побудовою плану на рік студент завантажує документ деканату з нормативними дисциплінами (use-case 3). Сервер розпізнає їх у фоні.

#### `POST /deanery-documents`

`Content-Type: multipart/form-data`:

| Частина | Тип | Обов'язкова | Обмеження |
|---|---|---|---|
| `file` | файл | так | PDF або DOCX (перевірка за вмістом), ≤ 10 МБ |
| `academic_year` | integer | так | 2024–2030 |

Відповідь `202` (розпізнавання асинхронне) + `Location: /api/v1/deanery-documents/{id}`:

```json
{
  "id": 15,
  "academic_year": 2026,
  "original_filename": "plan_2026.pdf",
  "mime_type": "pdf",
  "size_bytes": 184233,
  "parse_status": "pending",
  "parse_error": null,
  "uploaded_at": "2026-10-08T10:00:00Z",
  "normative_courses": []
}
```

Помилки: `401`, `413 FILE_TOO_LARGE`, `415 UNSUPPORTED_FILE_TYPE`, `422`, `429 RATE_LIMITED`.

Фронтенд опитує `GET /deanery-documents/{id}` кожні 2 с, доки `parse_status` не стане `parsed` або `failed`.

#### `GET /deanery-documents`

Query: `academic_year` (необов'язковий). Відповідь `200`: `{ "deanery_documents": [ DeaneryDocument, ... ] }` (без пагінації: кілька документів на студента). Лише документи поточного студента.

#### `GET /deanery-documents/{document_id}`

Відповідь `200`: `DeaneryDocument`, де після розпізнавання заповнено `normative_courses`:

```json
{
  "id": 15,
  "academic_year": 2026,
  "parse_status": "parsed",
  "...": "...",
  "normative_courses": [
    { "course_id": 301, "raw_title": "Алгоритми та структури даних", "trimester": 1, "credits": 6.0 },
    { "course_id": null, "raw_title": "Фізичне виховання", "trimester": 2, "credits": 2.0 }
  ]
}
```

`NormativeCourse.course_id = null`, якщо дисципліни не знайдено в каталозі. Ці дисципліни **лише для читання**: фронтенд показує їх у конструкторі поруч із вибірковими, але не дає редагувати.

Помилки: `401`, `404 DOCUMENT_NOT_FOUND` (і для чужого документа).

**Документ за минулий рік:** якщо `academic_year` документа менший за поточний навчальний рік, після розпізнавання сервер додає його нормативні дисципліни в академічну історію з `source: "deanery_document"` (§3.2.2). Так студент заповнює історію 1 курсу без ручного введення.

#### `GET /deanery-documents/{document_id}/file`

Повертає завантажений файл власнику: `200`, `Content-Type` = `application/pdf` або `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `Content-Disposition: attachment`. Помилки: `401`, `404 DOCUMENT_NOT_FOUND`. Чужий документ → 404 (R3).

#### `DELETE /deanery-documents/{document_id}`

Відповідь `204`. Помилки: `401`, `404`, `409 DOCUMENT_IN_USE` (документ прив'язаний до плану не в статусі `draft`). Записи історії з цього документа видаляються разом із ним.

---

### 3.7. AI-генерація плану 🔵

Генерація триває до 5 хв (PERF-001), тому вона **асинхронна** (рекомендація threat model R10): запит повертає `202`, фронтенд опитує статус і показує skeleton-завантажувач.

#### `POST /plan-generations`

Тіло — побажання студента (use-case 6):

```json
{
  "academic_year": 2026,
  "course": 3,
  "load_levels": { "autumn": "low", "spring": "medium", "summer": "medium" },
  "direction_ids": [1, 2],
  "include_free_electives": true,
  "preferred_instructor_ids": [7],
  "unwanted_instructor_ids": [12],
  "wants_certificate": true,
  "certificate_program_id": null,
  "deanery_document_id": 15
}
```

| Поле | Обов'язкове | Обмеження |
|---|---|---|
| `academic_year`, `course` | так | Як у `CreatePlanRequest` |
| `load_levels` | ні | Ігнорується для 4 курсу |
| `direction_ids` | так | **1–3** елементи (FR-007); 4 → 422 |
| `include_free_electives` | ні, `true` | `false` = лише профорієнтовні |
| `preferred_instructor_ids`, `unwanted_instructor_ids` | ні | Списки не перетинаються |
| `wants_certificate` | ні, `false` | |
| `certificate_program_id` | ні | Конкретна програма, якщо обрана |
| `deanery_document_id` | ні | Документ у статусі `parsed` для цього року |

Тіло збігається з `Preferences` (§3.2.3) плюс `course` і `deanery_document_id`. Фронтенд перед генерацією зберігає побажання через `PUT /preferences/{academic_year}`, щоб вони не загубились, якщо генерація не вдасться.

Відповідь `202` + `Location: /api/v1/plan-generations/{id}`:

```json
{ "id": 77, "status": "pending", "plan_id": null, "notices": [], "error": null, "created_at": "2026-10-08T10:00:00Z", "finished_at": null }
```

Помилки: `401`, `409 COURSE_NOT_ELIGIBLE`, `422`, `429 GENERATION_IN_PROGRESS` / `RATE_LIMITED`.

#### `GET /plan-generations/{generation_id}`

Фронтенд опитує кожні 3 с. Відповідь `200`:

```json
{
  "id": 77,
  "status": "succeeded",
  "plan_id": 9,
  "notices": [
    { "code": "UNWANTED_INSTRUCTOR_UNAVOIDABLE", "message": "Дисципліну X за напрямком Data Science викладає лише обраний вами небажаний викладач", "course_id": 140 }
  ],
  "error": null,
  "created_at": "2026-10-08T10:00:00Z",
  "finished_at": "2026-10-08T10:01:12Z"
}
```

- `succeeded`: план збережено як `draft` з `origin: "ai_generated"`. Фронтенд завантажує `GET /plans/{plan_id}` (з `ai_explanation` і `alternatives` у `items`).
- `failed`: `error` має форму `ErrorResponse` (напр. `AI_UNAVAILABLE`). Конструктор далі працює вручну, без AI (R11).
- `notices`: повідомлення для студента, напр. про неможливість уникнути небажаного викладача (FR-006).

---

### 3.8. Сертифікатні програми 🔵

#### `GET /certificate-programs`

Query: `direction_id`, `availability` (необов'язкові). Програми, які адмін приховав (`hidden: true`), студентам не повертаються. Відповідь `200` без пагінації:

```json
{
  "certificate_programs": [
    { "id": 3, "title": "Data Engineering", "source_url": "https://...", "availability": "available", "direction_ids": [1], "course_count": 4 }
  ]
}
```

#### `GET /certificate-programs/{program_id}`

```json
{
  "id": 3,
  "title": "Data Engineering",
  "source_url": "https://...",
  "availability": "unavailable_this_year",
  "direction_ids": [1],
  "courses": [
    { "raw_title": "Бази даних", "course_id": 120, "match_status": "matched" },
    { "raw_title": "Хмарні обчислення", "course_id": null, "match_status": "not_found" }
  ]
}
```

Програма `unavailable_this_year`, якщо хоча б одна дисципліна має `match_status: "not_found"`. Звірка назв без урахування регістру — на сервері.

---

### 3.9. Адміністрування 🟡

Усі кінцеві точки `/admin/*` вимагають `role = admin`. Студент отримує `403 FORBIDDEN_ROLE` (R2). Фронтенд приховує адмінку за `GET /me → role`, але це лише UI, не захист.

#### `POST /admin/sync-jobs`

Запускає парсинг (FR-008). Тіло:

```json
{ "source": "saz_catalog" }
```

Відповідь `202` + `Location`: об'єкт `SyncJob` зі `status: "queued"`. Помилки: `401`, `403`, `409 SYNC_JOB_ALREADY_RUNNING`, `422`.

#### `GET /admin/sync-jobs`

Журнал (FR-011). Query: `limit`, `offset`, `source`, `status`. Сортування: `started_at` за спаданням.

```json
{
  "sync_jobs": [
    {
      "id": 31,
      "source": "saz_catalog",
      "initiator": "admin",
      "initiated_by": { "id": 1, "full_name": "Адміністратор" },
      "status": "failed",
      "started_at": "2026-10-08T09:00:00Z",
      "finished_at": "2026-10-08T09:04:10Z",
      "added_count": 0,
      "updated_count": 0,
      "error_message": "Не вдалося знайти таблицю дисциплін на сторінці САЗ"
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 1, "has_more": false }
}
```

`initiated_by` = `null`, якщо `initiator = "scheduler"`.

#### `GET /admin/sync-jobs/{job_id}`

Відповідь `200`: `SyncJob` (сирий HTML `raw_snapshot` в API не повертається). Фронтенд опитує, доки `status` = `queued` або `running`.

#### `GET /admin/moderation-items`

Query: `limit`, `offset`, `status` (за замовчуванням `pending`), `sync_job_id`, `change_type`.

```json
{
  "moderation_items": [
    {
      "id": 501,
      "sync_job_id": 31,
      "course_id": 101,
      "change_type": "update",
      "payload": { "title": "Функціональне програмування", "credits": 4.0, "trimester": 1 },
      "diff": { "credits": { "old": 5.0, "new": 4.0 } },
      "status": "pending",
      "reviewed_by": null,
      "reviewed_at": null
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 1, "has_more": false }
}
```

`course_id` = `null` для `change_type = "add"`. `diff` = `null` для `add`. Адмінка рендерить `payload` і `diff` як текст (R5, R7).

#### `POST /admin/moderation-items/{item_id}/approve` і `/reject`

Без тіла (для `reject` необов'язково `{ "reason": "..." }`). Відповідь `200`: оновлений `ModerationItem`. Помилки: `401`, `403`, `404`, `409 MODERATION_ITEM_ALREADY_REVIEWED`.

#### `POST /admin/moderation-items/bulk-review`

```json
{ "item_ids": [501, 502, 503], "decision": "approve" }
```

`decision`: `approve` | `reject`; `item_ids`: 1–100. Відповідь `200`:

```json
{ "approved": [501, 502], "rejected": [], "skipped": [ { "id": 503, "code": "MODERATION_ITEM_ALREADY_REVIEWED" } ] }
```

#### Користувачі: `/admin/users`

**`GET /admin/users`** — query: `limit`, `offset`, `q` (підрядок email або ПІБ), `role`, `course_year`, `course_year_source`, `onboarding_required`. Відповідь `200`:

```json
{
  "users": [
    {
      "id": 42,
      "email": "vl.smyrnov@ukma.edu.ua",
      "full_name": "Владислав Смирнов",
      "role": "student",
      "created_at": "2026-09-01T08:00:00Z",
      "last_login_at": "2026-10-08T09:55:00Z",
      "student": { "specialty": "Інженерія програмного забезпечення", "course_year": 3, "course_year_source": "self_declared" }
    }
  ],
  "pagination": { "limit": 20, "offset": 0, "total": 1, "has_more": false }
}
```

**`GET /admin/users/{user_id}`** — той самий об'єкт, де `student` має повну форму з `GET /me` (з лічильниками кредитів). Плани студента адмін **не бачить** через цю кінцеву точку: доступ до планів лише у власника (SEC-001).

**`PATCH /admin/users/{user_id}`** — часткове оновлення, усі поля необов'язкові:

```json
{ "role": "admin", "student": { "course_year": 4, "specialty": "Комп'ютерні науки" } }
```

Зміна `course_year` або `specialty` ставить `course_year_source: "admin"`. Відповідь `200`: оновлений користувач. Помилки: `401`, `403 FORBIDDEN_ROLE`, `404 USER_NOT_FOUND`, `409 CANNOT_CHANGE_OWN_ROLE` (адмін не може зняти роль сам із себе, щоб не залишити систему без адміністратора), `422`. Кожна зміна пишеться в `AuditLog`.

**Перший адміністратор** не створюється через API: бекенд при вході користувача з email зі змінної оточення `INITIAL_ADMIN_EMAILS` призначає йому роль `admin`. Далі ролі змінюються лише через `PATCH`.

#### Академічна історія студента

**`GET /admin/users/{user_id}/academic-history`** — та сама форма, що `GET /me/academic-history`.

**`POST /admin/users/{user_id}/academic-history/verify`** — підтвердити записи `self_declared`:

```json
{ "record_ids": [310, 311] }
```

Відповідь `200`: `{ "verified": [310, 311], "skipped": [] }`. Помилки: `401`, `403`, `404`, `422`.

#### Напрямки: `/admin/directions`

**`POST /admin/directions`** — тіло `{ "name": "Data Science", "description": "..." }`; `name` 2–50 символів, унікальне без урахування регістру. Відповідь `201`: `Direction`. Помилки: `401`, `403`, `409 DIRECTION_NAME_TAKEN`, `422`.

**`PATCH /admin/directions/{direction_id}`** — `name` і/або `description`. Відповідь `200`. Помилки: як для POST + `404 DIRECTION_NOT_FOUND`.

**`DELETE /admin/directions/{direction_id}`** — відповідь `204`. Помилки: `401`, `403`, `404`, `409 DIRECTION_IN_USE` (прив'язаний до дисциплін, сертифікатних програм або збережених побажань; спершу відв'язати).

#### Профорієнтовність дисципліни

**`PUT /admin/disciplines/{discipline_id}/directions`** — повністю замінює перелік напрямків, для яких дисципліна профорієнтовна:

```json
{ "direction_ids": [1, 3] }
```

Порожній масив робить дисципліну вільним вибором для всіх. Відповідь `200`: оновлений `Discipline`. Помилки: `401`, `403`, `404 DISCIPLINE_NOT_FOUND`, `422` (неіснуючий id напрямку). Зміна пишеться в `AuditLog`.

Це ручне налаштування, бо САЗ, імовірно, не публікує прив'язку до напрямків. Інші поля дисципліни (назва, кредити, триместр) адмін не редагує напряму: вони змінюються лише через чергу модерації (ADR-002).

#### Сертифікатні програми 🔵

**`PATCH /admin/certificate-programs/{program_id}`** — тіло `{ "direction_ids": [1], "hidden": false }`. `hidden: true` приховує програму від студентів. Відповідь `200`: `CertificateProgram`.

**`PUT /admin/certificate-programs/{program_id}/courses/{entry_id}`** — ручна звірка, коли автоматичне порівняння назв не знайшло збіг:

```json
{ "course_id": 120 }
```

`course_id: null` скасовує ручну звірку. Сервер перераховує `availability` програми. Відповідь `200`: програма з `courses`. Помилки: `401`, `403`, `404`, `422`.

#### Журнал аудиту: `GET /admin/audit-log`

Лише читання (журнал append-only, SEC-001). Query: `limit`, `offset`, `actor_id`, `action` (напр. `plan.read`, `user.update`, `moderation.approve`), `object_type`, `object_id`, `outcome` (`allowed` | `denied`), `from`, `to` (datetime). Сортування: `created_at` за спаданням.

```json
{
  "audit_log": [
    {
      "id": 9001,
      "actor": { "id": 42, "full_name": "Владислав Смирнов" },
      "action": "plan.read",
      "object_type": "IndividualPlan",
      "object_id": 3,
      "outcome": "denied",
      "ip": "10.0.0.15",
      "created_at": "2026-10-08T10:00:00Z"
    }
  ],
  "pagination": { "limit": 50, "offset": 0, "total": 1, "has_more": false }
}
```

`old_value`/`new_value` у списку не повертаються (містять PII); їх показує `GET /admin/audit-log/{id}`. `actor` = `null` для анонімних спроб.

---

## 4. Типи TypeScript для фронтенду

Типи відповідають схемам вище. Для ✅-моделей їх можна згенерувати з `docs/api/openapi-generated.json` (напр. `openapi-typescript`), щоб не підтримувати вручну; нижче — довідкова версія.

```ts
// ---------- Спільні ----------
export interface ErrorDetail { field: string; message: string }
export interface ErrorResponse { code: string; message: string; details: ErrorDetail[] }
export interface PaginationInfo { limit: number; offset: number; total: number; has_more: boolean }
export interface PageParams { limit?: number; offset?: number }
export interface Warning { code: string; message: string }

export type Trimester = 1 | 2 | 3;                         // 1 осінь, 2 весна, 3 літо
export type LoadLevel = "low" | "medium" | "high";
export interface LoadLevels { autumn: LoadLevel; spring: LoadLevel; summer: LoadLevel }

// ---------- Дисципліни (✅) ----------
export type DisciplineType = "normative" | "elective";
export interface Discipline {
  id: number;
  title: string;
  description: string;
  discipline_type: DisciplineType;
  instructor: string;
  recommended_year: 1 | 2 | 3 | 4;
  trimester: Trimester;
  credits: number;
  directions: string[];                                   // [] = вільний вибір
  // 🟡 сумісні розширення
  instructors?: Instructor[];
  category_for_me?: AcademicCategory;
  already_taken?: boolean;
  certificate_program_ids?: number[];                     // 🔵
}
export interface DisciplineFilters extends PageParams {
  direction?: string;
  trimester?: Trimester;
  instructor?: string;
  min_credits?: number;
  max_credits?: number;
  recommended_year?: 1 | 2 | 3 | 4;
  discipline_type?: DisciplineType;
}
export interface PaginatedDisciplines { disciplines: Discipline[]; pagination: PaginationInfo }

// ---------- Плани (✅ + 🟡/🔵 необов'язкові поля) ----------
export type PlanStatus = "draft" | "submitted" | "awaiting_deanery" | "approved";
export interface PlanItem {
  course_id: number;
  title: string;
  trimester: Trimester;
  credits: number;
  is_free_elective?: boolean;                             // за замовчуванням false
}
export interface PlanAlternative extends PlanItem { rank: 1 | 2 | 3; ai_explanation?: string | null }   // 🔵
export interface PlanItemResponse extends PlanItem {
  is_free_elective: boolean;
  ai_explanation?: string | null;                         // 🔵
  alternatives?: PlanAlternative[];                       // 🔵
}
export interface CreatePlanRequest {
  academic_year: number;                                  // 2024–2030, рік початку
  course: 2 | 3 | 4;
  load_levels?: Partial<LoadLevels>;
  items: PlanItem[];                                      // 1–30
  title?: string;                                         // 🟡
  deanery_document_id?: number | null;                    // 🟡
}
export interface NormativeCourse { course_id: number | null; raw_title: string; trimester: Trimester; credits: number }
export interface PlanResponse {
  id: number;
  student_id: number;
  academic_year: number;
  course: 2 | 3 | 4;
  load_levels: LoadLevels;
  items: PlanItemResponse[];
  status: PlanStatus;
  total_credits: number;
  free_elective_credits: number;
  created_at: string;
  // 🟡 сумісні розширення
  title?: string;
  origin?: "manual" | "ai_generated" | "saz_sync";
  updated_at?: string;
  load_levels_mode?: "manual" | "auto";
  deanery_document_id?: number | null;
  normative_items?: NormativeCourse[];
  year_total_credits?: number;
  credits_by_trimester?: Record<"1" | "2" | "3", number>;
  warnings?: Warning[];
  reviews_url?: string;
}
export interface PlanFilters extends PageParams { status?: PlanStatus; academic_year?: number }
export interface PaginatedPlans { plans: PlanResponse[]; pagination: PaginationInfo }
export interface PlanValidationResult {                   // 🟡
  valid: boolean;
  errors: (Warning & { field: string | null })[];
  warnings: Warning[];
  summary: {
    total_credits: number;
    free_elective_credits: number;
    free_elective_used_all_years: number;
    free_elective_remaining: number;
    year_total_credits: number;
    credits_by_trimester: Record<"1" | "2" | "3", number>;
  };
}

// ---------- Auth і профіль (🟡) ----------
export interface AuthUser { id: number; email: string; full_name: string; role: "student" | "admin" }
export interface TokenResponse { access_token: string; token_type: "Bearer"; expires_in: number; user: AuthUser }
export interface Me extends AuthUser {
  student: null | {
    faculty: string;
    specialty: string | null;
    course_year: 1 | 2 | 3 | 4 | null;                    // null до онбордингу
    course_year_source: CourseYearSource | null;
    onboarding_required: boolean;
    can_create_plan: boolean;
    load_levels_mode: "manual" | "auto";
    credits: {
      total_used: number; total_limit: number;
      free_choice_used: number; free_choice_limit: number;
      professional_used: number; professional_limit: number;
    };
    saz_synced_at: string | null;
  };
}
export type CourseYearSource = "self_declared" | "admin" | "saz_sync";
export interface OnboardingRequest { course_year: 1 | 2 | 3 | 4; specialty: string }

// ---------- Конфігурація (🟡) ----------
export interface AppConfig {
  api_version: string;
  google_client_id: string;
  allowed_email_domain: string;
  reviews_url: string;
  limits: {
    total_credits: number; free_choice_credits: number; professional_credits: number;
    min_year_credits: number; max_directions: number; max_plan_items: number; max_item_credits: number;
    academic_year_min: number; academic_year_max: number; max_upload_bytes: number;
  };
  load_levels: Record<LoadLevel, { min_hours_per_week?: number; max_hours_per_week?: number }>;
  features: { ai_generation: boolean; certificate_programs: boolean; saz_sync: boolean; plan_export: boolean };
}

// ---------- Академічна історія і побажання (🟡) ----------
export type AcademicCategory = "normative" | "professional" | "free_choice";
export type RecordSource = "self_declared" | "deanery_document" | "approved_plan" | "admin" | "saz_sync";
export interface AcademicRecord {
  id: number; academic_year: number; course_year: 1 | 2 | 3 | 4;
  course_id: number | null; title: string; trimester: Trimester; credits: number;
  category: AcademicCategory; source: RecordSource; verified: boolean; created_at: string;
}
export interface AcademicRecordInput {
  academic_year: number; course_year: 1 | 2 | 3 | 4; course_id: number | null;
  title?: string; trimester: Trimester; credits?: number; category: AcademicCategory;
}
export interface AcademicHistory {
  years: { academic_year: number; course_year: 1 | 2 | 3 | 4; total_credits: number; records: AcademicRecord[] }[];
}
export interface Preferences {
  academic_year: number;
  load_levels: LoadLevels;
  direction_ids: number[];                                // 0–3
  include_free_electives: boolean;
  preferred_instructor_ids: number[];
  unwanted_instructor_ids: number[];
  wants_certificate: boolean;
  certificate_program_id: number | null;
  updated_at?: string;                                    // лише у відповіді
}

// ---------- Довідники, документи, AI, сертифікати, адмінка ----------
export interface Direction { id: number; name: string; description: string | null }
export interface Instructor { id: number; full_name: string }
export interface DeaneryDocument {
  id: number; academic_year: number; original_filename: string; mime_type: "pdf" | "docx";
  size_bytes: number; parse_status: "pending" | "parsed" | "failed"; parse_error: string | null;
  uploaded_at: string; normative_courses: NormativeCourse[];
}
export interface PlanGenerationRequest {                  // 🔵
  academic_year: number; course: 2 | 3 | 4; load_levels?: Partial<LoadLevels>;
  direction_ids: number[];                                // 1–3
  include_free_electives?: boolean;
  preferred_instructor_ids?: number[]; unwanted_instructor_ids?: number[];
  wants_certificate?: boolean; certificate_program_id?: number | null;
  deanery_document_id?: number | null;
}
export interface PlanGeneration {                         // 🔵
  id: number; status: "pending" | "succeeded" | "failed"; plan_id: number | null;
  notices: (Warning & { course_id?: number })[]; error: ErrorResponse | null;
  created_at: string; finished_at: string | null;
}
export interface CertificateProgram {                     // 🔵
  id: number; title: string; source_url: string;
  availability: "available" | "unavailable_this_year"; direction_ids: number[];
  course_count?: number;
  courses?: { raw_title: string; course_id: number | null; match_status: "matched" | "not_found" }[];
}
export interface SyncJob {
  id: number; source: "saz_catalog" | "faculty_certificates"; initiator: "admin" | "scheduler";
  initiated_by: { id: number; full_name: string } | null;
  status: "queued" | "running" | "succeeded" | "failed";
  started_at: string; finished_at: string | null;
  added_count: number; updated_count: number; error_message: string | null;
}
export interface ModerationItem {
  id: number; sync_job_id: number; course_id: number | null;
  change_type: "add" | "update" | "remove";
  payload: Record<string, unknown>; diff: Record<string, { old: unknown; new: unknown }> | null;
  status: "pending" | "approved" | "rejected";
  reviewed_by: { id: number; full_name: string } | null; reviewed_at: string | null;
}

// ---------- Адмінка: користувачі, довідники, аудит (🟡) ----------
export interface AdminUser {
  id: number; email: string; full_name: string; role: "student" | "admin";
  created_at: string; last_login_at: string | null;
  student: null | { specialty: string | null; course_year: 1 | 2 | 3 | 4 | null; course_year_source: CourseYearSource | null };
}
export interface AdminUserPatch {
  role?: "student" | "admin";
  student?: { course_year?: 1 | 2 | 3 | 4; specialty?: string };
}
export interface DirectionInput { name: string; description?: string | null }
export interface CertificateProgramPatch { direction_ids?: number[]; hidden?: boolean }   // 🔵
export interface AuditLogEntry {
  id: number; actor: { id: number; full_name: string } | null;
  action: string; object_type: string; object_id: number;
  outcome: "allowed" | "denied"; ip: string; created_at: string;
  old_value?: unknown; new_value?: unknown;               // лише в GET /admin/audit-log/{id}
}
export interface BulkReviewResult { approved: number[]; rejected: number[]; skipped: { id: number; code: string }[] }
```

---

## 5. Паралельна розробка: як працювати

**Фронтенд:**
- Для ✅-кінцевих точок працювати проти реального бекенду: `uvicorn src.api.main:app --reload --port 3000`, токен `Bearer test`. Автентифікація поки заглушка: будь-який токен означає студента з id `42`. Дані зберігаються в БД (без `DATABASE_URL` — локальний файл `yourpath.sqlite`, див. [`../architecture/database.md`](../architecture/database.md)); у порожню БД при старті додаються демо-дані: дисципліни `101`, `102`, `205` (вибіркові) і `301` (нормативна), плани `1` (`draft`) і `2` (`submitted`) студента 42, план `3` — чужий (403). `POST /plans` повертає новий id, зміни зберігаються між запитами. Щоб почати з чистих демо-даних, видаліть `yourpath.sqlite`.
- Для 🟡/🔵-кінцевих точок використовувати моки (напр. MSW) з прикладами з цього документа.
- Не покладатися на клієнтську валідацію як на єдину перевірку: завжди обробляти 422 від сервера.

**Бекенд:**
- Реалізувати 🟡-кінцеві точки з формами, описаними тут, через Pydantic-моделі. Кожна нова кінцева точка: `error_responses(...)` для документування помилок, `ApiError` для бізнес-помилок, smoke-тест у `tests/test_api_smoke.py`, перегенерована специфікація.
- Змінювати ✅-форми лише сумісно (§1.7).

**CORS:** зараз `allow_origins=["*"]`, `allow_credentials=False`. Цього достатньо для запитів з Bearer-токеном, але refresh-cookie (§3.1) вимагає `allow_credentials=True` і **явний** список origin фронтенду (з `*` браузер cookie не надішле). Змінити разом з реалізацією `/auth/*`.

---

## 6. Розбіжності, які треба вирішити команді

| # | Розбіжність | Код зараз | Документи | Рекомендація |
|---|---|---|---|---|
| 1 | Чужий план | `403 PLAN_FORBIDDEN` | threat model R3: 404, щоб не розкривати існування запису | Перейти на 404 `PLAN_NOT_FOUND`. Фронтенд уже обробляє 403 і 404 однаково (§1.4), тому зміна не ламає UI |
| 2 | Значення статусу «затверджено» | `approved` | `data-model.md`: `approved_in_saz` | Залишити `approved` (зафіксовано в API v1); у БД назва може бути будь-якою |
| 3 | Тип триместру | integer 1–3 | `data-model.md`: enum `autumn`/`spring`/`summer` | Залишити integer в API (зафіксовано), мапити в БД |
| 4 | Тип навчального року | integer `2026` | `data-model.md`: рядок `"2026/2027"` | Залишити integer (рік початку) в API |
| 5 | Хто визначає `is_free_elective`, `credits`, `title` елемента плану | клієнт | R15, `data-model.md` (`PlanItem.category` рахує сервер) | Сервер перевіряє і перераховує за каталогом; поля в запиті залишаються для сумісності (§3.4) |
| 6 | 4 курс: навантаження | сервер зберігає надіслане | FR-003: розрахунок автоматично | Сервер ігнорує надіслане для `course = 4` (§2.3) |
| 7 | AI-генерація | — | `sequence-generate-plan.puml`: синхронний запит | Асинхронна (202 + опитування), як рекомендує R10 (§3.7). Оновити sequence-діаграму |
| 8 | `request_id` у помилках | немає | `quality-attributes.md`: обов'язковий `request_id` | Заголовок `X-Request-ID` (§1.2), без зміни тіла помилки |
| 9 | Форма помилки 422 для бізнес-правил плану | `field` вказує на тіло загалом, `message` з префіксом `Value error, ` | — | Віддавати власні коди (`FREE_ELECTIVE_LIMIT_EXCEEDED` тощо) у `details`, як у `/plans/validate`. Це сумісна зміна |
| 10 | Звідки береться `course_year` | — | `data-model.md`, R15: лише синхронізація з САЗ або адмін | Синхронізація заблокована (R14), тому студент вказує курс один раз при онбордингу (`self_declared`), адмін виправляє (§3.2.1). Альтернатива: лише адмін заповнює курс для всіх студентів, але це блокує студента до дії адміна |
| 11 | Звідки береться історія попередніх років | — | Мала надходити з САЗ («Оновити», ⛔) | Студент вводить її сам або через документ деканату за минулий рік; адмін може підтвердити (§3.2.2). Лічильники `/me` рахуються з неї. Коли з'явиться синхронізація, вона додаватиме записи `source: "saz_sync"` |
| 12 | Хто визначає профорієнтовність дисципліни | — | Не визначено (`Course` має `CourseDirection`, але не сказано, хто їх заповнює) | Адмін вручну (`PUT /admin/disciplines/{id}/directions`). Якщо САЗ публікує цю інформацію, парсер пропонує зміни через чергу модерації, а ручна кінцева точка залишається для виправлень |
| 13 | Експорт плану | — | Use-case 16: «фіксація / експорт» без формату | PDF на сервері (`/plans/{id}/export`). Якщо достатньо друку з браузера, не реалізовувати й вимкнути `features.plan_export` |
| 14 | Адмін і плани студентів | — | SEC-001: доступ до планів лише власнику | Адмін не має кінцевих точок для перегляду планів студентів; бачить лише профіль, лічильники й історію |

---

## 7. Покриття вимог

Перевірка, що контракт охоплює всі функції системи, яких торкається фронтенд.

### 7.1. Use-case'и (`AGENTS.md` §6)

| № | Кейс | Кінцеві точки |
|---|---|---|
| 1 | Автентифікація | `/auth/google`, `/auth/refresh`, `/auth/logout`, `/config` |
| 2 | Профіль + Індивідуальний план | `/me`, `/me/onboarding`, `/me/academic-history`, `GET /plans?status=approved` |
| 3 | Документ деканату | `/deanery-documents` (POST, GET, GET `{id}`, `{id}/file`, DELETE) |
| 4 | Створення плану вибіркових | `POST /plans`, `PUT /plans/{id}`, `/plans/validate`, `/plan-generations`, `/disciplines` |
| 6 | Побажання | `/preferences/{academic_year}`, `/directions`, `/instructors`, `/certificate-programs` |
| 7 | Навантаження по триместрах | `load_levels` у планах і побажаннях; `warnings` (`LOW_LOAD_FUTURE_INCREASE`) |
| 8 | Автонавантаження 4 курсу | `load_levels_mode: "auto"` у `/me` і `PlanResponse`; сервер розраховує `load_levels` |
| 9 | Каталог | `GET /disciplines` (фільтри, `category_for_me`, `already_taken`), `/disciplines/{id}` |
| 10 | AI-рекомендації | `/plan-generations`, `ai_explanation` у `PlanItem` |
| 11 | Альтернативи | `alternatives` у `PlanItem`; заміна через `PUT /plans/{id}` |
| 12 | Контроль нормативу | `/plans/validate`, `/plans/{id}/submit`, лічильники `/me` |
| 13 | Сертифікатні програми | `/certificate-programs`, `certificate_program_ids` у `Discipline`, `/admin/certificate-programs/*`, `SyncJob` з `source: faculty_certificates` |
| 14 | Збереження + автосинк із САЗ | Збереження: `POST`/`PUT /plans` + `GET /plans?status=draft`. Автосинк: ⛔ `/plans/sync-saz` (R14) |
| 15 | Адміністрування парсингу | `/admin/sync-jobs`, `/admin/moderation-items/*` |
| 16 | Фіксація / експорт | `GET /plans/{id}`, `/plans/{id}/export`, `reviews_url` |

Доменні функції адміна з `AGENTS.md` §3 («керує довідниками»): `/admin/directions`, `/admin/disciplines/{id}/directions`, `/admin/certificate-programs/*`, `/admin/users`.

### 7.2. Функціональні вимоги (`requirements.md`)

| FR | Де в контракті |
|---|---|
| FR-001 вибір навантаження для 2–3 курсу | `load_levels`, §2.3 |
| FR-002 попередження про низьке навантаження | `warnings`, §2.4 |
| FR-003 автонавантаження 4 курсу | §2.3, `load_levels_mode` |
| FR-004 збереження чернетки, «Збережені плани» | `POST /plans`, `GET /plans?status=draft` |
| FR-005 небажані викладачі | `unwanted_instructor_ids` у побажаннях і генерації |
| FR-006 неможливо уникнути викладача | `notices` (`UNWANTED_INSTRUCTOR_UNAVOIDABLE`) у генерації |
| FR-007 1–3 напрямки | `direction_ids`, 422 при 4 |
| FR-008 ручний запуск парсингу, черга модерації | `POST /admin/sync-jobs`, `/admin/moderation-items` |
| FR-009 2–3 альтернативи | `alternatives` (`rank` 1–3) |
| FR-010 ліміт 25 при заміні на альтернативу | `PUT /plans/{id}` + §2.4 |
| FR-011 журнал `SyncJob` | `GET /admin/sync-jobs`, `error_message` |
| FR-012 вхід лише з домену НаУКМА | `/auth/google`, `403 DOMAIN_NOT_ALLOWED` |
| FR-013 каталог і сертифікатні програми для читання | `/disciplines`, `/certificate-programs` |

User stories US-001…US-010 відповідають тим самим FR і покриті тими самими кінцевими точками. NFR: PERF-001 (асинхронна генерація, §3.7), REL-001 (`AI_UNAVAILABLE` після повторів), SEC-001 (лише власник, `/admin/audit-log`), USE-001 (онбординг → побажання → генерація: 3 кроки).

### 7.3. Що свідомо не входить у контракт

Це внутрішні частини бекенду, які фронтенд не викликає:

- парсери САЗ і сайту сертифікатних програм (запускаються через `/admin/sync-jobs`, але самі є фоновими задачами);
- розпізнавання документа деканату (результат видно через `parse_status`);
- виклики LLM, анонімізований prompt, повторні спроби (R1, R5);
- запис `AuditLog`, rate limiting, логування з `X-Request-ID`;
- схема БД, міграції, ролі БД (R12), розгортання.

Також поза системою (`high-level-design.md`, «Out-of-scope»): запис у САЗ, відгуки про дисципліни (лише посилання), кабінет деканату. Сповіщень (email, push) у вимогах немає, тому кінцевих точок для них теж немає.

---

## Використання ШІ

- **Що створено:** весь документ підготовлено за допомогою Claude (Claude Code, модель Opus 5.5) за запитом команди. Розділи про ✅-кінцеві точки описують поточний код; форми 🟡/🔵-кінцевих точок, коди помилок і попереджень, типи TypeScript і рекомендації в §6 — **пропозиції ШІ**, виведені з `requirements.md`, `user-stories.md`, `data-model.md`, `threat-model.md`, `quality-attributes.md`, `api-design.md`, `AGENTS.md` і `Project-Description.md`. Вони потребують узгодження командою.
- **Як перевірено:** форми, обмеження, коди помилок і статус-коди ✅-кінцевих точок звірено вручну з `src/api/common.py`, `src/api/routes/plans.py`, `src/api/routes/disciplines.py` і `src/api/main.py`. Поведінку заглушки (id планів, власник, id нового плану) звірено з кодом. Приклади помилок перевірено запитами через `TestClient` до реального застосунку: 422 для ліміту вільного вибору (`field: "body"`, `28.0 > 25`), 403 для чужого плану, `HTTP_404` для неіснуючого шляху, 422 для `limit=500`. Кінцеві точки 🟡/🔵 не існують у коді й не перевірялись; TypeScript-типи не компілювались.
- **Друга ітерація (також Claude):** додано контракти, яких бракувало для повного покриття: `/config`, онбординг і академічна історія, побажання, експорт плану, файл і видалення документа деканату, адмінські кінцеві точки для користувачів, напрямків, профорієнтовності дисциплін, сертифікатних програм і журналу аудиту; розбіжності 10–14 у §6; матриця покриття §7. Покриття перевірено вручну: кожен use-case з `AGENTS.md` §6, кожна FR з `requirements.md` і кожна сутність з `data-model.md`, яку бачить фронтенд, зіставлені з кінцевими точками в §7.
