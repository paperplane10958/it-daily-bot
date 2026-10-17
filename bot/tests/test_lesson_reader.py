"""Тесты reader'а уроков: read-only доступ бота к базе генератора.

Бот не редактирует уроки — таблица lessons (схема — generator/src/agent/store.py)
для него контракт. Reader открывает базу в mode=ro и не создаёт таблиц:
нет базы/таблицы — понятная ошибка при старте, а не тихие пустые уроки.
"""

import json
import sqlite3

import pytest

from src.bot.reader import LessonReader


@pytest.fixture()
def db_path(tmp_path):
    """База с таблицей lessons в том виде, как её создаёт генератор."""
    path = tmp_path / "lessons.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE lessons (
            id          TEXT PRIMARY KEY,
            roadmap_id  TEXT NOT NULL,
            node        TEXT NOT NULL,
            category    TEXT,
            node_order  INTEGER,
            status      TEXT NOT NULL,
            difficulty  INTEGER,
            language    TEXT,
            xp          INTEGER,
            json        TEXT NOT NULL,
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    rows = [
        ("backend-beginner-javascript", 1, "published", {"id": "backend-beginner-javascript", "title": "JavaScript"}),
        ("backend-beginner-go", 3, "published", {"id": "backend-beginner-go", "title": "Go"}),
        ("backend-beginner-draft", 2, "review", {"id": "backend-beginner-draft", "title": "Draft"}),
    ]
    for lid, order, status, body in rows:
        conn.execute(
            "INSERT INTO lessons (id, roadmap_id, node, status, node_order, json) "
            "VALUES (?, 'backend-beginner', 'n', ?, ?, ?)",
            (lid, status, order, json.dumps(body, ensure_ascii=False)),
        )
    conn.commit()
    conn.close()
    return path


def test_get_lesson_returns_body(db_path):
    reader = LessonReader(db_path)
    lesson = reader.get_lesson("backend-beginner-javascript")
    assert lesson["title"] == "JavaScript"
    assert reader.get_lesson("no-such-id") is None
    reader.close()


def test_next_published_skips_seen_and_draft(db_path):
    reader = LessonReader(db_path)
    nxt = reader.next_published_lesson(["backend-beginner-javascript"])
    assert nxt["id"] == "backend-beginner-go"  # draft (review) не выдаётся
    assert reader.next_published_lesson(["backend-beginner-javascript", "backend-beginner-go"]) is None
    reader.close()


def test_all_published_count(db_path):
    reader = LessonReader(db_path)
    assert reader.all_published_count() == 2
    reader.close()


def test_missing_db_file_raises(tmp_path):
    with pytest.raises(RuntimeError, match="не найден"):
        LessonReader(tmp_path / "nope.db")


def test_db_without_lessons_table_raises(tmp_path):
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(path)  # база есть, таблицы lessons нет
    conn.close()
    with pytest.raises(RuntimeError, match="lessons"):
        LessonReader(path)


def test_reader_is_read_only(db_path):
    """Reader не должен создавать/менять ничего: открытие в mode=ro."""
    reader = LessonReader(db_path)
    reader.get_lesson("backend-beginner-javascript")
    reader.close()
    conn = sqlite3.connect(db_path)
    n = conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    conn.close()
    assert n == 3  # записи на месте, reader ничего не тронул