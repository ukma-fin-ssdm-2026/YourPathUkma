# Scavenger hunt: ризики надійності в коді

Мета: знайти в коді `src/` місця, де система може тихо зламатися, зависнути або розкрити зайве. Кожну знахідку віднесено до категорії A–E.

| Категорія | Що шукали |
|-----------|-----------|
| A. Обробка помилок | відсутні `try/except`, надто широкий `except Exception`, приховані помилки, витік внутрішніх деталей |
| B. Зовнішні залежності | виклики БД/API без тайм-аутів, файлові операції без резервного шляху, неперевірений зовнішній вхід |
| C. Валідація вхідних даних | порожні значення, типи, граничні перевірки |
| D. Мовчазні збої | `None` без логування, порожні блоки обробки помилок, відсутність чіткої помилки |
| E. Продуктивність і блокування | довгі операції в обробнику, нескінченні або необмежені цикли, блокувальний ввід-вивід |

Метод: пошук за шаблонами (`except`, `pass`, `return None`, `timeout`, `sleep`, `int(`, `os.getenv`, `UploadFile`) і читання знайдених місць.

## Підсумок

| № | Кат. | Місце | Суть |
|---|------|-------|------|
| 1 | A | `src/api/routes/admin/sync.py:521` | `except Exception` без логування |
| 2 | A | `src/parser/sync.py:222` | текст внутрішнього винятку потрапляє в `error_message` |
| 3 | A | `src/parser/fetcher.py:89`, `:143` | широкий `except`; помилка закриття ресурсів маскує причину |
| 4 | B | `src/parser/fetcher.py:166` | запит до САЗ без явного тайм-ауту |
| 5 | B | `src/parser/fetcher.py:134` | запис файлу сесії без резервного шляху |
| 6 | B, C | `src/parser/config.py:29` | env-значення без перевірки типів і меж |
| 7 | C | `src/api/routes/deanery.py:226` | файл читається в пам'ять до перевірки розміру; тип за розширенням |
| 8 | D | `src/api/tokens.py:86` | `None` без логування |
| 9 | D | `src/parser/fetcher.py:140`, `src/parser/auth.py:37` | `except OSError: pass` |
| 10 | D, E | `src/api/routes/ai.py:77` | генерація `pending` ніколи не завершується |
| 11 | E | `src/parser/sync.py:99` | цикл по сторінках без верхньої межі й загального дедлайну |
| 12 | E | `src/api/routes/deanery.py:155` | обробка документа у фоні без ліміту часу |

---

## 1. Широкий `except Exception` без логування в масовому схваленні (A)

Файл: `src/api/routes/admin/sync.py:513-524`

```python
for item_id in dict.fromkeys(payload.item_ids):
    try:
        with db.begin_nested():
            _review_item(db, item_id, payload.decision, admin, ip)
    except ApiError as exc:
        skipped.append(SkippedItem(id=item_id, code=exc.code))
    except IntegrityError:
        skipped.append(SkippedItem(id=item_id, code="CONFLICT"))
    except Exception:
        skipped.append(SkippedItem(id=item_id, code="INTERNAL_ERROR"))
```

**Чому небезпечно.** Будь-який несподіваний виняток (помилка в `payload`, збій БД, баг у коді) перетворюється на рядок `INTERNAL_ERROR` у списку `skipped`. Ні стеку, ні причини ніде не залишається.

**Потенційний вплив.** Адмін бачить, що частину змін пропущено, але ні він, ні розробник не можуть зʼясувати чому. Системний баг може місяцями ховатися за «пропущеними» елементами.

## 2. Текст внутрішньої помилки зберігається й віддається користувачу (A)

Файл: `src/parser/sync.py:218-223`

```python
try:
    _execute(db, job, fetcher_factory or _default_fetcher)
except SyncFailure as exc:
    _fail(db, job_id, str(exc), exc.snapshot)
except Exception as exc:  # фонова задача не має залишити SyncJob у статусі running
    _fail(db, job_id, f"{type(exc).__name__}: {exc}")
```

**Чому небезпечно.** Для непередбачених винятків у `SyncJob.error_message` пишеться сирий текст (`{exc}`): це можуть бути фрагменти SQL, шляхи до файлів, імена таблиць. Поле показується адміністраторам через API. Самого стеку в логах немає, бо `logger.exception` не викликається.

**Потенційний вплив.** Витік внутрішньої будови системи в інтерфейс, а розробнику нічого діагностувати: повідомлення в БД обрізане до `ERROR_MAX` і без трасування.

## 3. Широкий `except` при запуску браузера та закриття ресурсів без захисту (A)

Файл: `src/parser/fetcher.py:86-97` та `:143-152`

```python
for attempt in range(retries + 1):
    try:
        return start()
    except Exception as exc:  # Playwright кидає різні типи винятків
        last = f"{type(exc).__name__}: {exc}"
        cleanup()
        ...
```

