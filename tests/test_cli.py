"""Тесты CLI контент-агента (LLM и сеть замоканы)."""

import argparse
import json
from pathlib import Path

from src.agent import cli
from src.agent.generator import build_prompt

DOCS = Path(__file__).resolve().parents[1] / "docs"
EXAMPLE = json.loads((DOCS / "examples" / "lesson-what-is-the-internet.json").read_text(encoding="utf-8"))


def test_canonical_lesson_id():
    """Канонический id = roadmap-slug: стабильный ключ независимо от фантазий LLM."""
    assert cli.lesson_id("backend-beginner", "JavaScript") == "backend-beginner-javascript"
    assert cli.lesson_id("backend-beginner", "Pick a Language") == "backend-beginner-pick-a-language"


def test_cmd_generate_assigns_canonical_id(tmp_path, monkeypatch):
    """cmd_generate кладёт урок под каноническим id, а не под slug от LLM.

    Регрессия: LLM каждый раз выдумывает новый id -> перезапуск generate
    плодил дубликаты уроков (дедуп-проверка CLI сравнивает по каноническому id).
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")  # герметичность: не читать .env машины

    topics_dir = tmp_path / "roadmaps" / "backend-beginner"
    topics_dir.mkdir(parents=True)
    (topics_dir / "topics.json").write_text(
        json.dumps(
            {"roadmap_id": "backend-beginner", "topics": [{"label": "JavaScript", "node_id": "n1", "position": "1:0"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cli, "fetch_topic_content", lambda *a, **k: "")

    class FakeClient:
        model = "fake-model"

        def complete(self, *a, **k):
            return json.dumps(EXAMPLE, ensure_ascii=False)

    monkeypatch.setattr(cli, "OpenRouterClient", lambda api_key, model: FakeClient())

    captured: dict = {}

    class FakeStore:
        def get_lesson(self, lesson_id):
            captured.setdefault("checks", []).append(lesson_id)
            return None

        def upsert_lesson(self, lesson):
            captured["lesson"] = lesson

        def close(self):
            pass

    monkeypatch.setattr(cli, "LessonStore", lambda db_path: FakeStore())

    args = argparse.Namespace(roadmap="backend-beginner", limit=5, no_sources=True)
    assert cli.cmd_generate(args) == 0

    assert captured["checks"] == ["backend-beginner-javascript"], "дедуп должен проверять канонический id"
    assert captured["lesson"]["id"] == "backend-beginner-javascript", "урок должен храниться под каноническим id"
    assert captured["lesson"]["roadmap"]["order"] == 1
