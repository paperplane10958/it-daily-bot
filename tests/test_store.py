"""Тесты хранилища уроков (SQLite)."""

import json
from pathlib import Path

import pytest

from src.agent.store import LessonStore

DOCS = Path(__file__).resolve().parents[1] / "docs"
EXAMPLE = json.loads((DOCS / "examples" / "lesson-what-is-the-internet.json").read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path):
    return LessonStore(tmp_path / "test.db")


def test_upsert_lesson(store):
    n = store.upsert_lesson(EXAMPLE)
    assert n == 1
    got = store.get_lesson(EXAMPLE["id"])
    assert got is not None
    assert got["title"] == EXAMPLE["title"]
    assert got["status"] == "published"


def test_upsert_replaces_existing(store):
    store.upsert_lesson(EXAMPLE)
    changed = json.loads(json.dumps(EXAMPLE))
    changed["title"] = "Новое название"
    store.upsert_lesson(changed)
    got = store.get_lesson(EXAMPLE["id"])
    assert got["title"] == "Новое название"
    # дублей нет
    assert store.count() == 1


def test_upsert_rejects_invalid_lesson(store):
    bad = json.loads(json.dumps(EXAMPLE))
    bad["quiz"] = bad["quiz"][:2]
    with pytest.raises(ValueError, match="валид"):
        store.upsert_lesson(bad)


def test_next_published_lesson_by_order(store):
    l1 = json.loads(json.dumps(EXAMPLE))
    l1["roadmap"]["order"] = 1
    l2 = json.loads(json.dumps(EXAMPLE))
    l2["id"] = "internet-second-lesson"
    l2["title"] = "Второй урок"
    l2["roadmap"]["order"] = 2
    l3 = json.loads(json.dumps(EXAMPLE))
    l3["id"] = "internet-draft-lesson"
    l3["title"] = "Черновик"
    l3["roadmap"]["order"] = 0
    l3["status"] = "draft"

    for l in (l3, l1, l2):
        store.upsert_lesson(l)

    nxt = store.next_published_lesson()
    assert nxt["id"] == "internet-what-is-the-internet"  # order=1, draft пропущен


def test_next_published_lesson_skips_seen(store):
    l1 = json.loads(json.dumps(EXAMPLE))
    l2 = json.loads(json.dumps(EXAMPLE))
    l2["id"] = "internet-second"
    l2["roadmap"]["order"] = 2
    store.upsert_lesson(l1)
    store.upsert_lesson(l2)
    nxt = store.next_published_lesson(seen_ids=["internet-what-is-the-internet"])
    assert nxt["id"] == "internet-second"


def test_next_published_lesson_none_when_all_seen(store):
    store.upsert_lesson(EXAMPLE)
    assert store.next_published_lesson(seen_ids=[EXAMPLE["id"]]) is None


def test_all_published_count(store):
    assert store.all_published_count() == 0
    store.upsert_lesson(EXAMPLE)
    assert store.all_published_count() == 1


def test_db_creates_parent_dirs(tmp_path):
    db_path = tmp_path / "sub" / "dir" / "db.sqlite"
    LessonStore(db_path)
    assert db_path.exists()