# Журнал работы агентов

## 2026-10-11 — Генерация всех 26 тем + выдача уроков в боте (/lesson, квиз, XP)

**Агент:** Hermes (GLM)
**Задача:** догенерировать roadmap backend-beginner, сделать выдачу уроков в боте (по выбору пользователя — сразу полный цикл: квиз-кнопки + XP + таблица progress).

### Сделано
- **Второй баг пайплайна (найден на живой генерации):** LLM каждый раз выдумывает новый id урока (`javascript-basics-intro` vs `javascript-intro-basics`), а дедуп-проверка `generate` сравнивала по id от LLM → перезапуск плодил дубликаты. Успел положить 3 (2 дубликата + Go). Фикс (TDD, `tests/test_cli.py`): `lesson_id()` = канонический `'<roadmap>-<slug>'`, назначает пайплайн (`lesson['id'] = lid` перед upsert), дедуп по нему же. База почищена: 3 урока под каноническими id, порядок = topics.json.
- **Генерация завершена:** 23 сгенерировано, 3 пропущено, 0 брак. В базе 26 уроков, все `published`, порядок 1..26 без дыр, средняя theory-секция 573 симв. Haiku-5.5: ~30 с/урок, 2 попытки потребовались лишь 4 темам (семантика квиза).
- **Выдача уроков (4 TDD-слайса, RED→GREEN каждый):**
  - `src/lessons/render.py` — рендер урока в HTML-сообщения: экранирование (кроме тела theory — там markdown от LLM), жадная упаковка материалов в сообщения ≤4000, `<pre>` для кода, ссылка-источники.
  - `src/bot/progress.py` — таблица `progress (user_id, lesson_id, correct, total, xp)` в той же SQLite, upsert (актуален последний результат).
  - `src/lessons/xp.py` — полный XP за идеальный квиз, половина с округлением вверх иначе, 0 за ноль.
  - `src/bot/handlers.py` — `/lesson` (следующий непройденный урок + первый вопрос), квиз без серверного состояния: битовая маска выбора + счёт верных путешествуют в callback_data; single = тап сразу отвечает, multi = toggle + «Выбрать все» + «Ответить»; после ответа вердикт + explanation, после последнего — итог и запись прогресса. `/progress` — пройдено/XP.
  - `src/bot/__main__.py` — `init_stores()` подключает `LessonStore`+`ProgressStore` к хендлерам (`runtime` dict, `LESSONS_DB` переопределяет путь).

### Изменённые файлы
- `src/agent/cli.py` (канонический id), `src/lessons/render.py`, `src/lessons/xp.py`, `src/bot/progress.py`, `src/bot/handlers.py`, `src/bot/__main__.py`, `tests/test_cli.py`, `tests/test_render.py`, `tests/test_xp.py`, `tests/test_progress.py`, `tests/test_lesson_handlers.py`, `tests/test_bot_handlers.py`, `.ai/context.md`

### Не доделано / риски
- Бот у пользователя работает со старым кодом — нужен перезапуск `python -m src.bot.__main__`, чтобы появились /lesson и /progress.
- Стрики/серии — следующий этап (данные для них уже есть: `updated_at` в progress).
- Квиз-состояние живёт в callback_data: если урок перегенерировать, старые кнопки в чатах дадут «Урок обновился — отправь /lesson заново» (обработано).
- `runtime` dict — простая зависимость; при росте можно заменить на aiogram middleware/контейнер.

### Как проверить
- `.venv/bin/python -m pytest tests/ -q` → 86 passed (проверено).
- `.venv/bin/python -c "import sqlite3; print(sqlite3.connect('data/lessons.db').execute(\"select count(*) from lessons where status='published'\").fetchone()[0])"` → 26 (проверено; утилиты sqlite3 в системе нет).
- Перезапустить бота → `/lesson` выдаёт урок, квиз по кнопкам начисляет XP, `/progress` показывает «1 из 26» после прохождения.

---

## 2026-10-11 — Платная модель haiku-5.5, фикс meta.model, первая генерация

**Агент:** Hermes (GLM)
**Задача:** перейти с openrouter/free на недорогую платную модель, перезапустить первую генерацию.

