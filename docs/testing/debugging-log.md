# Журнал налагодження: Lab 06

## Симптом

Під час фази `[REFACTOR]` у вправі TDD (`classify_load_level`) команда

    pytest tests/test_load_levels.py -q

почала падати ще на збиранні тестів:

    ImportError: cannot import name 'classify_load_level' from partially initialized module
    'src.services.load_levels' (most likely due to a circular import)
    src/services/load_levels.py:10: in <module>
        from src.services.load_levels import classify_load_level

До цього всі 5 тестів були зеленими. Помилка з'являлась повторно, навіть після першого відкоту.
Додатковий сигнал: Pylance у VS Code показував `Import "pytest" could not be resolved`
для `src/services/load_levels.py`, хоча `pytest` у робочому модулі не потрібен.

## Причина

У `src/services/load_levels.py` опинився код тестового файлу (docstring тестів, `import pytest`,
`from src.services.load_levels import classify_load_level`). Через це модуль імпортував сам себе.

Як це з'ясовано (спостереження → гіпотеза → експеримент):

1. Трасування вказувало на рядок 10 у `load_levels.py`, де модуль імпортує власну функцію, тобто сам файл неправильний.
2. Гіпотеза: у файл потрапив чужий вміст. `git diff src/services/load_levels.py` підтвердив:
   рядки з `import pytest` і `@pytest.mark.parametrize` додано, а робочу реалізацію видалено.
3. Файл відкотили, але помилка повернулась. Отже, щось записувало неправильний вміст назад.
   Найімовірніше джерело: відкрита вкладка редактора зі старим вмістом, яка збереглась поверх файлу.
   Підтверджено тим, що після запису файлів через термінал проблема зникла.

Першопричина: ручне вставлення коду у відкриті вкладки редактора без перевірки, який саме файл відкритий.

## Виправлення

- Відкотили файл до закоміченої версії: `git restore src/services/load_levels.py`.
- Закрили вкладку без збереження і надалі записували файли командою `cat > <файл> << 'EOF'`.
- Перевірили: `pytest tests/test_load_levels.py -q` дає `12 passed`, повний прогін `pytest -q` дає `116 passed, 1 skipped`.

Регресійний захист: [`tests/test_load_levels.py`](../../tests/test_load_levels.py)
(`test_classify_load_level`, `test_hours_out_of_range_rejected`, коміт `5dcaa5f`).
Якщо модуль знову буде зіпсований, тести впадуть уже на збиранні, і це видно одразу.
Обмеження: ці тести ловлять зламаний модуль, але не причину (перезапис файлу). Від неї захищає процес, описаний нижче.

## Урок

- Перед кожним комітом дивитися `git diff --staged` і перевіряти, що змінено саме той файл.
- Не тримати відкритими вкладки зі застарілим вмістом; при сумніві писати файли через термінал.
- Ввімкнути `Files: Insert Final Newline` у VS Code і запускати `ruff check src tests` до пушу.
- Коли помилка повторюється після виправлення, шукати джерело, яке її відтворює, а не лише лагодити наслідок.

## Використання ШІ

Структуру журналу та аналіз причин підготовлено за допомогою Claude (Anthropic) за реальним перебігом
налагодження. Перевірка: відповідність виводу `pytest` та `git diff`, повний прогін тестів, ручний огляд.
