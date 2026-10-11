"""Генератор уроков: промпт -> OpenRouter -> parse -> validate_lesson.

Контракт по docs/lesson-schema.md: урок валиден или возвращаются ошибки;
невалидный ответ LLM ретраится max_retries раз.
"""

import datetime as dt
import json
import re

from src.lessons.validator import validate_lesson

# В schema минимум 3 вопроса; промптом задаём 4 — с запасом на отбраковку
QUIZ_MIN = 4

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "Ты — методист, который пишет короткие уроки по IT для телеграм-бота "
    "(стиль Duolingo: просто, по делу, с аналогиями из жизни). "
    "Ты отвечаешь СТРОГО одним JSON-объектом без markdown-обёрток."
)


def build_prompt(topic: str, roadmap_id: str, source_md: str = "") -> str:
    """Собрать промпт генерации урока по теме."""
    source_block = ""
    if source_md.strip():
        source_block = (
            "\n\n## Исходный материал (roadmap.sh)\n"
            "Используй как опору по фактам, не копируй дословно:\n\n"
            f"{source_md.strip()}\n"
        )

    return f"""Сгенерируй обучающий урок по теме «{topic}» из roadmap {roadmap_id}.

## Требования к формату
Верни РОВНО один JSON-объект по этой структуре (без ```-обёрток, без комментариев):

{{
  "schema_version": 1,
  "id": "<англ. slug из 3-5 слов, дефисы, только a-z0-9>",
  "roadmap": {{"roadmap_id": "{roadmap_id}", "node": "{topic}", "category": "<категория темы>", "order": 0}},
  "language": "ru",
  "difficulty": 1,
  "est_minutes": <целое 5-15>,
  "xp": <целое 10-30>,
  "status": "published",
  "title": "<заголовок урока на русском, до 100 симв.>",
  "hook": "<зачем это нужно: 1-2 предложения, цепляющие, до 400 симв.>",
  "objectives": ["<после урока ты сможешь...>", "..."],   // 2-3 штуки
  "theory": [                                             // 2-4 секции
    {{"heading": "<подзаголовок>", "body": "<2-4 абзаца простым языком, markdown, до 2500 симв.>"}}
  ],
  "key_terms": [{{"term": "<термин>", "definition": "<определение до 300 симв.>"}}],  // 3-6
  "examples": [{{"title": "...", "body": "<до 2000 симв.>", "code": "<опционально, в один блок>"}}],  // 1-2
  "practice": {{"prompt": "<мини-задание>", "hint": "<подсказка>", "solution": "<решение>"}},
  "quiz": [                                               // ровно {QUIZ_MIN} вопроса
    {{
      "kind": "single",
      "question": "<вопрос>",
      "options": ["<вариант 1>", "<вариант 2>", "<вариант 3>", "<вариант 4>"],
      "correct": [<индекс(ы) верного варианта с 0>],
      "explanation": "<почему, до 500 симв.>"
    }}
  ],
  "pitfalls": ["<частая ошибка новичка>"],                // 1-3
  "sources": [{{"title": "roadmap.sh — {roadmap_id}: {topic}", "url": "https://roadmap.sh/{roadmap_id}"}}],
  "meta": {{"generated_at": "<ISO 8601>", "model": "<оставь пустым, заполнит пайплайн>", "prompt_version": "{PROMPT_VERSION}"}}
}}

## Требования к содержанию
- Весь контент на русском языке (термины можно оставлять англ. в скобках).
- Уровень — новичок: без жаргона без расшифровки, аналогии из быта.
- Каждый блок theory — самостоятельное сообщение: законченная мысль, ≤ 2500 симв.
- В квизе {QUIZ_MIN} вопроса: mix kind single/multi; у single ровно 1 correct,
  у multi — 2+; индексы 0-based и всегда в пределах options.
- Неправильные варианты правдоподобные, но однозначно неверные для новичка.
- difficulty: 1 (совсем база) … 5 (продвинутая тема).{source_block}"""


def parse_lesson_response(raw: str) -> dict:
    """Вытащить JSON-объект урока из ответа LLM (с ```-обёрткой или без)."""
    text = raw.strip()
    # срезаем markdown-фенс, если LLM его добавил
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"ответ LLM не является валидным JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("ответ LLM должен быть JSON-объектом")
    return data


def _stamp_meta(lesson: dict, model: str) -> dict:
    meta = lesson.setdefault("meta", {})
    meta["generated_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    meta["model"] = model
    meta.setdefault("prompt_version", PROMPT_VERSION)
    return lesson


def generate_lesson(
    client,
    topic: str,
    roadmap_id: str,
    source_md: str = "",
    temperature: float = 0.7,
    max_retries: int = 1,
) -> tuple[dict, dict]:
    """Сгенерировать и провалидировать урок. Вернёт (lesson, meta).

    meta: {valid: bool, errors: list[str], attempts: int}
    Валидность не бросает исключений — пайплайн сам решает, что делать с браком.
    """
    prompt = build_prompt(topic=topic, roadmap_id=roadmap_id, source_md=source_md)
    errors: list[str] = []
    attempts = 0

    for attempt in range(max_retries + 1):
        attempts = attempt + 1
        raw = client.complete(prompt, system=SYSTEM_PROMPT, temperature=temperature)
        try:
            lesson = parse_lesson_response(raw)
        except ValueError as e:
            errors = [str(e)]
            continue
        # LLM не обязан заполнять meta (промпт велит оставить model пустой) —
        # проставляем ДО валидации, иначе пустая meta.model отбраковывает урок зря
        _stamp_meta(lesson, model=getattr(client, "model", "unknown"))
        errors = validate_lesson(lesson)
        if not errors:
            return lesson, {"valid": True, "errors": [], "attempts": attempts}
        # ошибка валидации: ретраим с тем же промптом (LLM видит только его)

    return {}, {"valid": False, "errors": errors, "attempts": attempts}