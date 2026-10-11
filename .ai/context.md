# Контекст проекта (актуальное состояние)

Обновлено: 2026-10-11

## Статус
- [x] Инициализация репозитория и workflow
- [x] Решение по архитектуре контента: гибрид (roadmap.sh = скелет, ИИ-агент генерирует уроки пайплайном) — см. `.ai/decisions.md`
- [x] LLM-провайдер: OpenRouter (OpenAI-совместимый API, ключ в `.env`)
- [x] Схема урока v1: `docs/lesson.schema.json` + `docs/lesson-schema.md` + эталонный пример
- [x] Выбор стека: Python 3.13 + aiogram 3.31 (TDD: pytest, pytest-asyncio; venv через uv)
- [x] Валидатор уроков `validate_lesson` (JSON Schema + семантика квиза + лимиты рендера)
- [x] Каркас бота (echo-бот: /start, /help, эхо) — **бот запущен пользователем, @it_daily_paperplane_bot работает**
- [x] CI: GitHub Actions — pytest на push в main и PR
- [x] Репозиторий на GitHub: paperplane10958/it-daily-bot (SSH)
- [x] Контент-агент: roadmap.sh → темы (26 тем backend-beginner), генерация через OpenRouter, SQLite — **клиент OpenRouter переведён на httpx (urllib блокируется 403)**, автопубликация (status=published)
- [x] Первая реальная генерация уроков: 2 урока в базе (`data/lessons.db`, published, модель haiku-5.5)
- [x] Генерация всех 26 тем backend-beginner (0 брак, канонические id `<roadmap>-<slug>`, дедуп по ним же)
- [x] Выдача уроков в боте: /lesson (контент + квиз-кнопки, XP), /progress, таблица progress в SQLite
- [x] parse_mode=HTML по умолчанию + безопасный рендер LLM-текста (markdown -> теги, escape)
- [x] Геймификация: стрик, уровни (100 XP), карточки терминов /cards (без SRS)
- [x] Ежедневные напоминания: /remind (кнопки 7/12/19/22), фоновый тик раз в минуту, анти-спам (1/день), пропускает занимавшихся сегодня
- [ ] Пользователь проверяет бота вживую: /lesson, /progress, /cards, /remind в @it_daily_paperplane_bot (нужен перезапуск бота)
- [ ] SRS-повторения карточек (интервалы, приоритет забытых) — если /cards зайдёт

## Ключевые факты окружения
- Сеть блокирует api.telegram.org напрямую → `BOT_PROXY=socks5://localhost:1080` (прокси из `~/.ssh/config`, DynamicForward 1080) в `.env`.
- OpenRouter блокирует python-urllib по TLS-отпечатку (403) → клиент на httpx (прокси берёт из env `ALL_PROXY`).
- `.env`: BOT_TOKEN, OPENROUTER_API_KEY заданы; `LLM_MODEL=anthropic/claude-haiku-5.5` (~$0.003/урок, ~30 с). Тесты: 129 passed.
- Ветки: `main` (бот+валидатор+CI), `feat/content-agent` (контент-агент, актуальная работа).

## Следующий шаг
Перезапустить бота и проверить вживую: `/lesson`, `/progress`, `/cards`, `/remind` (напоминание сработает, только пока бот запущен — полная ценность после деплоя на VPS). Дальше: деплой на VPS (systemd-сервис, .env, БД) или SRS-повторения карточек.

## Важные решения
См. `.ai/decisions.md`
