<!-- Використання ШІ: файл створено за допомогою Claude (Anthropic). Перевірка: кожну команду зі скриптів `package.json` і змінну з `.env.example` звірено вручну; застосунок у браузері й з живим бекендом не запускався. -->

# YourPathUkma: фронтенд

Веб-застосунок для студентів Факультету інформатики НаУКМА: планування вибіркових дисциплін на навчальний рік із контролем лімітів кредитів. Інтерфейс українською. Для адміністратора є розділ модерації каталогу.

React 19, TypeScript (strict), Vite, Tailwind CSS 4, TanStack Query, Zustand, react-router, `@dnd-kit`, `sonner`. Тести: Vitest, Testing Library, MSW.

## Екрани

| Маршрут | Що робить |
|---|---|
| `/login` | Вхід через Microsoft 365 (OAuth2 Authorization Code + PKCE) |
| `/onboarding` | Курс і спеціальність при першому вході |
| `/` | Профіль, журнал кредитів за курсами |
| `/path/plan`, `/path/saved` | Таблиця планів за роками, збережені плани |
| `/path/create` | Конструктор плану: каталог, три триместри, перетягування, збереження й подання |
| `/path/create/document` | Документ деканату з нормативними дисциплінами |
| `/path/create/preferences` | Побажання: навантаження, напрямки, викладачі |
| `/path/plan/:id` | Перегляд плану й експорт у PDF |
| `/catalog` | Каталог дисциплін із фільтрами |
| `/admin/*` | Лише для ролі `admin`: огляд, модерація, синхронізація, користувачі, напрямки, журнал дій |

## Запуск

Потрібен Node.js. З теки `frontend/`:

```bash
npm ci
npm run gen:api   # типи ✅-моделей із ../docs/api/openapi-generated.json у src/api/generated/ (у .gitignore)
cp .env.example .env.local
npm run dev       # http://localhost:5173
```

Решта скриптів:

| Команда | Призначення |
|---|---|
| `npm run lint` | ESLint |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest, один прогін |
| `npm run build` | перевірка типів і збірка у `dist/` |

CI (`.github/workflows/ci.yaml`, job `frontend`) запускає: `npm ci`, `gen:api`, `lint`, `typecheck`, `test`, `build`.

## Змінні оточення (`.env.local`)

| Змінна | Значення за замовчуванням | Для чого |
|---|---|---|
| `VITE_USE_MOCKS` | `true` | Вмикає MSW-моки для ендпоінтів, яких ще немає в бекенді |
| `VITE_API_BASE` | `/api/v1` | Префікс API |
| `VITE_MS_CLIENT_ID` | порожньо | Application (client) ID застосунку Microsoft Entra; без нього вхід показує «Вхід не налаштовано» |
| `VITE_MS_TENANT` | `organizations` | Tenant для авторизації Microsoft |

## Бекенд і моки

Dev-сервер проксює `/api` на `http://localhost:3000` (`vite.config.ts`). Бекенд запускається окремо (див. корінь репозиторію, `uvicorn src.api.main:app --port 3000`).

Контракт: [`docs/api/contract.md`](../docs/api/contract.md). Позначки: ✅ є в бекенді, 🟡 лише запропоновано.

З `VITE_USE_MOCKS=true` моки (`src/mocks/`) закривають:

- вхід і сесію: `/auth/microsoft`, `/auth/refresh`, `/auth/logout`;
- `/me`, `/me/onboarding`, `/me/academic-history`;
- `/preferences/{year}`;
- `/deanery-documents*`;
- `POST /plans/{id}/submit`, `GET /plans/{id}/export` (віддає заглушку PDF);
- усе `/admin/*`.

Решта запитів іде на реальний бекенд: `/config`, `/plans*`, `/plans/validate`, `/disciplines`, `/directions`, `/instructors`. У `contract.md` `/directions`, `/instructors` і `/plans/validate` поки позначені 🟡, тому якщо в запущеному бекенді їх немає, відповідні екрани в dev не працюватимуть, поки їх не додадуть.

У тестах моки теж вмикаються (`src/test/setup.ts`); ✅-ендпоінти там перекриваються в самих тестах через `server.use(...)` (`src/test/handlers.ts`).

### Що потрібно від бекенду

- Вхід через Microsoft 365. Назва `POST /auth/microsoft` і форма запиту — **припущення фронтенду**; у контракті зараз `POST /auth/google`.
- Реалізація 🟡-ендпоінтів зі списку вище.
- CORS: для refresh-cookie потрібні явні origins і `allow_credentials` (зараз `*`).
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
