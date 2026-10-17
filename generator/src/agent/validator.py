"""Валидатор уроков: JSON Schema + семантика квиза + лимиты рендера Telegram.

Схема: docs/lesson.schema.json, дизайн: docs/lesson-schema.md.
Семантику kind/correct JSON Schema выразить не может — проверяем здесь.
"""

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

# Лимит Telegram на одно сообщение с запасом на префикс/кнопки
TG_MESSAGE_LIMIT = 4000

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
SCHEMA_PATH = DOCS_DIR / "lesson.schema.json"


@lru_cache
def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _format_path(path) -> str:
    """('theory', 0, 'body') -> 'theory[0].body'; пустой -> '<root>'."""
    parts = list(path)
    if not parts:
        return "<root>"
    out = str(parts[0])
    for part in parts[1:]:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def _schema_errors(lesson: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = []
    for err in validator.iter_errors(lesson):
        msg = err.message
        if len(msg) > 160:  # jsonschema вставляет сами значения — обрезаем
            msg = msg[:157] + "..."
        errors.append(f"{_format_path(err.absolute_path)}: {msg}")
    return errors


def _rendered_theory_len(section: dict) -> int:
    # Приблизительно как отрендерит бот: <b>заголовок</b> + пустая строка + тело
    return len(f"<b>{section['heading']}</b>\n\n{section['body']}")


def _quiz_errors(lesson: dict) -> list[str]:
    errors: list[str] = []
    for i, q in enumerate(lesson.get("quiz", [])):
        kind = q.get("kind")
        correct = q.get("correct", [])
        options = q.get("options", [])
        if len(correct) != len(set(correct)):
            errors.append(f"quiz[{i}]: дубли в correct: {correct}")
        if kind == "single" and len(correct) != 1:
            errors.append(
                f"quiz[{i}]: kind=single требует ровно 1 correct, найдено {len(correct)}"
            )
        if kind == "multi" and not correct:
            errors.append(f"quiz[{i}]: kind=multi требует хотя бы 1 correct")
        for idx in correct:
            if not 0 <= idx < len(options):
                errors.append(
                    f"quiz[{i}]: correct index {idx} вне диапазона options (0..{len(options) - 1})"
                )
    return errors


def validate_lesson(lesson, schema: dict | None = None) -> list[str]:
    """Проверить урок, вернуть список ошибок (пустой = валиден)."""
    if not isinstance(lesson, dict):
        return ["Урок должен быть JSON-объектом, получено: " + type(lesson).__name__]

    schema = schema if schema is not None else load_schema()
    errors = _schema_errors(lesson, schema)

    # Проверки, требующие целостной структуры урока
    if isinstance(lesson.get("theory"), list):
        for i, section in enumerate(lesson["theory"]):
            if isinstance(section, dict) and _rendered_theory_len(section) > TG_MESSAGE_LIMIT:
                errors.append(
                    f"theory[{i}]: отрендеренная секция не влезает в сообщение Telegram "
                    f"({_rendered_theory_len(section)} > {TG_MESSAGE_LIMIT})"
                )

    if isinstance(lesson.get("quiz"), list):
        errors.extend(_quiz_errors(lesson))

    return errors