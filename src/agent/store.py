"""SQLite-хранилище уроков контент-агента.

Схема по docs/lesson-schema.md: тело урока в колонке json,
поля выборки денормализованы в колонки. Прогресс пользователя — не здесь.
"""

import json
import sqlite3
from pathlib import Path

from src.lessons.validator import validate_lesson

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
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
CREATE INDEX IF NOT EXISTS idx_lessons_order ON lessons (roadmap_id, node_order);
CREATE INDEX IF NOT EXISTS idx_lessons_status ON lessons (status);
"""


class LessonStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def upsert_lesson(self, lesson: dict) -> int:
        """Валидирует и сохраняет урок (INSERT OR REPLACE). Возвращает 1."""
        errors = validate_lesson(lesson)
        if errors:
            raise ValueError(f"урок не валиден: {'; '.join(errors[:3])}")

        rm = lesson.get("roadmap", {})
        cur = self.conn.execute(
            """
            INSERT OR REPLACE INTO lessons
                (id, roadmap_id, node, category, node_order, status, difficulty, language, xp, json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                lesson["id"],
                rm.get("roadmap_id", ""),
                rm.get("node", ""),
                rm.get("category"),
                rm.get("order"),
                lesson["status"],
                lesson.get("difficulty"),
                lesson.get("language"),
                lesson.get("xp"),
                json.dumps(lesson, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return cur.rowcount

    def get_lesson(self, lesson_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT json FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        return json.loads(row["json"]) if row else None

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM lessons").fetchone()
        return row["n"]

    def all_published_count(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM lessons WHERE status = 'published'"
        ).fetchone()
        return row["n"]

    def next_published_lesson(self, seen_ids: list[str] | None = None) -> dict | None:
        """Ближайший по order опубликованный урок, которого нет в seen_ids."""
        params: list = ["published"]
        exclude = ""
        if seen_ids:
            marks = ",".join("?" for _ in seen_ids)
            exclude = f" AND id NOT IN ({marks})"
            params.extend(seen_ids)
        row = self.conn.execute(
            f"""
            SELECT json FROM lessons
            WHERE status = ?{exclude}
            ORDER BY node_order ASC, id ASC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return json.loads(row["json"]) if row else None