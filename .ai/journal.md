# Журнал работы агентов

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
