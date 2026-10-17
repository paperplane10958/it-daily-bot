"""Тесты валидатора уроков: JSON Schema + семантика квиза + лимиты рендера."""

import json
import copy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.agent.validator import validate_lesson

DOCS = Path(__file__).resolve().parents[1] / "docs"
SCHEMA_PATH = DOCS / "lesson.schema.json"
EXAMPLE_PATH = DOCS / "examples" / "lesson-what-is-the-internet.json"


@pytest.fixture
def valid_lesson() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


# --- валидный урок проходит -------------------------------------------------


def test_valid_lesson_passes(valid_lesson):
    errors = validate_lesson(valid_lesson)
    assert errors == []


# --- семантика квиза --------------------------------------------------------


def test_single_with_multiple_correct_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    lesson["quiz"][0]["correct"] = [0, 1]
    errors = validate_lesson(lesson)
    assert errors, "single с двумя correct должен быть отклонён"
    assert any("quiz[0]" in e for e in errors)


def test_correct_index_out_of_range_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    lesson["quiz"][0]["correct"] = [9]
    errors = validate_lesson(lesson)
    assert errors, "correct вне диапазона options должен быть отклонён"


def test_duplicate_correct_indices_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    lesson["quiz"][0]["correct"] = [1, 1]
    errors = validate_lesson(lesson)
    assert any("дубли" in e.lower() for e in errors)


def test_multi_with_no_correct_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    # multi должен иметь хотя бы один корректный индекс; пустой список
    # нарушает схему (minItems 1), проверяем что валидатор это ловит
    lesson["quiz"][0]["kind"] = "multi"
    lesson["quiz"][0]["correct"] = []
    errors = validate_lesson(lesson)
    assert errors


# --- лимиты рендера Telegram -------------------------------------------------


def test_too_long_theory_section_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    lesson["theory"][0]["body"] = "х" * 4000
    errors = validate_lesson(lesson)
    assert any("не влезает в сообщение" in e for e in errors)


def test_theory_body_over_schema_max_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    lesson["theory"][0]["body"] = "х" * 2600
    errors = validate_lesson(lesson)
    assert any("theory[0]" in e for e in errors)


# --- битые входные данные ----------------------------------------------------


def test_missing_required_field_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    del lesson["quiz"]
    errors = validate_lesson(lesson)
    assert errors
    assert any("quiz" in e for e in errors)


def test_extra_field_rejected(valid_lesson):
    lesson = copy.deepcopy(valid_lesson)
    lesson["unknown_field"] = "x"
    errors = validate_lesson(lesson)
    assert errors


def test_non_dict_input_rejected():
    errors = validate_lesson(["not", "a", "dict"])
    assert errors
    assert "JSON-объект" in errors[0]


def test_schema_itself_is_valid():
    Draft202012Validator.check_schema(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))