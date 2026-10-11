"""Тесты ежедневных напоминаний: настройки пользователя, выбор «кому напомнить», тик рассылки."""

import datetime as dt

import pytest

from src.bot.reminders import REMINDER_TEXT, ReminderStore, run_reminder_tick


@pytest.fixture
def store(tmp_path):
    s = ReminderStore(tmp_path / "lessons.db")
    yield s
    s.close()


def test_get_unset_returns_none(store):
    assert store.get(42) is None


def test_set_enables_at_hour(store):
    store.set(42, 9)
    r = store.get(42)
    assert r == {"hour": 9, "enabled": True}


def test_set_again_changes_hour(store):
    store.set(42, 9)
    store.set(42, 20)
    assert store.get(42)["hour"] == 20


def test_disable_keeps_hour(store):
    store.set(42, 9)
    store.disable(42)
    assert store.get(42) == {"hour": 9, "enabled": False}


def test_disable_unset_is_noop(store):
    store.disable(42)  # не должно бросить
    assert store.get(42) is None


def test_due_excludes_studied_today(tmp_path):
    from src.agent.store import LessonStore
    from src.bot.progress import ProgressStore

    db = tmp_path / "lessons.db"
    LessonStore(db).close()  # создаёт таблицу lessons
    rs = ReminderStore(db)
    ps = ProgressStore(db)
    rs.set(1, 9)
    rs.set(2, 9)
    ps.mark_completed(2, "l1", correct=4, total=4, xp=10)  # второй уже занимался
    due = rs.due_users(9, dt.date.today().isoformat(), studied_today={2})
    ps.close()
    rs.close()
    assert due == [1], "кто уже прошёл урок сегодня — не напоминаем"


def test_due_only_matching_hour_and_enabled(store):
    store.set(1, 9)
    store.set(2, 15)
    store.set(3, 9)
    store.disable(3)
    assert store.due_users(9, "2026-10-11") == [1]


def test_due_not_resent_same_day(store):
    store.set(1, 9)
    assert store.due_users(9, "2026-10-11") == [1]
    store.mark_sent(1, "2026-10-11")
    assert store.due_users(9, "2026-10-11") == []
    assert store.due_users(9, "2026-10-12") == [1], "на следующий день напомним снова"


# --- тик рассылки -----------------------------------------------------------------


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))


def test_tick_sends_to_due_and_marks(store):
    store.set(1, 9)
    bot = FakeBot()
    now = dt.datetime(2026, 10, 11, 9, 5)
    sent = run_reminder_tick_sync(bot, store, now)
    assert sent == 1
    assert bot.sent == [(1, REMINDER_TEXT)]
    assert store.due_users(9, "2026-10-11") == [], "после отправки не шлём повторно"


def run_reminder_tick_sync(bot, store, now):
    import asyncio

    return asyncio.run(run_reminder_tick(bot, store, now))


def test_tick_skips_wrong_hour_and_studied(tmp_path):
    from src.agent.store import LessonStore
    from src.bot.progress import ProgressStore

    db = tmp_path / "lessons.db"
    LessonStore(db).close()
    rs = ReminderStore(db)
    ps = ProgressStore(db)
    rs.set(1, 9)
    rs.set(2, 15)
    ps.mark_completed(2, "l1", correct=4, total=4, xp=10)
    bot = FakeBot()
    now = dt.datetime(2026, 10, 11, 9, 0)
    sent = run_reminder_tick_sync(bot, rs, now)
    assert sent == 1 and bot.sent[0][0] == 1
    ps.close()
    rs.close()


def test_tick_send_failure_does_not_crash(store):
    class BadBot:
        async def send_message(self, chat_id, text, **kwargs):
            raise RuntimeError("telegram down")

    store.set(1, 9)
    now = dt.datetime(2026, 10, 11, 9, 0)
    sent = run_reminder_tick_sync(BadBot(), store, now)
    assert sent == 0, "ошибка отправки не валит тик"
    assert store.due_users(9, "2026-10-11") == [], "неудачная отправка помечается, чтобы не спамить ретраями"
