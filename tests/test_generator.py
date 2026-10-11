"""Тесты клиента OpenRouter и генератора уроков (LLM замокан, сеть не дёргается)."""

import json
from pathlib import Path

import pytest

from src.agent.generator import build_prompt, generate_lesson, parse_lesson_response
from src.agent.openrouter import OpenRouterClient

DOCS = Path(__file__).resolve().parents[1] / "docs"
EXAMPLE = json.loads((DOCS / "examples" / "lesson-what-is-the-internet.json").read_text(encoding="utf-8"))


# --- промпт ---------------------------------------------------------------------


def test_build_prompt_contains_topic_and_constraints():
    prompt = build_prompt(topic="Git", roadmap_id="backend-beginner", source_md="# Git\n basics")
    assert "Git" in prompt
    assert "backend-beginner" in prompt
    assert "JSON" in prompt
    # ключевые ограничения из схемы урока: язык, лимиты, квиз
    assert "русском" in prompt
    assert "correct" in prompt
    assert "4" in prompt or "четыр" in prompt  # минимум 4 вопроса в квизе


def test_build_prompt_includes_source_material():
    prompt = build_prompt(topic="Git", roadmap_id="r", source_md="# Git basics")
    assert "# Git basics" in prompt


# --- парсинг ответа LLM ----------------------------------------------------------


def test_parse_lesson_response_extracts_json_from_markdown_fence():
    raw = "Вот урок:\n```json\n" + json.dumps(EXAMPLE, ensure_ascii=False) + "\n```"
    lesson = parse_lesson_response(raw)
    assert lesson["id"] == EXAMPLE["id"]


def test_parse_lesson_response_plain_json():
    raw = json.dumps(EXAMPLE, ensure_ascii=False)
    lesson = parse_lesson_response(raw)
    assert lesson["title"] == EXAMPLE["title"]


def test_parse_lesson_response_rejects_garbage():
    with pytest.raises(ValueError):
        parse_lesson_response("не JSON вообще")


def test_parse_lesson_response_rejects_non_object():
    with pytest.raises(ValueError):
        parse_lesson_response("[1,2,3]")


# --- генерация (LLM замокан) ------------------------------------------------------


class FakeClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, prompt: str, system: str = "", temperature: float = 0.7) -> str:
        self.calls.append({"prompt": prompt, "system": system, "temperature": temperature})
        return self.response


def test_generate_lesson_validates_and_metas():
    raw = json.dumps(EXAMPLE, ensure_ascii=False)
    client = FakeClient(raw)
    lesson, meta = generate_lesson(client, topic="Git", roadmap_id="backend-beginner", source_md="# Git")
    assert lesson["title"] == EXAMPLE["title"]
    assert meta["valid"] is True
    assert meta["errors"] == []
    assert len(client.calls) == 1


def test_generate_lesson_reports_validation_errors():
    bad = json.loads(json.dumps(EXAMPLE))
    bad["quiz"] = bad["quiz"][:2]  # меньше 3 вопросов — нарушение схемы
    raw = json.dumps(bad, ensure_ascii=False)
    client = FakeClient(raw)
    lesson, meta = generate_lesson(client, topic="Git", roadmap_id="r", source_md="")
    assert meta["valid"] is False
    assert meta["errors"], "должен вернуть список ошибок валидации"


def test_generate_lesson_retries_on_invalid_then_passes():
    bad = json.loads(json.dumps(EXAMPLE))
    bad["quiz"] = bad["quiz"][:2]
    good = json.dumps(EXAMPLE, ensure_ascii=False)
    responses = iter([json.dumps(bad, ensure_ascii=False), good])
    calls = []
    client = FakeClient(None)
    client.complete = lambda *a, **kw: (calls.append(1), next(responses))[1]
    lesson, meta = generate_lesson(client, topic="Git", roadmap_id="r", source_md="", max_retries=1)
    assert meta["valid"] is True
    assert len(calls) == 2


# --- клиент OpenRouter (структура, без сети) --------------------------------------


def test_openrouter_client_requires_key():
    with pytest.raises(ValueError):
        OpenRouterClient(api_key="")


def test_openrouter_client_builds_request(monkeypatch):
    captured = {}

    class FakeResp:
        status = 200

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "hello"}}]}
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        captured["body"] = json.loads(req.data.decode())
        return FakeResp()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = OpenRouterClient(api_key="test-key", model="test/model")
    out = client.complete("prompt text", system="sys")
    assert out == "hello"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"].get("Authorization") == "Bearer test-key"
    assert captured["body"]["model"] == "test/model"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "sys"}