```python
def __exit__(self, exc_type, *_exc) -> None:
    try:
        if exc_type is None and self._context is not None:
            self._refresh_session()
    finally:
        for resource in (self._context, self._browser):
            if resource is not None:
                resource.close()
        if self._playwright is not None:
            self._playwright.stop()
```

**Чому небезпечно.** Перший блок перехоплює все, включно з помилками конфігурації, і зберігає лише рядок: оригінальний виняток і його стек губляться. У `__exit__` закриття не обгорнуте в `suppress` (на відміну від `_stop`): якщо `context.close()` кине виняток, `browser` і `playwright` залишаться незакритими, а початкова помилка обходу буде замаскована.

**Потенційний вплив.** Процеси Chromium можуть «осиротіти» й споживати памʼять, причина збою синхронізації стає нечитабельною.

## 4. Запит до зовнішнього сайту без явного тайм-ауту (B)

Файл: `src/parser/fetcher.py:161-169`

```python
def fetch(self, page: int) -> str:
    url = catalog_url(self._settings, page)

    def get() -> RawResponse:
        self._pause()
        response = self._context.request.get(url)
        return response.status, response.url, response.text()
```

**Чому небезпечно.** Тайм-аут не заданий ні тут, ні в `new_context`, тож вся надійність залежить від значення за замовчуванням у бібліотеці. Повторні спроби (`retries`) множать цей час.

**Потенційний вплив.** Якщо САЗ відповідає повільно, фонова задача синхронізації висить у статусі `running` хвилинами, займає потік і лише після перезапуску сервера позначається як перервана.

## 5. Запис файлу сесії без резервного шляху (B)

Файл: `src/parser/fetcher.py:132-141`

```python
def _refresh_session(self) -> None:
    state_path = self._settings.state_path
    tmp = state_path.with_name(state_path.name + ".tmp")
    self._context.storage_state(path=str(tmp))
    os.replace(tmp, state_path)
```

**Чому небезпечно.** Помилки диска, прав доступу чи блокування файлу (на Windows `os.replace` часто падає, якщо файл відкритий) не обробляються. Виняток вилітає з `__exit__`, а залишковий `.tmp` не прибирається.

**Потенційний вплив.** Повністю успішний обхід каталогу завершується збоєм через побічну операцію оновлення cookies; результати втрачаються, а залишки `.tmp` містять cookies сесії.

## 6. Змінні оточення без перевірки типу та меж (B, C)

Файл: `src/parser/config.py:25-33`

```python
academic_year=int(os.getenv("SAZ_ACADEMIC_YEAR", "2026")),
level=int(os.getenv("SAZ_LEVEL", "1")),
delay_s=float(os.getenv("SAZ_DELAY_S", "1.0")),
max_retries=int(os.getenv("SAZ_MAX_RETRIES", "3")),
```

**Чому небезпечно.** Некоректне значення (`SAZ_DELAY_S=abc`, порожній рядок) дає `ValueError` у момент виклику, тобто посеред фонової задачі, а не при старті застосунку. Граничних перевірок нема: від'ємна затримка змусить `_pause` не чекати зовсім, а `SAZ_MAX_RETRIES=-1` вимкне будь-які запити (цикл `range(0)`) і задача впаде з незрозумілим повідомленням.

**Потенційний вплив.** Помилка в `.env` проявляється пізно й невиразно; надто агресивний обхід (без пауз) може призвести до блокування IP у САЗ.

## 7. Завантаження документа: файл у памʼяті до перевірки розміру, тип за розширенням (C)

Файл: `src/api/routes/deanery.py:226-245`

```python
content = await file.read()
size = len(content)

if size > MAX_UPLOAD_BYTES:
    raise ApiError(413, "FILE_TOO_LARGE", "Файл більший за 10 МБ")
...
doc_mime = mime_map.get(file.content_type)
if not doc_mime:
    if file.filename and file.filename.endswith(".pdf"):
        doc_mime = db_enums.DocumentMimeType.PDF
    elif file.filename and file.filename.endswith(".docx"):
        doc_mime = db_enums.DocumentMimeType.DOCX
```

**Чому небезпечно.** Ліміт перевіряється після повного читання: надсилання дуже великого тіла все одно завантажує його в памʼять. Тип файлу визначається за заголовком `Content-Type` або розширенням (з урахуванням регістру: `.PDF` буде відхилено), вміст (магічні байти `%PDF`, `PK`) не перевіряється. Порожній файл (`size == 0`) теж проходить до запису в БД, де його зупиняє лише `CheckConstraint`, тобто користувач отримає 500 замість зрозумілої 4xx.

**Потенційний вплив.** Вичерпання памʼяті від кількох паралельних великих запитів; у БД і в майбутній парсер потрапляють файли, що лише прикидаються PDF/DOCX.

