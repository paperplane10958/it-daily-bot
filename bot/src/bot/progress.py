"""Прогресс пользователя: SQLite-таблица в той же базе, что уроки.

Ключ (user_id, lesson_id): повторное прохождение перезаписывает результат —
актуален последний. Прогресс — не в документе урока (docs/lesson-schema.md).
"""

import datetime as dt
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    user_id    INTEGER NOT NULL,
    lesson_id  TEXT NOT NULL,
    correct    INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    xp         INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, lesson_id)
);
CREATE INDEX IF NOT EXISTS idx_progress_user ON progress (user_id);

-- Состояние прохождения квиза (qidx — текущий вопрос, mask — выбранные
-- варианты multi-вопроса, ok — счёт верных ответов).
-- Раньше mask и ok кодировались в callback_data: два быстрых тапа приходили
-- от одной и той же старой клавиатуры и перезаписывали друг друга (вариант
-- «отваливался», submit шёл с неполной маской). Теперь тап складывает вариант
-- в состояние, submit читает его; счёт тоже не теряется при гонке тапов.
CREATE TABLE IF NOT EXISTS quiz_state (
    user_id   INTEGER NOT NULL,
    lesson_id TEXT NOT NULL,
    qidx      INTEGER NOT NULL,
    mask      INTEGER NOT NULL,
    ok        INTEGER NOT NULL,
    PRIMARY KEY (user_id, lesson_id)
);
"""


class ProgressStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def mark_completed(self, user_id: int, lesson_id: str, correct: int, total: int, xp: int) -> None:
        """Записать результат квиза (upsert: последний результат актуален)."""
        self.conn.execute(
            """
            INSERT INTO progress (user_id, lesson_id, correct, total, xp, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, lesson_id) DO UPDATE SET
                correct = excluded.correct,
                total = excluded.total,
                xp = excluded.xp,
                updated_at = excluded.updated_at
            """,
            (user_id, lesson_id, correct, total, xp),
        )
        self.conn.commit()

    def seen_lesson_ids(self, user_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT lesson_id FROM progress WHERE user_id = ?", (user_id,)
        ).fetchall()
        return [r["lesson_id"] for r in rows]

    def completed_count(self, user_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM progress WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["n"]

    def total_xp(self, user_id: int) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(xp), 0) AS s FROM progress WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["s"]

    def get_result(self, user_id: int, lesson_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT correct, total, xp FROM progress WHERE user_id = ? AND lesson_id = ?",
            (user_id, lesson_id),
        ).fetchone()
        return {"correct": row["correct"], "total": row["total"], "xp": row["xp"]} if row else None

    def last_completed_lesson_id(self, user_id: int) -> str | None:
        """id последнего завершённого урока пользователя (для повторного прохождения)."""
        row = self.conn.execute(
            """
            SELECT lesson_id FROM progress
            WHERE user_id = ?
            ORDER BY updated_at DESC, lesson_id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return row["lesson_id"] if row else None

    def activity_dates(self, user_id: int) -> list:
        """Дни (date), когда пользователь завершал уроки (по updated_at)."""
        rows = self.conn.execute(
            "SELECT DISTINCT substr(updated_at, 1, 10) AS day FROM progress WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return [dt.date.fromisoformat(r["day"]) for r in rows]

    def set_quiz_state(self, user_id: int, lesson_id: str, qidx: int, mask: int, ok: int) -> None:
        """Сохранить состояние прохождения квиза (текущий вопрос, выбор, счёт)."""
        self.conn.execute(
            """
            INSERT INTO quiz_state (user_id, lesson_id, qidx, mask, ok)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, lesson_id) DO UPDATE SET
                qidx = excluded.qidx, mask = excluded.mask, ok = excluded.ok
            """,
            (user_id, lesson_id, qidx, mask, ok),
        )
        self.conn.commit()

    def get_quiz_state(self, user_id: int, lesson_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT qidx, mask, ok FROM quiz_state WHERE user_id = ? AND lesson_id = ?",
            (user_id, lesson_id),
        ).fetchone()
        return {"qidx": row["qidx"], "mask": row["mask"], "ok": row["ok"]} if row else None

    def delete_quiz_state(self, user_id: int, lesson_id: str) -> None:
        self.conn.execute(
            "DELETE FROM quiz_state WHERE user_id = ? AND lesson_id = ?",
            (user_id, lesson_id),
        )
        self.conn.commit()

    def terms(self, user_id: int) -> list[tuple[str, str, str, str]]:
        """Термины (term, definition, lesson_id, lesson_title) из пройденных уроков.

        JOIN с таблицей lessons той же базы: ключевые термины документа урока
        -> карточки повторения.
        """
        rows = self.conn.execute(
            """
            SELECT p.lesson_id, l.json
            FROM progress p JOIN lessons l ON l.id = p.lesson_id
            WHERE p.user_id = ?
            ORDER BY l.node_order, p.lesson_id
            """,
            (user_id,),
        ).fetchall()
        out: list[tuple[str, str, str, str]] = []
        for row in rows:
            lesson = json.loads(row["json"])
            for t in lesson.get("key_terms", []):
                out.append((t["term"], t["definition"], row["lesson_id"], lesson["title"]))
        return out
