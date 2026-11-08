# Звіт про надійність (Лаб 9)

> **Це шаблон для заповнення.** Файлу `docs/reliability/reliability-report.md` раніше не було, тому його створено за структурою з завдання Лаб 9. Автор цього коміту (Владислав Смирнов, інженер надійності) додав сюди **лише докази бонуса** (розділ «Бонуси» в кінці файлу). Решту розділів (1-6) має заповнити відповідальний за документацію; у кожному вказано, що там має бути і де взяти матеріал. Коли розділ заповнено, цей блок і рядки «Заповнює…» треба прибрати.

## 1. Таблиця всіх знайдених проблем
*Заповнює: відповідальний за документацію. Джерело: [`scavenger-hunt.md`](scavenger-hunt.md), зведена таблиця (12 знахідок: категорія, файл, несправність, помилка, відмова, критичність) і таблиця «Статус виправлень».*

## 2. Оцінка критичності
*Заповнює: відповідальний за документацію. Джерело: стовпець «Критичність» у `scavenger-hunt.md`.*

## 3. До/після (фрагменти коду)
*Заповнює: відповідальний за документацію разом з інженером надійності (завдання #228, пункт «Передати фрагменти до/після для звіту»). Джерело: PR [#211](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/pull/211) (вкладка Files changed): виправлення знахідок №4, №7, №8, №11.*

## 4. Застосовані патерни надійності
*Заповнює: відповідальний за документацію. Джерело: опис PR #211 і таблиця «Статус виправлень» у `scavenger-hunt.md` (тайм-аути, обмежені повтори, guard clauses, логування, перевірка вхідних даних).*

## 5. Режими відмов і відновлення
*Заповнює: відповідальний за документацію. Для кожної виправленої проблеми: швидка чи безпечна відмова, що бачить користувач під час збою, як система повертається до норми. Джерело: опис PR #211, стовпець «Режим відмови».*

## 6. Які проблеми залишилися відкритими
*Заповнює: відповідальний за документацію. Джерело: рядки «Не виправлено» в таблиці «Статус виправлень» `scavenger-hunt.md` (№1, 2, 3, 5, 6, 9, 10, 12), а також issues `[Tech Debt]` [#213](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/issues/213)-[#221](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/issues/221).*

## Використання ШІ

Структуру шаблону (розділи 1-6) створено за допомогою Claude (Claude Code) за завданням Лаб 9. Фактичних даних у розділах 1-6 файл не містить; перевірка: звірка переліку розділів із текстом завдання. Розділ «Бонуси» див. нижче.

## Бонуси

### Тести надійності як обов'язкова перевірка PR

Тести з `tests/reliability/` запускаються в CI окремим кроком, і цей крок є обов'язковою перевіркою для `main`: PR не зливається за звичайними правилами, поки він не пройшов.

**Що зроблено:**
- Окремий workflow [`.github/workflows/reliability.yml`](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/blob/main/.github/workflows/reliability.yml) із job `reliability-tests`, який виконує `pytest tests/reliability -q`. Тригери: push і PR у `main`, ручний запуск.
- У `.github/workflows/ci.yaml` основний крок тестів запускається з `--ignore=tests/reliability`, щоб ці тести не виконувалися двічі.
- Залежності для job ставляться лише з [`requirements-ci.lock`](https://github.com/ukma-fin-ssdm-2026/YourPathUkma/blob/main/requirements-ci.lock) (`pip install --require-hashes`): інакше SonarCloud (правило S8544) валить Quality Gate, який теж обов'язковий. Правило записано в `AGENTS.md` §9.2.
- Статус `reliability-tests` додано до обов'язкових перевірок у ruleset «Require status check», який діє на `main`. Змінено 2026-11-08 о 14:06 за київським часом.

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

#### Хто пояснює бонус у відео
Владислав Смирнов, у відео Лаб 9: https://www.loom.com/share/1d113dcd9f7648f4af3bff23c260eb91 (також у `Labs/Lab09/video_Vladyslav.txt`).

#### Використання ШІ
Розділ «Бонуси» підготовлено за допомогою Claude (Claude Code). Workflow, lock-файл і додавання статусу до обов'язкових перевірок також зроблено з Claude Code. Перевірка: наявність файлів на `main`, список обов'язкових перевірок і стан ruleset звірено через GitHub API; результат обох прогонів взято зі сторінок Actions.
