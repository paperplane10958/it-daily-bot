# IT Daily Bot 🤖🎓

Телеграм-бот в стиле Duolingo: каждый день учит меня IT по [roadmap.sh](https://roadmap.sh), начиная с базы.

## Цель
- Ежедневные короткие уроки (5–15 мин) с геймификацией: стрики, XP, уровни.
- Контент на основе roadmap.sh (начинаем с Beginner roadmap: Internet, Linux, Git и т.д.).

## Стек
- Python 3.13, aiogram 3.x, SQLite
- Зависимости: uv (`uv pip install -r requirements.txt`)

## Запуск
```bash
cp .env.example .env   # вписать BOT_TOKEN от @BotFather
uv venv .venv          # один раз
uv pip install -r requirements.txt
.venv/bin/python -m src.bot.__main__
```

## Тесты
```bash
.venv/bin/python -m pytest tests/ -q
```

## Структура
- `src/bot/` — бот (обработчики, точка входа)
- `src/lessons/` — уроки: валидатор (`validate_lesson`)
- `docs/lesson.schema.json` — схема урока v1, `docs/lesson-schema.md` — дизайн
- `tests/` — pytest (валидатор, обработчики бота)

## Workflow
- Git: `main` — стабильная ветка, фичи — через `feat/...` ветки.
- История работы ИИ-агентов: `.ai/journal.md` (правила см. в `AGENTS.md`).
