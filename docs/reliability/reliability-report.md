## Використання ШІ

Розділ «Бонуси» підготовлено за допомогою Claude (Claude Code). Workflow, lock-файл і додавання статусу до обов'язкових перевірок також зроблено з Claude Code. Перевірка: наявність файлів на `main`, список обов'язкових перевірок і стан ruleset звірено через GitHub API; результат обох прогонів взято зі сторінок Actions.

## Бонуси

### Тести надійності як обов'язкова перевірка PR

Тести з `tests/reliability/` запускаються в CI окремим кроком, і цей крок є обов'язковою перевіркою для `main`: PR не зливається за звичайними правилами, поки він не пройшов.

**Що зроблено:**
- Окремий workflow [`.github/workflows/reliability.yml`](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/blob/main/.github/workflows/reliability.yml) із job `reliability-tests`, який виконує `pytest tests/reliability -q`. Тригери: push і PR у `main`, ручний запуск.
- У `.github/workflows/ci.yaml` основний крок тестів запускається з `--ignore=tests/reliability`, щоб ці тести не виконувалися двічі.
- Залежності для job ставляться лише з [`requirements-ci.lock`](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/blob/main/requirements-ci.lock) (`pip install --require-hashes`): інакше SonarCloud (правило S8544) валить Quality Gate, який теж обов'язковий. Правило записано в `AGENTS.md` §9.2.
- Статус `reliability-tests` додано до обов'язкових перевірок у ruleset «Require status check», який діє на `main`. Змінено 2026-11-08 о 14:06 за київським часом.

### Перевірка здоров'я (health check) сервісу

**Що зроблено.** Додано `GET /health/ready` (`src/api/health.py`). Він паралельно перевіряє критичні
залежності: БД (`SELECT 1` через SQLAlchemy engine) і Microsoft Entra ID (запит до публічного JWKS-ендпоінта
тенанта, потрібного для входу). Кожна перевірка має тайм-аут 2 с, загальний час відповіді обмежений.
Наявний `/health` залишено як liveness-перевірку без залежностей, щоб збій БД не спричиняв
перезапуск застосунку платформою.

**Формат відповіді.**
- Усе гаразд: `200 {"status": "healthy", "checks": {"database": {"status": "up", ...}, ...}}`
- Збій залежності: `503 {"status": "unhealthy", ...}` зі статусом `down` для проблемної залежності.
- Microsoft не налаштовано (локальна розробка): `not_configured`, це не збій.

**Режим відмови: швидка відмова (fail fast).** Збій критичної залежності не маскується резервним
значенням, а чесно повертається як `unhealthy`/503, бо моніторинг має знати про реальний стан.
Деталі збою (хост, порт, текст винятку) лише в логах, назовні їх немає.

**Відновлення.** Автоматичне: щойно залежність відповідає, наступний запит повертає `healthy`.
Окремих кроків не потрібно.

#### Докази

| Що | Посилання / результат |
|---|---|
| PR, який додав окремий крок CI | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/pull/226 |
| Workflow на `main` | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/blob/main/.github/workflows/reliability.yml |
| **Прогін, де крок `reliability-tests` пройшов** (на PR #226, 47 с) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/actions/runs/42475966440/job/128717301428 |
| **Прогін на `main` після злиття** (успішний) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/actions/runs/42478577815 |
| Обов'язкові перевірки `main` (GitHub API `GET /repos/ukma-fin-ssdm-2026/YourPathUkma/rules/branches/main`, правило `required_status_checks`) | `frontend`, `build`, `SonarCloud Code Analysis`, **`reliability-tests`** (застосунок GitHub Actions, `integration_id` 15368) |
| Налаштування ruleset (видно лише адміністраторам репозиторію) | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/settings/rules/25622155 |
| Тести, які запускає крок | https://github.com/ukma-fin-ssdm-2026/YourPathUkma/tree/main/tests/reliability (3 файли, 30 тестів) |

**Як перевірити обов'язковість:** на будь-якому відкритому PR у списку перевірок є `reliability-tests`, а `statusCheckRollup` для нього рахується серед обов'язкових (GraphQL-поле `isRequired`).

**Чесно про історію.** Перша спроба (PR [#212](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/pull/212)) була стековою: її змерджено в стару гілку вже після злиття #211, тому в `main` вона не потрапила. Ті самі коміти подано повторно як #226 і злито в `main`.

**Докази.** Тести `tests/reliability/test_health.py`:
- `test_ready_unhealthy_when_database_down`: ін'єкція збою БД -> 503, статус `unhealthy`, без витоку деталей;
- `test_ready_unhealthy_on_timeout`: зависла залежність -> `down` у межах тайм-ауту;
- решта тестів: healthy, not_configured, справжня БД.

#### Хто пояснює бонус у відео
Владислав Смирнов, у відео Лаб 9: https://www.loom.com/share/1d113dcd9f7648f4af3bff23c260eb91 (також у `Labs/Lab09/video_Vladyslav.txt`).
