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
- [ ] **Первая реальная генерация уроков** (клиент проверен, `generate --limit 2` прерван на полпути — перезапустить)
- [ ] Выдача уроков в боте (/lesson + прогресс пользователя)
- [ ] Геймификация (стрики, XP)

## Ключевые факты окружения
- Сеть блокирует api.telegram.org напрямую → `BOT_PROXY=socks5://localhost:1080` (прокси из `~/.ssh/config`, DynamicForward 1080) в `.env`.
- OpenRouter блокирует python-urllib по TLS-отпечатку (403) → клиент на httpx (прокси берёт из env `ALL_PROXY`).
- `.env`: BOT_TOKEN, OPENROUTER_API_KEY заданы; `LLM_MODEL=openrouter/free` (free-роутер, медленный — nvidia/nemotron...:free). Тесты: 49 passed.
- Ветки: `main` (бот+валидатор+CI), `feat/content-agent` (контент-агент, актуальная работа).

## Следующий шаг
Перезапустить генерацию: `.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 2` (займёт минуты из-за free-роутера). Затем выдача уроков в боте: /lesson берёт `next_published_lesson`, рендерит theory секциями, квиз кнопками.

## Важные решения
См. `.ai/decisions.md`
