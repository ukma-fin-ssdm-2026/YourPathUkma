# Звіт про аналіз якості коду в SonarCloud (YourPathUkma)

**Проєкт:** YourPathUkma (REST API + вебфронтенд)
**Відповідальні ролі:** Quality Lead
**Інструмент:** SonarCloud (проєкт `ukma-fin-ssdm-2026_YourPathUkma`)
**Станом на:** TODO
**Версія / коміт аналізу:** TODO

> Шаблон звіту. Значення `TODO` потрібно заповнити за даними з SonarCloud;
> у цьому файлі їх не вигадано.

## 1. Загальна інформація

| Параметр | Значення |
|---|---|
| Репозиторій | ukma-fin-ssdm-2026/YourPathUkma |
| Гілка / PR аналізу | TODO |
| Дата аналізу | TODO |
| Quality Gate | TODO (Passed / Failed) |
| Кількість рядків коду (LoC) | TODO |

## 2. Підсумок за категоріями

| Категорія | Кількість проблем | Рейтинг (A–E) | Висновок |
|---|---|---|---|
| Security | 14 | TODO | Усі проблеми в CI/CD workflow; 1 Blocker (script injection) |
| Reliability | TODO | TODO | TODO |
| Maintainability | TODO | TODO | TODO |
| Duplications | TODO % | — | TODO |

Додатково: Security Hotspots — TODO, Coverage — TODO %, Technical Debt — TODO.

## 3. Security

**Показники:** проблем Security — 14 (Blocker 1, High 1, Medium 12); Vulnerabilities — TODO; Security Hotspots (переглянуто / усього) — TODO; рейтинг — TODO.

**Результати аналізу:**

Усі 14 проблем категорії Security стосуються CI/CD-конфігурації (`.github/workflows/`), коду застосунку вони не зачіпають. За severity: Blocker — 1, High — 1, Medium — 12. Найкритичніша — ін'єкція скрипта через `inputs.paths` у `mutation.yml`. Решта — незафіксовані версії залежностей, встановлення без `--only-binary :all:` / `--ignore-scripts` та action без фіксації за SHA. Орієнтовна трудомісткість за оцінкою Sonar: 1 год на ін'єкцію, по 30 хв на SHA, PASSWORD і `--ignore-scripts`, по 1 год на кожну з решти.

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | `.github/workflows/mutation.yml` L36 | script injection (CWE) | Blocker | `inputs.paths` потрапляє напряму в `run`; значення задає той, хто запускає workflow | Передати вираз через змінну середовища (`env:`) і використовувати її в `run` | Open |
| 2 | `.github/workflows/deploy-api-docs.yml` L37 | full commit SHA (CWE) | High | Залежність підключена не за повним SHA коміту | Зафіксувати action за повним SHA коміту | Open |
| 3 | `.github/workflows/ci.yaml` L21 | hard-coded credential (CWE) | Medium | Виявлено «PASSWORD», можливий захардкоджений секрет | Перевірити, що це не реальний секрет; за потреби винести в GitHub Secrets | Open |
| 4 | `.github/workflows/ci.yaml` L38 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 5 | `.github/workflows/ci.yaml` L38 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 6 | `.github/workflows/ci.yaml` L40 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 7 | `.github/workflows/ci.yaml` L40 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 8 | `.github/workflows/ci.yaml` L42 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 9 | `.github/workflows/ci.yaml` L42 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 10 | `.github/workflows/ci.yaml` L70 | npm: `--ignore-scripts` (CWE) | Medium | Без `--ignore-scripts` під час встановлення пакетів запускаються lifecycle-скрипти | Додати `--ignore-scripts` | Open |
| 11 | `.github/workflows/deploy-api-docs.yml` L31 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 12 | `.github/workflows/deploy-api-docs.yml` L31 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |
| 13 | `.github/workflows/mutation.yml` L30 | pip: `--only-binary :all:` (CWE) | Medium | Відсутність `--only-binary :all:` дозволяє виконання setup-скриптів | Додати `--only-binary :all:` або підтвердити безпечність | Open |
| 14 | `.github/workflows/mutation.yml` L30 | незафіксовані залежності | Medium | Залежності без зафіксованих версій | Зафіксувати версії (lock-файл / `==`) | Open |

## 4. Reliability

**Показники:** Bugs — TODO; рейтинг — TODO.

**Результати аналізу:**

TODO

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | TODO | TODO | TODO | TODO | TODO | TODO |

## 5. Maintainability

**Показники:** Code Smells — TODO; Technical Debt — TODO; Debt Ratio — TODO %; рейтинг — TODO.

**Результати аналізу:**

TODO

| # | Файл | Правило | Severity | Опис | Рішення | Статус |
|---|---|---|---|---|---|---|
| 1 | TODO | TODO | TODO | TODO | TODO | TODO |

## 6. Duplications

**Показники:** Duplicated Lines Density — TODO %; Duplicated Blocks — TODO; Duplicated Files — TODO.

**Результати аналізу:**

TODO

| # | Файли з дублюванням | Кількість рядків | Опис | План усунення | Статус |
|---|---|---|---|---|---|
| 1 | TODO | TODO | TODO | TODO | TODO |

## 7. Висновки та план рефакторингу

TODO

## Використання ШІ

Структуру шаблону (шапка, розділи за категоріями) створено за допомогою Claude Code.
Фактичних даних SonarCloud файл не містить; перевірка — лише перегляд структури.