### Сделано
- **Модель:** `LLM_MODEL=anthropic/claude-haiku-5.5` в `.env`. Цены сняты с API OpenRouter 2026-10-11: ~$0.003/урок (≈$0.08 все 26 тем) при ~4k in / ~5k out токенов. Решение с альтернативами — в `.ai/decisions.md`.
- **Найден баг пайплайна:** промпт велит LLM оставить `meta.model` пустым («заполнит пайплайн»), а `_stamp_meta()` вызывался ПОСЛЕ `validate_lesson()` — каждый урок браковался («meta.model: '' should be non-empty»). Free-роутер до валидации не доходил (прерывался на reasoning), поэтому баг проявился только на платной модели.
- **Фикс (TDD):** `_stamp_meta` перенесён до валидации в `generate_lesson()`; тест `test_generate_lesson_stamps_meta_before_validation`; FakeClient получил атрибут `model`. 50 passed.
- **Первая реальная генерация удалась:** 2 урока (JavaScript, Pick a Language) → `data/lessons.db`, оба `published`. Haiku: 25–35 с на урок (free-роутер — минуты). Второй урок прошёл валидацию со 2-й попытки (семантика квиза). Качество проверено вручную: чистый русский, бытовые аналогии (ресторан = фронт/бэк), квиз корректен.

### Изменённые файлы
- `src/agent/generator.py`, `tests/test_generator.py`, `.ai/decisions.md`, `.ai/context.md`, `.env` (не в git: `LLM_MODEL=anthropic/claude-haiku-5.5`)

### Не доделано / риски
- Осталось 24 темы backend-beginner: `generate --limit 24` (~15 мин).
- Выдача уроков в боте (/lesson + прогресс пользователя) — следующий этап.

### Как проверить
- `.venv/bin/python -m pytest tests/ -q` → 50 passed.
- `python3 -c "import sqlite3; print(sqlite3.connect('data/lessons.db').execute('SELECT id,status FROM lessons').fetchall())"` → 2 урока published.

---

## 2026-10-11 — Реальная генерация: запуск бота, прокси, OpenRouter через httpx

**Агент:** Hermes (GLM)
**Задача:** автопубликация уроков, запуск бота у пользователя, первая генерация.

### Сделано
- **Автопубликация:** промпт генератора теперь ставит `status: "published"` (решение пользователя).
- **Бот запущен пользователем:** `@it_daily_paperplane_bot` отвечает, polling работает. Токен в `.env`.
- **Прокси-проблема решена:** в этой сети `api.telegram.org` напрямую недоступен (urllib/curl без прокси → network unreachable). В `~/.ssh/config` есть SOCKS-прокси `DynamicForward 1080` → в `.env` добавлено `BOT_PROXY=socks5://localhost:1080`; `build_bot()` в `src/bot/__main__.py` строит `AiohttpSession(proxy=...)` при заданном `BOT_PROXY`. Deps: `pysocks`, `python-socks` (+ в requirements.txt). Тесты build_bot/dispatcher добавлены (48).
- **OpenRouter блокирует python-urllib по TLS-отпечатку** (HTTP 403 "Access denied by security policy"; curl с тем же ключом/тела — 200). Фикс: `src/agent/openrouter.py` переписан на `httpx` (+ `httpx[socks]` в requirements); прокси httpx берёт из env (`ALL_PROXY=socks5://localhost:1080` уже задана в системе). httpx-запрос с ключом прошёл: 200, модель `nvidia/nemotron-3-ultra-550b-a55b:free` (это роутер `openrouter/free` из `.env` LLM_MODEL).
- `.env`: `BOT_TOKEN` задан, `OPENROUTER_API_KEY` задан, `LLM_MODEL=openrouter/free` (роутер free-моделей), `BOT_PROXY=socks5://localhost:1080`.

### Изменённые файлы
- `src/bot/__main__.py` (BOT_PROXY), `src/agent/openrouter.py` (httpx), `.env.example` (+BOT_PROXY), `requirements.txt` (+pysocks, python-socks, httpx, socksio), `tests/test_bot_handlers.py`, `tests/test_generator.py`, `src/agent/generator.py` (status=published)

