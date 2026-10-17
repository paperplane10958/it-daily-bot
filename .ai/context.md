# Контекст проекта (актуальное состояние)

Обновлено: 2026-10-17

## Структура репо (с 2026-10-17 — два проекта в одном репо)
- `bot/` — телеграм-бот: src/bot (handlers, __main__, reader, progress, reminders), src/lessons (render, gamify, xp), tests (118), deploy/ (systemd-юнит + README деплоя), data/lessons.db (уроки + прогресс)
- `generator/` — контент-агент: src/agent (cli, generator, openrouter, roadmap, store, validator), docs/ (схема урока), tests (42), data/ (roadmaps + lessons.db генерации)
- Контракт между проектами — таблица `lessons` в SQLite: бот читает её read-only (`bot/src/bot/reader.py`), код генератора боту не нужен
- Общее: корневой `.env` (оба проекта находят через load_dotenv), venv в корне `.venv`, `.github/workflows/ci.yml` (матрица bot/generator), `.ai/`

## Статус
- [x] Инициализация репозитория и workflow
- [x] Решение по архитектуре контента: гибрид (roadmap.sh = скелет, ИИ-агент генерирует уроки пайплайном) — см. `.ai/decisions.md`
- [x] LLM-провайдер: OpenRouter (OpenAI-совместимый API, ключ в `.env`)
- [x] Схема урока v1: `generator/docs/lesson.schema.json` + дизайн + эталонный пример
- [x] Выбор стека: Python 3.13 + aiogram 3.31 (TDD: pytest, pytest-asyncio; venv через uv)
- [x] Валидатор уроков `validate_lesson` (`generator/src/agent/validator.py`)
- [x] Каркас бота, CI (GitHub Actions, матрица bot/generator), репо на GitHub (SSH)
- [x] Контент-агент: 26 тем backend-beginner сгенерированы (haiku-5.5, ~$0.08 все), автопубликация, SQLite
- [x] Выдача уроков в боте: /lesson (квиз-кнопки, XP), /progress, parse_mode=HTML + безопасный рендер
- [x] Геймификация: стрик, уровни (100 XP), карточки /cards
- [x] Ежедневные напоминания: /remind, фоновый тик, анти-спам
- [x] Деплой на VPS: systemd-сервис it-daily-bot, бот работает вживую (проверено пользователем)
- [x] Фикс квиза: multi-выбор в серверном состоянии quiz_state — смержен в main и на сервере
- [x] Inline-меню: /start = шапка со статистикой + кнопки-лаунчер, setMyCommands — ветка `feat/menu` (154 теста на тот момент)
- [x] Разделение репо на bot/ и generator/: бот читает базу read-only через LessonReader, базы разъехались, requirements/CI/README/deploy разделены — ветка `refactor/split-generator` (118 + 42 теста, коммит 4b3573c)
- [x] Смержено в main и запушено (merge `07231de`: feat/menu + split-generator) — шаг 1 гайда миграции
- [x] Гайд миграции сервера `bot/deploy/migration-2026-10.md` (+ фикс шага 3.1 `c93ef40`)
- [x] Сервер: шаги 2.1–2.5 и 3.1 выполнены пользователем (бэкап базы, pull, база в bot/data/, юнит перезаписан — ловушка пути из bot/, обойдена)
- [ ] **Сервер: докончить миграцию** — шаги 3.2 (ручная проверка из `~/it-daily-bot/bot`) → 4 (запуск сервиса + /start вживую); статус pytest 2.6 не подтверждён
- [ ] SRS-повторения карточек (интервалы, приоритет забытых) — если /cards зайдёт

## Ключевые факты окружения
- Сеть блокирует api.telegram.org напрямую → `BOT_PROXY=socks5://localhost:1080` в `.env` (на сервере не нужен — прямой доступ).
- OpenRouter блокирует python-urllib по TLS-отпечатку (403) → клиент на httpx (прокси берёт из env `ALL_PROXY`).
- `.env` в корне: BOT_TOKEN, OPENROUTER_API_KEY, `LLM_MODEL=anthropic/claude-haiku-5.5` (~$0.003/урок).
- Запуск: `cd bot && ../.venv/bin/python -m src.bot.__main__`; генерация: `cd generator && ../.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit N`. Один venv в корне: `uv pip install -r bot/requirements.txt -r generator/requirements.txt`.
- Тесты: bot 118 + generator 42 (venv общий, pytest.ini в каждой директории).
- Ветки: `main` (стабильная, на сервере), `feat/menu` (inline-меню), `refactor/split-generator` (разделение, на нём сейчас работаем).
- Базы: `bot/data/lessons.db` — то, что живёт у бота (уроки + progress + quiz_state + reminder_settings); `generator/data/lessons.db` — рабочая база генерации. Корневая `data/lessons.db` — старая копия, можно удалить.

## Следующий шаг
Докончить миграцию сервера по `bot/deploy/migration-2026-10.md`: шаг 2.6 (pytest из `~/it-daily-bot/bot`, ожидание 118 passed) → 3.2 (ручной запуск, /start вживую, Ctrl+C) → 4 (systemctl start + статус + журнал). После стабильной недели удалить `data/lessons.db.migration.bak`. Кандидаты: SRS-повторения карточек (или mini app, если зайдёт SRS), новые roadmap (linux, frontend), статистика/админка.

## Важные решения
См. `.ai/decisions.md`