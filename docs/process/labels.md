# Мітки: значення та робочий процес

Цей документ описує всі мітки (labels), що використовуються в репозиторії, та те, як вони застосовуються протягом життєвого циклу задачі.

## 1. Мітки типу задачі

| Мітка | Опис (Description) |
|---|---|
| `type: bug` | Something isn't working |
| `type: feature` | New functionality |
| `type: docs` | Documentation |
| `type: refactor` | Improve code quality or structure |

## 2. Мітки пріоритету

| Мітка | Опис (Description) |
|---|---|
| `priority: high` | Critical, needs immediate attention |
| `priority: medium` | Default priority level |
| `priority: low` | Not urgent |

## 3. Мітки статусу

| Мітка | Опис (Description) | Як встановлюється |
|---|---|---|
| `status: in progress` | Currently being worked on | вручну виконавцем при взятті задачі |
| `status: needs review` | Ready for review | вручну виконавцем |
| `status: blocked` | Blocked by another task | вручну, за потреби |
| `status: done` | Task completed and closed | **автоматично**, воркфлоу `.github/workflows/label-sync.yml` при закритті issue |

Мітка `status: done` не встановлюється вручну. Вона додається автоматично разом з видаленням міток `status: in progress` та `status: needs review`, коли issue закривається (`issues: types: [closed]`). Таким чином критерій готовності задачі — це саме факт закриття issue, зафіксований через `gh issue edit`.

## 4. Службові мітки (стандартні GitHub + додаткові)

| Мітка | Опис (Description) |
|---|---|
| `bug` | Something isn't working *(дублює `type: bug`, стандартна мітка GitHub)* |
| `documentation` | Improvements or additions to documentation |
| `duplicate` | This issue or pull request already exists |
| `enhancement` | New feature or request |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention is needed |
| `invalid` | This doesn't seem right |
| `question` | Further information is requested |
| `wontfix` | This will not be worked on |
| `accessibility` | Barrier affecting people with disabilities |
| `feedback` | Зворотний зв'язок викладача; не входить в оцінку трекера |

## 5. Життєвий цикл задачі

1. Issue створюється, отримує мітки типу (`type: …`) та пріоритету (`priority: …`).
2. Виконавець бере задачу в роботу — вручну додає `status: in progress`.
3. Коли відкрито pull request і задача готова до перегляду — мітка вручну змінюється на `status: needs review`.
4. Якщо задачу заблоковано — додається `status: blocked` до вирішення блокера.
5. Після злиття PR і закриття issue воркфлоу [`label-sync.yml`](../../.github/workflows/label-sync.yml) автоматично видаляє мітки `status: in progress` / `status: needs review` та додає `status: done`.

Отже, задача вважається завершеною тоді й лише тоді, коли issue закрито і має мітку `status: done`.

## Використання ШІ

- **Що зроблено за допомогою ШІ:** ШІ використовувався під час підготовки цього документа. Який саме інструмент і яку частину тексту він створив, уточнює авторка документа (Дарʼя Чорна).
- **Як перевірено:** опис автоматичної зміни міток при закритті issue (розділи 3 і 5) звірено з `.github/workflows/label-sync.yml` (Claude Code, 2026-10-24): воркфлоу на `issues: closed` видаляє `status: in progress` та `status: needs review` і додає `status: done`. Решту документа (перелік міток і їхні описи) з налаштуваннями репозиторію на GitHub не звіряли.
