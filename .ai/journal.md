# Журнал работы агентов

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