## 8. Валідація токена повертає `None` без жодного сліду (D)

Файл: `src/api/tokens.py:75-87`

```python
def decode_access_token(token: str) -> Optional[int]:
    try:
        claims = jwt.decode(...)
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError):
        return None
```

**Чому небезпечно.** Прострочений токен, неправильний підпис, підроблений `aud`/`iss` і зіпсоване поле `sub` неможливо відрізнити: усе зводиться до `None`, а потім до однакової 401 без запису в лог.

**Потенційний вплив.** Атаку підбору чи підробки токенів і масову помилку конфігурації (наприклад, змінений `JWT_SECRET` після деплою, коли всі користувачі раптом «розлогінені») неможливо помітити в моніторингу.

## 9. Порожній `except OSError: pass` на захисті файлу з cookies (D)

Файли: `src/parser/fetcher.py:138-141`, `src/parser/auth.py:35-38`

```python
try:
    os.chmod(state_path, 0o600)  # на Windows діє лише частково
except OSError:
    pass
```

**Чому небезпечно.** Це єдиний захід, який обмежує доступ до файлу з сесійними cookies САЗ (вони дають доступ від імені адміністратора). Якщо `chmod` не вдався, програма мовчки продовжує.

**Потенційний вплив.** Файл із діючою сесією залишається читабельним для інших користувачів системи, а команда про це не знає.

## 10. Генерація плану в статусі `pending` ніколи не завершується (D, E)

Файл: `src/api/routes/ai.py:76-105`

```python
active = db.scalar(
    select(PlanGeneration.id).where(
        PlanGeneration.student_id == profile.user_id,
        PlanGeneration.status == db_enums.GenerationStatus.PENDING,
    )
)
if active:
    raise ApiError(409, *_GENERATION_IN_PROGRESS)
...
generation = PlanGeneration(..., status=db_enums.GenerationStatus.PENDING)
db.add(generation)
db.commit()
```

**Чому небезпечно.** Запис створюється у стані `pending`, але в цьому модулі немає ні виконавця, ні тайм-ауту, ні очищення застарілих записів (на відміну від `SyncJob`, де є «перервані» задачі). Якщо виконавець колись впаде або не буде викликаний, запис залишиться `pending` назавжди.

**Потенційний вплив.** Студент отримує постійний `409 GENERATION_IN_PROGRESS` і більше не може запускати генерацію; фронтенд, що опитує статус, чекає вічно.

## 11. Обхід сторінок без верхньої межі та загального дедлайну (E)

Файл: `src/parser/sync.py:92-101`

```python
first_html = fetcher.fetch(1)
first = parser.parse(first_html)
...
pages = [first]
for number in range(2, (first.last_page or 1) + 1):
    pages.append(parser.parse(fetcher.fetch(number)))
```

**Чому небезпечно.** Кількість ітерацій задає значення `last_page`, яке парсер бере з HTML зовнішнього сайту. Якщо розмітка зміниться й число буде хибним (наприклад, 100000), цикл виконає стільки ж запитів, кожен із паузою `delay_s` і до `max_retries` повторів. Загального ліміту сторінок чи часу немає. Усе виконується блокувально (`time.sleep`) у потоці фонової задачі.

**Потенційний вплив.** Задача працює годинами, навантажує САЗ (ризик блокування IP), займає потік пулу запитів сервера.

## 12. Обробка документа у фоні без ліміту часу (E)

Файл: `src/api/routes/deanery.py:155-170`

```python
def process_document(document_id: int) -> None:
    with session_factory()() as db:
        document = db.get(DeaneryPlanDocument, document_id)
        ...
        try:
            parsed = extract_courses(document.content, document.mime_type)
            _store_courses(db, document, parsed)
            db.commit()
        except NotImplementedError as exc:
            db.rollback()
            _mark_failed(db, document_id, str(exc))
```

**Чому небезпечно.** Розбір PDF/DOCX (поки заглушка, але призначений для реальної реалізації) виконується синхронно у фоновому потоці без обмеження часу чи памʼяті, на користувацькому вході до 10 МБ. Спеціально сформований файл (zip-бомба в DOCX, надскладний PDF) може заблокувати потік. Також, якщо процес впаде під час обробки, документ назавжди залишиться в `pending`: механізму відновлення, як у `SyncJob`, нема.

**Потенційний вплив.** Вичерпання потоків і памʼяті сервера від одного користувача; документи, що «висять» без результату.

---

## Використання ШІ

Файл створено за допомогою Claude (Claude Code). Знахідки отримано пошуком за шаблонами та читанням відповідних фрагментів `src/`. Номери рядків і фрагменти звірено з кодом на момент створення; код не запускався і тести не виконувались. Потребує перегляду людиною.
