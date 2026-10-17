# Generator — контент-агент IT Daily Bot

Пайплайн: темы roadmap.sh → генерация уроков через OpenRouter → SQLite
(`data/lessons.db`). Схема урока v1 — `docs/lesson.schema.json`, дизайн —
`docs/lesson-schema.md`, эталон — `docs/examples/`.

## Команды

```bash
cd generator
../.venv/bin/python -m src.agent.cli topics --roadmap backend-beginner
../.venv/bin/python -m src.agent.cli generate --roadmap backend-beginner --limit 5
```

- `OPENROUTER_API_KEY` и `LLM_MODEL` — из корневого `.env` (образец:
  `generator/.env.example`). Прокси для httpx берётся из системной `ALL_PROXY`
  (OpenRouter блокирует python-urllib по TLS-отпечатку).
- Канонический id урока `<roadmap>-<slug>` назначает пайплайн (не LLM) —
  по нему дедуп: перезапуск `generate` пропускает уже сгенерированные темы.
- Прогресс пользователей в этой базе не живёт: базу бота (`bot/data/lessons.db`)
  обновляй переносом сгенерированных уроков (на сервер — `scp`,
  см. `bot/deploy/README.md`).

## Тесты

```bash
cd generator && ../.venv/bin/python -m pytest tests/ -q
```

## Структура

- `src/agent/cli.py` — CLI (`topics`, `generate`)
- `src/agent/generator.py` — промпт, парсинг, ретрай при невалидном ответе
- `src/agent/openrouter.py` — клиент OpenRouter (httpx)
- `src/agent/roadmap.py` — fetch/parse тем roadmap.sh
- `src/agent/store.py` — SQLite-хранилище уроков (определение таблицы `lessons`
  — это контракт с ботом)
- `src/agent/validator.py` — `validate_lesson`: JSON Schema + семантика квиза +
  лимиты рендера Telegram
- `tests/` — pytest (LLM и сеть замоканы)
- `data/roadmaps/<id>/topics.json` — скачанные темы, `data/lessons.db` — база уроков