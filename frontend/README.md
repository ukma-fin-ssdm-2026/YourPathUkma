<!-- Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: кожну команду зі скриптів `package.json` і змінну з `.env.example` звірено вручну; застосунок у браузері й з живим бекендом не запускався. -->

# YourPathUkma: фронтенд

Веб-застосунок для студентів Факультету інформатики НаУКМА: планування вибіркових дисциплін на навчальний рік із контролем лімітів кредитів. Інтерфейс українською. Для адміністратора є розділ модерації каталогу.

React 19, TypeScript (strict), Vite, Tailwind CSS 4, TanStack Query, Zustand, react-router, `@dnd-kit`, `sonner`. Тести: Vitest, Testing Library, MSW.

## Екрани

| Маршрут                     | Що робить                                                                                 |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| `/login`                    | Вхід через Microsoft 365 (OAuth2 Authorization Code + PKCE)                               |
| `/onboarding`               | Курс і спеціальність при першому вході                                                    |
| `/`                         | Профіль, журнал кредитів за курсами                                                       |
| `/path/plan`, `/path/saved` | Таблиця планів за роками, збережені плани                                                 |
| `/path/create`              | Конструктор плану: каталог, три триместри, перетягування, збереження й подання            |
| `/path/create/document`     | Документ деканату з нормативними дисциплінами                                             |
| `/path/create/preferences`  | Побажання: навантаження, напрямки, викладачі                                              |
| `/path/plan/:id`            | Перегляд плану й експорт у PDF                                                            |
| `/catalog`                  | Каталог дисциплін із фільтрами                                                            |
| `/admin/*`                  | Лише для ролі `admin`: огляд, модерація, синхронізація, користувачі, напрямки, журнал дій |

## Запуск

Потрібен Node.js. З теки `frontend/`:

```bash
npm ci
npm run gen:api   # типи ✅-моделей із ../docs/api/openapi-generated.json у src/api/generated/ (у .gitignore)
cp .env.example .env.local
npm run dev       # http://localhost:5173
```

Решта скриптів:

| Команда             | Призначення                        |
| ------------------- | ---------------------------------- |
| `npm run lint`      | ESLint                             |
| `npm run typecheck` | `tsc --noEmit`                     |
| `npm test`          | Vitest, один прогін                |
| `npm run build`     | перевірка типів і збірка у `dist/` |

CI (`.github/workflows/ci.yaml`, job `frontend`) запускає: `npm ci`, `gen:api`, `lint`, `typecheck`, `test`, `build`.

## Змінні оточення (`.env.local`)

