# Bot — телеграм-бот IT Daily Bot

Выдаёт уроки из готовой базы: квиз по кнопкам, XP/уровни/стрики, карточки
терминов, ежедневные напоминания. Деплой на VPS — `deploy/README.md`.

## Запуск

```bash
# из корня репо: venv общий (.venv), секреты в корневом .env
cd bot
../.venv/bin/python -m src.bot.__main__
```

`BOT_TOKEN` обязателен (в корневом `.env`); `BOT_PROXY` — если api.telegram.org
недоступен напрямую; `LESSONS_DB` — путь к базе уроков (по умолчанию
`bot/data/lessons.db`).

## Тесты

```bash
cd bot && ../.venv/bin/python -m pytest tests/ -q
```

## Структура

- `src/bot/handlers.py` — команды (/start меню, /lesson, /progress, /cards,
  /remind, /help), квиз-колбэки
- `src/bot/__main__.py` — точка входа: polling, конфиг, фоновый тик напоминаний
- `src/bot/reader.py` — read-only чтение базы уроков генератора (контракт:
  таблица `lessons`, схема в `generator/src/agent/store.py`)
- `src/bot/progress.py` — прогресс/квиз-состояние (SQLite, та же база)
- `src/bot/reminders.py` — настройки и тик напоминаний
- `src/lessons/` — рендер урока в HTML Telegram, геймификация (XP/стрик/уровни)
- `tests/` — pytest
- `data/lessons.db` — база бота: уроки + прогресс пользователей (в .gitignore)

База уроков появляется здесь переносом из `generator/data/lessons.db`
(на сервер — `scp`, см. `deploy/README.md`). Reader открывает базу в
`mode=ro`: нет файла или таблицы `lessons` — RuntimeError при старте,
а не тихие «нет уроков».