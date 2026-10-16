"""Тесты callback-кнопок меню: тап по кнопке открывает соответствующий экран.

Меню — лаунчер: кнопки отправляют НОВОЕ сообщение (message.answer), экран
открывается свежим сообщением под меню; само меню остаётся сверху как якорь.
Состояние в callback_data не ездит (урок по префиксному колбэку не выбирается),
поэтому гонок быстрых тапов здесь нет в принципе.
"""

import json
from pathlib import Path

import pytest

from src.bot.handlers import MENU_CALLBACKS, answer_callback
from tests.test_lesson_handlers import EXAMPLE, FakeCallback, FakeMessage, stores

MENU_ACTIONS = {
    "m:lesson": None,
    "m:progress": None,
    "m:cards": None,
    "m:remind": None,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("data", sorted(MENU_ACTIONS))
async def test_menu_button_opens_screen(data):
    """Каждая кнопка меню открывает свой экран: новое сообщение с контентом."""
    lessons, progress = stores()
    reminders = FakeReminderStore()
    cb = FakeCallback(data)
    await answer_callback(cb, lessons, progress, reminders)
    assert cb.message.sent, f"{data} должен открыть экран"


@pytest.mark.asyncio
async def test_menu_lesson_sends_quiz():
    """«Урок дня» выдает урок с квизом — тот же сценарий, что /lesson."""
    lessons, progress = stores()
    cb = FakeCallback("m:lesson")
    await answer_callback(cb, lessons, progress)
    assert any("❓" in t for _, t, _ in cb.message.sent), "квиз идёт после урока"


@pytest.mark.asyncio
async def test_menu_progress_uses_real_stats():
    lessons, progress = stores()
    progress.mark_completed(42, "l1", correct=4, total=4, xp=20)
    cb = FakeCallback("m:progress")
    await answer_callback(cb, lessons, progress)
    assert any("1 из 1" in t for _, t, _ in cb.message.sent)


@pytest.mark.asyncio
async def test_menu_remind_uses_reminder_store():
    lessons, progress = stores()
    reminders = FakeReminderStore()
    reminders.set(42, 12)
    cb = FakeCallback("m:remind")
    await answer_callback(cb, lessons, progress, reminders)
    assert any("12" in t for _, t, _ in cb.message.sent), "экран напоминаний с текущей настройкой"


@pytest.mark.asyncio
async def test_menu_cards_without_terms_prompts():
    lessons, progress = stores()
    cb = FakeCallback("m:cards")
    await answer_callback(cb, lessons, progress)
    assert any("/lesson" in t for _, t, _ in cb.message.sent)


@pytest.mark.asyncio
async def test_menu_without_stores_shows_restart_alert():
    """Хендлер-обёртка с None-store: вежливый алерт, не исключение."""
    from src.bot.handlers import handle_menu_callback

    cb = FakeCallback("m:lesson")
    await handle_menu_callback(cb)
    assert cb.alerts and "перезапускается" in cb.alerts[-1][0], "вежливое сообщение вместо падения"


def test_menu_callback_data_within_budget():
    """callback_data кнопок меню не превышает бюджет 64 байта."""
    for data in MENU_CALLBACKS:
        assert len(data.encode()) <= 64


# --- фейки напоминаний (общие для меню) ---------------------------------------------


class FakeReminderStore:
    def __init__(self):
        self.settings: dict[int, dict] = {}

    def set(self, user_id, hour):
        self.settings[user_id] = {"hour": hour, "enabled": True}

    def disable(self, user_id):
        if user_id in self.settings:
            self.settings[user_id]["enabled"] = False

    def get(self, user_id):
        return self.settings.get(user_id)
