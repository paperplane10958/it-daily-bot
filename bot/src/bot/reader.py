"""Read-only доступ бота к базе уроков генератора.

Таблица lessons — контракт с генератором (см. generator/src/agent/store.py):
тело урока в колонке json, поля выборки денормализованы. Бот уроки не пишет
и не валидирует — только читает published по порядку.

База открывается в mode=ro: бот никогда не создаёт/не мигрирует таблицы
генератора. Нет базы или таблицы — RuntimeError с путём (поймать при старте,
а не тихо отдавать «нет уроков»).
"""

import json
import sqlite3
from pathlib import Path


class LessonReader:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        if not self.db_path.is_file():
            raise RuntimeError(
                f"база уроков не найдена: {self.db_path} — "
                "скопируй data/lessons.db из generator/ (scp/перенос), см. README"
            )
        self.conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        if not self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lessons'"
        ).fetchone():
            self.conn.close()
            raise RuntimeError(
                f"в {self.db_path} нет таблицы lessons — это не база генератора уроков?"
            )

    def close(self) -> None:
        self.conn.close()

    def get_lesson(self, lesson_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT json FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        return json.loads(row["json"]) if row else None

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