### Не доделано / риски
- **Первая реальная генерация не завершена**: `generate --limit 2` был прерван пользователем (долго: free-модель + reasoning). Клиент уже рабочий (проверен коротким запросом). Перезапуск: `.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 2`. Возможно поставить модель пошустрее (`LLM_MODEL` в .env) или оставить openrouter/free.
- Сайт roadmap.sh блокирует urllib (403 security policy) — topics fetching через urllib работал ранее; если упадёт — тот же переход на httpx.
- Тесты: 49 passed на текущем main-состоянии ветки feat/content-agent.

### Как проверить
- `.venv/bin/python -m pytest tests/ -q` → 49 passed.
- Генерация: `.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 2` (несколько минут, free-роутер; в конце «итог: N сгенерировано»).
- База: `sqlite3 data/lessons.db "SELECT id, status, title FROM lessons;"`.

---

## 2026-10-11 — Контент-агент: roadmap → OpenRouter → SQLite

**Агент:** Hermes (GLM)
**Задача:** собрать пайплайн генерации уроков (branch feat/content-agent).

### Сделано
- Разведка roadmap.sh: структура нод в `https://roadmap.sh/<slug>.json` (topic/subtopic с label + position), контент тем — markdown в GitHub-репо `developer-roadmap/roadmaps/<id>/content/<slug>@<node_id>.md` (описание + ресурсы, короткие).
- `src/agent/roadmap.py` (TDD, 8 тестов): fetch/parse/save; порядок тем — по y/x позиции ноды; fixture — урезанный реальный JSON backend-beginner.
- `src/agent/openrouter.py`: минимальный клиент (stdlib, POST /chat/completions, json_object response_format), ошибки HTTP читаемые.
- `src/agent/generator.py` (TDD, 11 тестов): промпт v1 (все поля схемы, квиз 4 вопроса, русский, rookie-уровень), парсинг ответа (с ```-фенсом и без), ретрай при невалидном ответе, простановка meta.
- `src/agent/store.py` (TDD, 8 тестов): SQLite `data/lessons.db`, таблица lessons (денормализованные поля + json-тело), upsert с валидацией, next_published_lesson (по order, skip seen).
- `src/agent/cli.py`: команды `topics` (скачать темы) и `generate` (N уроков за запуск, skip существующих, тянуть markdown ноды как опору). Smoke на фейковом клиенте — урок кладётся в базу, order=1.
- Итого: 45 тестов зелёные.

### Изменённые файлы
- `src/agent/` (roadmap, openrouter, generator, store, cli), `tests/test_roadmap.py`, `tests/test_generator.py`, `tests/test_store.py`, `tests/fixtures/roadmap-backend-beginner.json`, `data/roadmaps/backend-beginner/topics.json`

### Не доделано / риски
- Реальная генерация не проверялась — нет OPENROUTER_API_KEY в .env. Запуск: вписать ключ, `.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 3`.
- id урока от LLM = slug темы, а не autonumber — при одинаковых label разных roadmap коллизия маловероятна (id включает roadmap_id).
- Стрик/XP/выдача уроков в боте — следующий этап.

### Как проверить
- `.venv/bin/python -m pytest tests/ -q` → 45 passed.
- `.venv/bin/python -m src.agent.cli topics --roadmap backend-beginner` → 26 тем.
- С ключом OpenRouter: `.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 3` → строки «✓ <тема>», уроки в `data/lessons.db`.
- Нюанс статусов: промпт ставит `status: review`; у эталонного примера `published`. Бот в будущем берёт только published — перед выдачей решаем: автопубликация после валидации или ручная.

---

## 2026-10-11 — Каркас бота + валидатор уроков (TDD)

**Агент:** Hermes (GLM)
**Задача:** собрать echo-бот (aiogram 3) и валидатор `validate_lesson` по TDD.

### Сделано
- Окружение: uv (без sudo, `~/.local/bin`), `.venv` (python 3.13), deps: aiogram 3.31, jsonschema, pytest, pytest-asyncio, python-dotenv. `requirements.txt` зафиксирован.
- TDD RED→GREEN: `src/lessons/validator.py` — JSON Schema + семантика квиза (kind↔correct, индексы в диапазоне, дубли) + лимит рендера Telegram (секция theory ≤ 4000 симв). 11 тестов.
- TDD RED→GREEN: `src/bot/handlers.py` (/start, /help, echo catch-all последним) + `src/bot/__main__.py` (polling, `BOT_TOKEN` из `.env`, внятная ошибка без токена). 7 тестов.
- `.env.example` с `BOT_TOKEN` / `OPENROUTER_API_KEY` / `LLM_MODEL`.
- README: запуск, тесты, структура.
- Итого `pytest tests/ -q`: 18 passed.

### Изменённые файлы
- `src/lessons/validator.py`, `src/bot/handlers.py`, `src/bot/__main__.py`, `tests/`, `requirements.txt`, `pytest.ini`, `.env.example`, `README.md`, `.ai/*`

### Не доделано / риски
- Реальный запуск с токеном не проверялся (токена нет) — проверить вручную: `/start` в чате с ботом.
- `.ai/decisions.md` не обновлён решением по стеку (Python 3.13 + aiogram 3 + pytest) — зафиксировать при следующей сессии.
- Git: работа шла в ветке `feat/echo-bot`, мёрж в `main` не делался.

### Как проверить
- `.venv/bin/python -m pytest tests/ -q` → 18 passed.
- `.venv/bin/python -m src.bot.__main__` без `.env` → падает с «BOT_TOKEN не задан…» (проверено).
- С токеном: `cp .env.example .env`, вписать токен, запустить, отправить боту `/start`.

---

## 2026-10-11 — OpenRouter + схема урока v1

**Агент:** Hermes (GLM)
**Задача:** закоммитить решение по контенту, зафиксировать LLM-провайдера, спроектировать схему урока.

### Сделано
- Закоммичены правки прошлого агента по архитектуре контента (`88cfa80`).
- Решение зафиксировано: LLM-провайдер — OpenRouter (OpenAI-совместимый API, `OPENROUTER_API_KEY` в `.env`).
- Спроектирована схема урока v1: JSON Schema (`docs/lesson.schema.json`), дизайн-док (`docs/lesson-schema.md`), эталонный урок-пример (`docs/examples/lesson-what-is-the-internet.json`).
- Проверено: пример валиден по схеме (jsonschema, 0 ошибок), семантика квиза (kind↔correct, индексы) и лимиты рендера Telegram — OK.

### Изменённые файлы
- `docs/lesson.schema.json`, `docs/lesson-schema.md`, `docs/examples/lesson-what-is-the-internet.json`
- `.ai/decisions.md`, `.ai/context.md`

### Не доделано / риски
- Валидатор `validate_lesson` (схема + семантика квиза) ещё не код — сейчас проверено скриптом ad-hoc.
- Эталонный урок написан вручную, не сгенерирован LLM — качество генерации проверим на пайплайне.

### Как проверить
- Через execute_code/venv (в системном python3 нет jsonschema): `jsonschema.Draft202012Validator(json.load(open('docs/lesson.schema.json'))).validate(json.load(open('docs/examples/lesson-what-is-the-internet.json')))` — без исключения = OK (проверено, 0 ошибок).

---

## 2026-10-11 — Решение по архитектуре контента

**Агент:** Zed (GLM)
**Задача:** учесть требование — контент должен искать/генерировать ИИ-агент autonomously.

### Сделано
- Зафиксировано решение в `.ai/decisions.md`: гибрид — roadmap.sh как скелет тем, ИИ-агент генерирует уроки пайплайном в базу, бот выдаёт готовое.
- Обновлён `.ai/context.md`.

### Следующий шаг
Выбор LLM-провайдера и схемы урока.

---

## 2026-10-11 — Инициализация проекта

**Агент:** Zed (GLM)
**Задача:** создать git-workflow и систему истории для ИИ-агентов.

### Сделано
- Создана структура `.ai/` (journal, decisions, context, templates)
- Написан `AGENTS.md` с правилами для агентов
- Инициализирован git-репозиторий

### Следующий шаг
Выбор стека и каркас телеграм-бота.
