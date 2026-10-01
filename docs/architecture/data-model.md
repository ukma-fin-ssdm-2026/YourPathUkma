# Data Model — YourPathUkma

Діаграма (ER, PlantUML): [`uml/data-model.plantuml`](uml/data-model.plantuml) · зображення: [`uml/data-model.png`](uml/data-model.png)

![Data model](uml/data-model.png)

Джерела: `Project-Description.md` (ключові функції), `requirements.md` (глосарій, FR-001…FR-012, PERF/REL/SEC), `traceability-matrix.md` (компоненти), `component-diagram.plantuml`, `deployment.puml` (усі дані, включно з файлами документів, зберігаються в одній БД PostgreSQL), `sequence-generate-plan.puml` (потік AI-генерації). Сутності `AuditLog` і `AIGenerationRequest` додано за результатами [`threat-model.md`](threat-model.md).

## Нотація

| Позначка | Значення |
|---|---|
| `<<PK>>` | Первинний ключ. `<<PK, FK>>` на кількох полях означає складений ключ зв'язкової таблиці |
| `<<FK>>` / `<<unique>>` | Зовнішній ключ / унікальне поле (природний ключ) |
| `<<PII>>` (рожевий) | Сутність містить персональні дані |
| `{PII}` | Поле з персональними даними |
| `{sensitive}` | Чутливе поле, що не є PII напряму, але визначає права доступу або є репутаційно чутливим |
| `<<security>>` (синій) | Сутність, додана для виконання SEC-001 / REL-001 і контрзаходів з `threat-model.md` |
| `*` | Обов'язкове поле (NOT NULL) |

## 1. Ключові функції → сутності

Модель покриває всі 7 ключових функцій з `Project-Description.md`.

| # | Функція | Сутності | Вимоги |
|---|---|---|---|
| 1 | Особистий кабінет: лічильники кредитів, історія планів, «Оновити» з САЗ | `User`, `StudentProfile` (`credits_used_*`, `saz_synced_at`), `IndividualPlan` (`status`, `origin = saz_sync`) | FR-004, FR-012, SEC-001 |
| 2 | Конструктор плану: дисципліни по триместрах, рівні навантаження, конфлікти з нормативними | `PlanPreferences`, `TrimesterLoad`, `PreferenceDirection`, `IndividualPlan`, `PlanItem`, `DeaneryPlanDocument`, `NormativeCourseEntry` | FR-001, FR-003, FR-004, FR-007 |
| 3 | AI-генерація плану з 2–3 альтернативами та поясненнями (`sequence-generate-plan.puml`) | `PlanPreferences` (вхід), `InstructorPreference` (фільтр каталогу до LLM), `Course` (затверджений каталог), `AIGenerationRequest` (спроби ≤ 3), `IndividualPlan` (зберігається як `draft`), `PlanItem.ai_explanation`, `PlanAlternative` | FR-005, FR-006, FR-009, FR-010, PERF-001, REL-001 |
| 4 | Каталог дисциплін із фільтрацією | `Course`, `Instructor`, `CourseInstructor`, `Direction`, `CourseDirection` | FR-005, FR-007, НФВ-1 |
| 5 | Сертифікатні програми: case-insensitive звірка з каталогом | `CertificateProgram`, `CertificateProgramCourse` (`raw_title` → `course_id`), `Course.title_normalized`, `PlanPreferences.certificate_program_id` | Опис проєкту, п. 5 |
| 6 | Контроль кредитного нормативу: 240 / 25 / 54, 57–60 на рік | `StudentProfile.credits_used_*` (похідні), `PlanItem.category`, `Course.credits`, `Course.kind`, `IndividualPlan.total_credits` | FR-002, FR-003, FR-010 |
| 7 | Адміністрування парсингу САЗ і черга модерації | `SyncJob`, `ModerationItem`, `User.role`, `AuditLog` | FR-008, FR-011, PERF-002 |

## 2. Сутності та їхня ідентичність

Усі сурогатні ключі — `bigint` (Long), генеруються БД (`GENERATED ALWAYS AS IDENTITY`); зовнішні ключі теж `bigint`. Такі id послідовні, тому їх легко перебрати: захист від доступу до чужих записів забезпечує лише перевірка власника на сервері (R3 у threat model), а не «непередбачуваність» id.

| Сутність | Первинний ключ | Унікальні поля (`<<unique>>`) | Призначення | Дані |
|---|---|---|---|---|
| `User` | `id` | `google_sub`, `email` | Обліковий запис (студент або адмін) після Google SSO | **PII** |
| `StudentProfile` | `user_id` (PK = FK, 1:1 з `User`) | — | Курс, спеціальність, лічильники кредитів | **PII** |
| `PlanPreferences` | `id` | — | Побажання студента на навчальний рік | **PII** |
| `PreferenceDirection` | (`preferences_id`, `direction_id`) | — | 1–3 обрані напрямки (FR-007) | — |
| `TrimesterLoad` | (`preferences_id`, `trimester`) | — | Рівень навантаження на триместр (FR-001, FR-003) | — |
| `InstructorPreference` | (`preferences_id`, `instructor_id`) | — | Бажані / небажані викладачі (FR-005) | **PII, sensitive** |
| `DeaneryPlanDocument` | `id` | — | Завантажений документ деканату: файл (`content`, у PostgreSQL) і метадані | **PII** |
| `NormativeCourseEntry` | `id` | — | Нормативна дисципліна, розпізнана з документа | — |
| `IndividualPlan` | `id` | — | План студента на рік (draft / submitted / approved_in_saz) | **PII** (через `student_id`) |
| `PlanItem` | `id` | — | Дисципліна плану в триместрі | — |
| `PlanAlternative` | `id` | — | Альтернатива 1..3 для слота (FR-009) | — |
| `AIGenerationRequest` | `id` | — | Запит генерації: статус, спроби, токени, хеш prompt | Службові (`student_id`) |
| `Course` | `id` | `saz_code` | Дисципліна з каталогу САЗ | Публічні, висока цілісність |
| `Instructor` | `id` | — | Викладач | **PII** (ПІБ) |
| `CourseInstructor` | (`course_id`, `instructor_id`) | — | Хто викладає дисципліну | — |
| `Direction` | `id` | `name` | Напрямок розвитку | Публічні |
| `CourseDirection` | (`course_id`, `direction_id`) | — | Прив'язка дисципліни до напрямку | — |
| `CertificateProgram` | `id` | — | Сертифікатна програма з сайту факультету | Публічні |
| `CertificateProgramCourse` | `id` | — | Дисципліна програми; `course_id` — результат звірки | Публічні |
| `SyncJob` | `id` | — | Запуск парсингу (FR-008, FR-011) | Службові (`initiated_by`) |
| `ModerationItem` | `id` | — | Зміна каталогу, що чекає схвалення адміна | Службові (`reviewed_by`) |
| `AuditLog` | `id` | — | Журнал доступу та змін, append-only (SEC-001) | **PII** (`ip`, `old_value`/`new_value`) |

