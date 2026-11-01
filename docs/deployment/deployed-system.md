# Розгорнута система

Застосунок YourPathUkma розгорнуто публічно в Microsoft Azure.

| | |
|---|---|
| **Сайт** | https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io |
| **Swagger UI (API)** | https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io/api-docs |
| **Перевірка стану** | https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io/health |

## Як увійти

Вхід лише через Microsoft 365 з корпоративною поштою `@ukma.edu.ua` (вимога FR-012). Пароль застосунок не бачить і не зберігає. Після першого входу застосунок просить вказати курс і спеціальність.

- **Студент:** профіль із лічильниками кредитів, каталог дисциплін із фільтрами, побажання (рівні навантаження, напрями, викладачі), конструктор плану з перевіркою кредитів, збереження чернеток, подання плану й експорт.
- **Адміністратор:** користувачі, модерація змін каталогу, запуск і журнал синхронізації, напрями, журнал аудиту. Роль `admin` отримують пошти зі змінної `ADMIN_EMAILS` при першому вході.

## Де і як працює

```
Браузер ──HTTPS──▶ Azure Container Apps (yourpath) ──▶ Azure Database for PostgreSQL
                      один Docker-образ zarraban/yourpath         (база yourpath, PostgreSQL 16)
                      ├─ /            фронтенд (React)
                      └─ /api/v1/...  API (FastAPI)
```

- **Застосунок:** Azure Container Apps, регіон France Central, одна репліка (0,5 vCPU, 1 ГіБ). Фронтенд і API працюють в одному контейнері на одному адресі, тому refresh-cookie (`SameSite=strict`, `Secure`) працює без CORS.
- **Образ:** [`zarraban/yourpath`](https://hub.docker.com/r/zarraban/yourpath) на Docker Hub (публічний, без секретів).
- **База даних:** Azure Database for PostgreSQL (Flexible Server, Burstable). Міграції Alembic застосовуються при старті.
- **Секрети** (`JWT_SECRET`, рядок підключення до бази, секрет застосунку Microsoft Entra) зберігаються як secrets Container Apps, а не в образі чи репозиторії.
- **Вхід:** застосунок зареєстровано в Microsoft Entra, адреса `…/auth/callback` додана до дозволених redirect URI.
- Підписка Azure for Students: регіони обмежені політикою (Norway East, France Central, Austria East, Sweden Central, Switzerland North).

## Обмеження

- **Парсер САЗ у хмарі вимкнений** (`SAZ_AUTORUN=0`): йому потрібні Playwright і вхід у видимому вікні браузера. Сторінка «Синхронізація» в адмінці є, але реальний парсинг працює лише локально (див. [README](../../README.md)).
- Одна репліка: міграції виконуються при старті, а фонові задачі живуть у процесі застосунку.
- **Каталог демонстраційний.** У розгорнутій базі 4 демо-дисципліни («Функціональне програмування», «Основи кібербезпеки», «Управління цифровим продуктом», «Алгоритми та структури даних») і 3 напрями (Data Science, Cybersecurity, Software Engineering), щоб студент міг користуватися каталогом і конструктором плану. Застосунок сіє демо-дані лише в порожню базу, а тут уже є реальні користувачі, тому каталог додано вручну зсередини контейнера (`az containerapp exec`). Демо-користувачі й демо-плани не створювались. Повний каталог САЗ з'являється лише після запуску парсера й схвалення змін у черзі модерації (парсер працює локально, див. [README](../../README.md)).

## Як перевірити

```bash
curl https://yourpath.blackbush-960afa87.francecentral.azurecontainerapps.io/health
# {"status":"ok","version":"1.0.0","message":"All systems operational"}
```

Далі відкрийте сайт і увійдіть поштою `@ukma.edu.ua`.

---
**Нотатка щодо використання ШІ:** сторінку створено за допомогою Claude (Claude Code) за станом реального розгортання (ресурси Azure, змінні середовища, журнали контейнера). Перевірка: `GET /health` = 200, головна сторінка й Swagger відкриваються, вхід через Microsoft підтверджено вручну. Розділ про демонстраційний каталог оновлено за допомогою Claude (Claude Code) після додавання демо-даних; перевірка: `GET /api/v1/disciplines` розгорнутого API повертає 4 дисципліни.
