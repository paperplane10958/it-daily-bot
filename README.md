# IT Daily Bot 🤖🎓

Телеграм-бот в стиле Duolingo: каждый день учит IT по [roadmap.sh](https://roadmap.sh).
С 2026-10 репо разделено на два проекта:

| Проект | Что делает |
|---|---|
| [`generator/`](generator/) | Контент-агент: темы roadmap.sh → генерация уроков через OpenRouter → SQLite |
| [`bot/`](bot/) | Телеграм-бот: выдача уроков, квиз, XP/уровни/стрики, карточки, напоминания, деплой на VPS |

## Контракт между проектами

Таблица `lessons` в SQLite: тело урока — колонка `json` (схема урока —
`generator/docs/lesson.schema.json`), поля выборки денормализованы в колонки
(определение таблицы — `generator/src/agent/store.py`). Бот читает базу
read-only (`bot/src/bot/reader.py`), писать и валидировать уроки он не умеет.

Поток уроков: генерация в `generator/data/lessons.db` → перенос в `bot/data/lessons.db`
(на сервер — `scp`, см. `bot/deploy/README.md`). Прогресс пользователей живёт
в базе бота (`bot/data/lessons.db`: таблицы `progress`, `quiz_state`,
`reminder_settings`) — перезаливая базу, делай бэкап.

## Окружение

- Python 3.13, зависимости через uv. Один venv на репо в корне (`.venv`):
  `uv venv .venv && uv pip install -r bot/requirements.txt -r generator/requirements.txt`
- Секреты в корневом `.env` (`BOT_TOKEN`, `OPENROUTER_API_KEY`, `LLM_MODEL`,
  `BOT_PROXY`) — оба проекта находят его через `load_dotenv()` (поиск вверх).
  Образцы: `.env.example` (корень, для бота) и `generator/.env.example`.
- `data/lessons.db` в корне не используется — базы у каждого проекта свои
  (`bot/data/`, `generator/data/`).

## Тесты

```bash
cd bot       && ../.venv/bin/python -m pytest tests/ -q
cd generator && ../.venv/bin/python -m pytest tests/ -q
```

## Workflow

- Git: `main` — стабильная ветка, фичи — через `feat/...` ветки, conventional commits.
- История работы ИИ-агентов: `.ai/journal.md` (правила см. в `AGENTS.md`).