## 3. Персональні та чутливі дані

| Поле | Категорія | Чому чутливе | Як захищене (див. `threat-model.md`) |
|---|---|---|---|
| `User.email`, `User.full_name`, `User.google_sub` | PII, пряма ідентифікація | Ідентифікують студента | Доступ лише власнику (R3); не передаються в LLM (R1) |
| `User.role` | sensitive (права) | Визначає доступ до адмін-модулів | Змінюється лише іншим адміном, не з тіла запиту (R2) |
| `StudentProfile.specialty`, `course_year` | PII; `course_year` ще й визначає права (FR-001, FR-003) | Освітні дані студента | `course_year` змінює лише синхронізація з САЗ або адмін (`course_year_source`, R15) |
| `StudentProfile.credits_used_*` | PII (академічний прогрес) | Освітні дані | Похідні, обчислюються сервером (R15) |
| `PlanPreferences`, `TrimesterLoad`, `PreferenceDirection` | PII (через `student_id`) | Особисті вподобання | Доступ лише власнику (R3) |
| `InstructorPreference.kind = unwanted` | PII + sensitive (репутаційне) | Витік списку «небажаних викладачів» шкодить і студенту, і викладачу | Лише id викладача в prompt; доступ лише власнику (R1, R3) |
| `DeaneryPlanDocument.content` (файл), `original_filename` | PII | Файл містить ПІБ і спеціальність; назва файлу часто містить прізвище | Файл зберігається в PostgreSQL (TZ-3, окремого файлового сховища в `deployment.puml` немає); шифрування бекапів БД; доступ лише власнику (R3, R12) |
| `IndividualPlan`, `PlanItem`, `PlanAlternative` | PII (через `student_id`) | Академічний план студента | SEC-001: доступ лише власнику, кожна спроба в `AuditLog` (R3) |
| `Instructor.full_name` | PII (публічна службова інформація) | Персональні дані викладача | Відображається лише як частина каталогу |
| `AuditLog.ip`, `old_value`, `new_value` | PII | IP-адреса; копії змінених записів | Лише INSERT для застосунку, доступ лише адміну, зберігання ≥ 1 рік (R9) |
| `AIGenerationRequest.prompt_sha256` | службові | Текст prompt не зберігається навмисно | R1 |
| Облікові дані САЗ студента | **критичні, навмисно відсутні в моделі** | Дали б доступ до всього профілю студента в САЗ | R14: не зберігати |
| JWT / refresh-токени | критичні (у моделі не зберігаються) | Дають доступ до сесії | Cookie `HttpOnly` (R7) |

Публічні дані з високою вимогою до **цілісності** (від них залежить валідація 240 / 25 / 57–60): `Course`, `Direction`, `CertificateProgram*`, `ModerationItem`.

## 4. Бізнес-правила, закладені в модель

- `PreferenceDirection`: від 1 до 3 записів на `PlanPreferences` (FR-007), перевірка на сервері.
- `TrimesterLoad.is_auto = true` і заборона ручної зміни для `course_year = 4` (FR-003).
- `PlanAlternative.rank` ∈ 1..3 (FR-009). Заміна (`is_selected`) перевіряє ліміт 25 кредитів вільного вибору (FR-010).
- `Course.kind = normative` не може бути в `PlanItem`: нормативні дисципліни надходять лише з `NormativeCourseEntry`.
- `IndividualPlan.status` за замовчуванням `draft` (FR-004). `total_credits` і `credits_used_*` обчислюються сервером.
- Нові та змінені дисципліни потрапляють у `Course` лише через `ModerationItem.status = approved` (FR-008).
- `SyncJob` фіксує дату, ініціатора, статус, лічильники і помилку (FR-011).
- `AuditLog` — append-only: без UPDATE і DELETE (SEC-001).
- AI-генерація (`sequence-generate-plan.puml`): дисципліни небажаних викладачів (`InstructorPreference.kind = unwanted`) відфільтровуються Catalog Service **до** виклику LLM; у prompt не потрапляють id і email студента (ADR-003); `AIGenerationRequest.attempts` ≤ 3; результат зберігається як `IndividualPlan.status = draft` після повторної перевірки лімітів.

## 5. Відкриті питання

- **«Оновити» з САЗ (R14).** Як отримати затверджений план студента, не зберігаючи його облікові дані САЗ. Модель поки передбачає лише `IndividualPlan.origin = saz_sync` і `StudentProfile.saz_synced_at`.
