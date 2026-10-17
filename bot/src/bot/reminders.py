"""Ежедневные напоминания: настройки пользователя и тик рассылки.

ReminderStore — таблица reminder_settings (user_id, hour, enabled) и
reminders_sent (user_id, day) в той же SQLite-базе, что уроки и прогресс.
Тик (run_reminder_tick) вызывается фоновым циклом из __main__: раз в минуту
смотрит, у кого наступил час напоминания, и шлёт тем, кто ещё не занимался
сегодня. Неудачная отправка тоже помечается — ретраи внутри часа превратились
бы в спам, а не в сервис.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reminder_settings (
    user_id INTEGER PRIMARY KEY,
    hour    INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS reminders_sent (
    user_id INTEGER NOT NULL,
    day     TEXT NOT NULL,
    PRIMARY KEY (user_id, day)
);
"""

REMINDER_TEXT = (
    "🔔 Время для урока!\n"
    "5–15 минут — и стрик 🔥 в безопасности.\n"
    "Продолжить: /lesson"
)


class ReminderStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def set(self, user_id: int, hour: int) -> None:
        """Включить напоминание в hour:00 (время местное у пользователя)."""
        self.conn.execute(
            """
            INSERT INTO reminder_settings (user_id, hour, enabled)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET hour = excluded.hour, enabled = 1
            """,
            (user_id, hour),
        )
        self.conn.commit()

    def disable(self, user_id: int) -> None:
        self.conn.execute(
            "UPDATE reminder_settings SET enabled = 0 WHERE user_id = ?", (user_id,)
        )
        self.conn.commit()

    def get(self, user_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT hour, enabled FROM reminder_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        return {"hour": row["hour"], "enabled": bool(row["enabled"])} if row else None

    def due_users(self, hour: int, today: str, studied_today: set[int] | None = None) -> list[int]:
        """id пользователей, которым пора напомнить в этот час.

        Не учитывая тех, кто уже занимался сегодня (studied_today), и тех,
        кому уже отправляли напоминание сегодня.
        """
        studied = studied_today or set()
        rows = self.conn.execute(
            """
            SELECT s.user_id FROM reminder_settings s
            WHERE s.enabled = 1 AND s.hour = ?
              AND s.user_id NOT IN (SELECT user_id FROM reminders_sent WHERE day = ?)
            ORDER BY s.user_id
            """,
            (hour, today),
        ).fetchall()
        return [r["user_id"] for r in rows if r["user_id"] not in studied]

    def mark_sent(self, user_id: int, day: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO reminders_sent (user_id, day) VALUES (?, ?)", (user_id, day)
        )
        self.conn.commit()


async def run_reminder_tick(bot, reminders, now: dt.datetime, studied_today: set[int] | None = None) -> int:
    """Один тик: отправить напоминания тем, у кого час настал. Вернуть число отправок."""
    hour, today = now.hour, now.date().isoformat()
    due = reminders.due_users(hour, today, studied_today)
    sent = 0
    for user_id in due:
        try:
            await bot.send_message(user_id, REMINDER_TEXT)
            sent += 1
        except Exception:  # Telegram недоступен/чат не существует
            pass
        # помечаем в любом случае: ретраи внутри часа превратились бы в спам
        reminders.mark_sent(user_id, today)
    return sent
