# Контекст проекта (актуальное состояние)

Обновлено: 2026-10-11

## Статус
- [x] Инициализация репозитория и workflow
- [x] Решение по архитектуре контента: гибрид (roadmap.sh = скелет, ИИ-агент генерирует уроки пайплайном) — см. `.ai/decisions.md`
- [x] LLM-провайдер: OpenRouter (OpenAI-совместимый API, ключ в `.env`)
- [x] Схема урока v1: `docs/lesson.schema.json` + `docs/lesson-schema.md` + эталонный пример
- [x] Выбор стека: Python 3.13 + aiogram 3.31 (TDD: pytest, pytest-asyncio; venv через uv)
- [x] Валидатор уроков `validate_lesson` (JSON Schema + семантика квиза + лимиты рендера) — 11 тестов
- [x] Каркас бота (echo-бот: /start, /help, эхо) — 7 тестов
- [x] CI: GitHub Actions — pytest на push в main и PR
- [x] Репозиторий на GitHub: paperplane10958/it-daily-bot (SSH)
- [x] Контент-агент: roadmap.sh → темы (26 тем backend-beginner), генерация через OpenRouter, SQLite — 45 тестов, реальная генерация ждёт ключ
- [ ] Выдача уроков в боте + прогресс пользователя (что пройдено)
- [ ] Геймификация (стрики, XP)
- [ ] Автопубликация или ревью уроков (статусы draft/review/published)

## Следующий шаг
Выдача уроков в боте: /lesson берёт `next_published_lesson` из SQLite, рендерит theory секциями, квиз кнопками. Нужен ключ OPENROUTER_API_KEY в `.env`, чтобы наполнить базу реальными уроками.

## Важные решения
См. `.ai/decisions.md`
