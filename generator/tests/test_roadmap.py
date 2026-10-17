"""Тесты загрузчика roadmap: JSON roadmap.sh -> упорядоченный список тем."""

import json
import urllib.request
from pathlib import Path

import pytest

from src.agent.roadmap import fetch_roadmap, parse_topics, save_topics

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def roadmap_json() -> dict:
    """Урезанный fixture с реального roadmap.sh/backend-beginner.json."""
    return json.loads((FIXTURES / "roadmap-backend-beginner.json").read_text(encoding="utf-8"))


def test_parse_topics_extracts_topic_and_subtopic(roadmap_json):
    topics = parse_topics(roadmap_json)
    labels = [t["label"] for t in topics]
    assert "Pick a Language" in labels
    assert "Go" in labels
    assert len(topics) == 26  # topic + subtopic с непустым label


def test_parse_topics_orders_by_position(roadmap_json):
    topics = parse_topics(roadmap_json)
    # первый по y/x — JavaScript (subtopic выше всех), последний — Functional Testing
    assert topics[0]["label"] == "JavaScript"
    assert topics[-1]["label"] == "Functional Testing"
    # порядок монотонный по (y, x)
    keys = [(t["y"], t["x"]) for t in topics]
    assert keys == sorted(keys)


def test_parse_topics_has_roadmap_and_ids(roadmap_json):
    topics = parse_topics(roadmap_json)
    t = topics[0]
    assert t["roadmap_id"] == "backend-beginner"
    assert t["node_id"]  # непустой id ноды
    assert t["label"]


def test_parse_topics_skips_noise(roadmap_json):
    topics = parse_topics(roadmap_json)
    labels = {t["label"] for t in topics}
    # section/title/paragraph/button не попадают
    assert "Backend" not in labels  # title
    assert "Backend Developer Roadmap" not in labels  # button


def test_parse_topics_rejects_empty():
    with pytest.raises(ValueError):
        parse_topics({"nodes": []})


# --- сохранение ----------------------------------------------------------------


def test_save_topics_writes_json(tmp_path, roadmap_json):
    out = save_topics(roadmap_json, tmp_path)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["roadmap_id"] == "backend-beginner"
    assert len(data["topics"]) == 26
    assert data["topics"][0]["label"] == "JavaScript"


# --- сетевой слой (мокаем urllib) -----------------------------------------------


def test_fetch_roadmap_parses_json(monkeypatch, roadmap_json):
    payload = json.dumps(roadmap_json).encode()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return payload

    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: FakeResponse())
    data = fetch_roadmap("backend-beginner")
    assert data["slug"] == "backend-beginner"


def test_fetch_roadmap_404_raises(monkeypatch):
    import urllib.error

    def fake_urlopen(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="404"):
        fetch_roadmap("nonexistent-roadmap")