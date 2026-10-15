# Звіт про прогрес розробки та структуру проєкту (Progress Report)

**Проєкт:** YourPathUkma (REST API)  
**Відповідальні ролі:** Quality Lead & Prototype Lead  
**Статус:** MVP повністю реалізовано та протестовано (55/55 тестів пройшли успішно).  

---

## 1. Базова структура коду та модулів

Проєкт реалізовано на фреймворку **FastAPI** із використанням **SQLAlchemy ORM** та **Pydantic v2**, дотримуючись шарової архітектури (Layered Architecture):

```text
src/
├── api/
│   ├── main.py                  # Точка входу FastAPI, конфігурація CORS, реєстрація роутерів, генерація OpenAPI
│   ├── common.py                # Обробка помилок (ApiError), пагінація, залежність get_current_student_id
│   ├── onboarding.py            # Перевірка статусу онбордингу студента (get_onboarded_student)
│   └── routes/
│       ├── auth.py              # Авторизація через Google SSO (/auth/*)
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

##файл згенеровано ШІ на основі пояснень та опису проєкту (структури, функціоналу і тд.)