| Змінна              | Значення за замовчуванням | Для чого                                                                                                                                                                                    |
| ------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VITE_USE_MOCKS`    | `false`                   | `false`: усе йде на реальний бекенд (потрібен справжній вхід через Microsoft). `true`: моки входу, `/me`, онбордингу й `/admin/*`, решта з бекенду. `full`: моки всього, бекенд не потрібен |
| `VITE_MOCK_ROLE`    | (порожньо)                | `admin`: мок-користувач стає адміністратором, відкриваються екрани `/admin`                                                                                                                 |
| `VITE_API_BASE`     | `/api/v1`                 | Префікс API                                                                                                                                                                                 |
| `VITE_MS_CLIENT_ID` | порожньо                  | Application (client) ID застосунку Microsoft Entra; без нього вхід показує «Вхід не налаштовано»                                                                                            |
| `VITE_MS_TENANT`    | порожньо                  | GUID tenant тієї ж app registration, що й `MS_TENANT_ID` у бекенді (бекенд звіряє `tid` та `iss`)                                                                                           |

## Бекенд і моки

Dev-сервер проксює `/api` на `http://localhost:3000` (`vite.config.ts`). Бекенд запускається окремо (див. корінь репозиторію, `uvicorn src.api.main:app --port 3000`).

Контракт: [`docs/api/contract.md`](../docs/api/contract.md). Позначки: ✅ є в бекенді, 🟡 лише запропоновано.

З `VITE_USE_MOCKS=true` моки (`src/mocks/`) підміняють вхід і профіль, щоб UI можна було показати без Microsoft: `/auth/microsoft`, `/auth/refresh`, `/auth/logout`, `/me*` (разом з онбордингом й історією оцінок) і `/admin/*`.

Усе інше йде на реальний бекенд: `/config`, `/preferences/*`, `/disciplines`, `/directions`, `/instructors`, `/plans*` (разом із `submit` і `export`), `/deanery-documents*`. Бекенд-заглушки, які це торкається: експорт повертає фальшивий PDF, а розпізнавання документа деканату ще не реалізоване, тож будь-яке завантаження закінчується статусом «Не розпізнано».

З `VITE_USE_MOCKS=full` додатково вмикаються моки всіх цих ендпоінтів (`coreHandlers` у `core.ts` і `backendHandlers` у `handlers.ts`), тож застосунок працює без запущеного бекенду.

Запуск проти реального бекенду з справжнім входом через Microsoft:

1. У Microsoft Entra створіть app registration (tenant НаУКМА) з redirect URI `http://localhost:5173/auth/callback`. Бекенд сам обмінює код на токен, тому тип застосунку має бути **Web** з client secret (для типу SPA Microsoft відхиляє обмін коду з сервера).
2. У корені: `cp .env.example .env`, заповніть `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), `COOKIE_SECURE=0` за потреби, `ADMIN_EMAILS` для адміністратора. Запустіть `uvicorn src.api.main:app --port 3000`.
3. У `frontend/`: `cp .env.example .env.local`, заповніть `VITE_MS_CLIENT_ID` і `VITE_MS_TENANT` (ті самі значення), `npm run dev`. Перший вхід автоматично створює студента, далі відкривається онбординг.

Без Microsoft-застосунку UI можна запустити з `VITE_USE_MOCKS=true` (вхід через мок). Змінні оболонки мають пріоритет над `.env.local`.

У тестах (`src/test/setup.ts`) вмикаються і `handlers`, і `backendHandlers`; окремі тести перекривають їх через `server.use(...)` (`src/test/handlers.ts`).

### Що потрібно від бекенду

- Вхід через Microsoft 365: `POST /auth/microsoft` з тілом `{code, code_verifier, nonce, redirect_uri}` реалізовано (гілка `feat/microsoft-auth`). Фронтенд передає той самий `nonce`, що й у запиті авторизації.
- Токени різних користувачів (зокрема адміна: `ADMIN_EMAILS`) видає справжній вхід, тому `/admin/*` доступний без моків.
- CORS: для refresh-cookie потрібні явні origins і `allow_credentials` (`CORS_ORIGINS=http://localhost:5173`).
- Заголовок `X-Request-ID` має бути в `Access-Control-Expose-Headers`, щоб фронтенд показував «Код помилки».

## Структура `src/`

```
api/       клієнт (Bearer у пам'яті, refresh при 401), типи, помилки, /config
auth/      Microsoft OAuth + PKCE, сесія (Zustand), захист маршрутів
app/       маршрути, шапка, навігація
features/  catalog, builder, plans, plan-view, deanery, preferences, profile, admin
ui/        базові компоненти (Button, Card, Badge, Segmented, Switch), хук фокусу діалогів
lib/       кредити, триместри, дати, ініціали, завантаження файлів
mocks/     MSW-обробники й стан моків
styles/    токени (світла/темна тема), глобальні стилі
test/      налаштування Vitest, спільні тестові обробники
```

## Правила роботи

- Кожен PR до ~400 рядків рукописного коду (lock- і згенеровані файли не рахуються).
- У кожному файлі коментар «Використання ШІ» (вимога `AGENTS.md` §9): що створено за допомогою ШІ і як перевірено.
- Помилки API розгалужуються за `code`, а не за текстом повідомлення; дані з API (`payload`, `diff`, `old_value`, …) показуються лише як текст.

## Що не перевірялось і відомі обмеження

- Застосунок не запускався в браузері й з живим бекендом: усе перевірено лише автотестами (jsdom). Зокрема не перевірено справжнє перетягування в конструкторі (jsdom не має геометрії), завантаження PDF і редірект Microsoft-входу.
- Сторінка перегляду плану показує лише вибіркові дисципліни, нормативні з'являться, коли бекенд поверне `normative_items`.
- У dev зміни напрямків (`/admin/directions`) йдуть у моки, а список читається з реального `/directions`, тож він не оновиться.
- `beforeunload`-попередження про незбережений план спрацьовує лише при закритті вкладки.
