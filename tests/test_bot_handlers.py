"""Тесты echo-бота: /start, /help, эхо и конфигурация бота."""

import pytest

from src.bot.handlers import router, handle_start, handle_help, handle_echo


class FakeMessage:
    """Минимальная заглушка сообщения: хранит ответы вместо реальной отправки."""

    def __init__(self, text: str | None = None, chat_id: int = 1):
        self.text = text
        self.chat = type("Chat", (), {"id": chat_id})()
        self.sent: list[str] = []
        self.last_kwargs: dict = {}

    async def answer(self, text: str, **kwargs):
        self.sent.append(text)
        self.last_kwargs = kwargs


def _handler_names() -> list[str]:
    return [h.callback.__name__ for h in router.message.handlers]


def _handler_filters(name: str) -> list:
    for h in router.message.handlers:
        if h.callback.__name__ == name:
            return h.filters or []
    return []


def test_start_handler_is_registered():
    assert "handle_start" in _handler_names()
    filters = _handler_filters("handle_start")
    assert filters, "у handle_start должен быть фильтр команды"
    assert any(
        type(getattr(f, "callback", None)).__name__ == "CommandStart" for f in filters
    )


def test_help_handler_is_registered_with_command_filter():
    assert "handle_help" in _handler_names()
    filters = _handler_filters("handle_help")
    assert filters, "у handle_help должен быть фильтр команды"


def test_echo_handler_is_registered_last():
    names = _handler_names()
    assert "handle_echo" in names
    # echo — catch-all, должен стоять последним, чтобы не перехватывать команды
    assert names[-1] == "handle_echo"


@pytest.mark.asyncio
async def test_start_replies_greeting():
    msg = FakeMessage()
    await handle_start(msg)
    assert msg.sent, "/start должен отвечать"
    assert "/help" in msg.sent[0]


@pytest.mark.asyncio
async def test_start_shows_menu_with_buttons(monkeypatch):
    """Со stores на месте /start открывает меню со статистикой и кнопками."""
    from src.bot import handlers
    from tests.test_lesson_handlers import FakeLessonStore, FakeProgressStore

    monkeypatch.setitem(handlers.runtime, "lessons", FakeLessonStore([]))
    monkeypatch.setitem(handlers.runtime, "progress", FakeProgressStore())
    msg = FakeMessage()
    await handle_start(msg)
    assert msg.sent, "/start должен отвечать"
    assert "Главное меню" in msg.sent[0], "/start открывает меню, а не голое приветствие"
    assert msg.last_kwargs.get("reply_markup") is not None, "меню приходит с кнопками"


@pytest.mark.asyncio
async def test_help_lists_commands():
    msg = FakeMessage()
    await handle_help(msg)
    assert msg.sent
    assert "/lesson" in msg.sent[0] and "/progress" in msg.sent[0]
    assert "меню" in msg.sent[0].lower(), "help упоминает /start как меню"


@pytest.mark.asyncio
async def test_echo_replies_with_same_text():
    msg = FakeMessage("привет")
    await handle_echo(msg)
    assert msg.sent == ["привет"]


@pytest.mark.asyncio
async def test_echo_ignores_empty_message():
    msg = FakeMessage(None)
    await handle_echo(msg)
    assert msg.sent == []


# --- конфигурация бота ---------------------------------------------------------


def test_build_bot_uses_socks_session_when_proxy_set():
    from src.bot.__main__ import build_bot
    from aiogram.client.session.aiohttp import AiohttpSession

    bot = build_bot("123:test", "socks5://localhost:1080")
    assert isinstance(bot.session, AiohttpSession)


def test_build_bot_plain_without_proxy():
    from src.bot.__main__ import build_bot

    bot = build_bot("123:test", None)
    assert bot.session.proxy is None


def test_build_bot_sets_html_parse_mode():
    """Рендер урока шлёт HTML-теги — parse_mode='HTML' должен быть дефолтом бота."""
    from src.bot.__main__ import build_bot

    for proxy in ("socks5://localhost:1080", None):
        bot = build_bot("123:test", proxy)
        assert bot.default.parse_mode == "HTML", f"parse_mode не задан (proxy={proxy!r})"


@pytest.mark.asyncio
async def test_echo_escapes_html():
    """Пользовательский текст уходит как есть — при HTML-режиме `<` сломает отправку."""
    msg = FakeMessage("1<2 и a&b")
    await handle_echo(msg)
    assert msg.sent == ["1&lt;2 и a&amp;b"]


def test_dispatcher_includes_router():
    from src.bot.__main__ import build_dispatcher

    dp = build_dispatcher("123:test")
    assert "messages" in [r.name for r in dp.sub_routers], "роутер не подключён"


def test_init_stores_wires_runtime(tmp_path):
    from src.bot.__main__ import init_stores
    from src.agent.store import LessonStore
    from src.bot.progress import ProgressStore
    from src.bot.reminders import ReminderStore
    from src.bot.handlers import runtime

    init_stores(tmp_path / "lessons.db")
    try:
        assert isinstance(runtime["lessons"], LessonStore)
        assert isinstance(runtime["progress"], ProgressStore)
        assert isinstance(runtime["reminders"], ReminderStore)
    finally:
        runtime["lessons"].close()
        runtime["progress"].close()
        runtime["reminders"].close()
        runtime["lessons"] = None
        runtime["progress"] = None
        runtime["reminders"] = None


def test_start_polling_sets_bot_commands():
    """При старте регистрируются команды бота: синяя меню-кнопка Telegram."""
    from src.bot.__main__ import set_bot_commands

    commands: list = []

    class FakeBot:
        async def set_my_commands(self, cmds):
            commands.extend(cmds)

    import asyncio

    asyncio.run(set_bot_commands(FakeBot()))
    scopes = [c.command for c in commands]
    assert "lesson" in scopes and "progress" in scopes and "cards" in scopes
    assert "remind" in scopes and "help" in scopes


def test_start_polling_registers_commands(monkeypatch):
    """start_polling вызывает set_my_commands перед циклом polling."""
    from src.bot import __main__ as main_mod

    calls: list = []

    class FakeBot:
        async def set_my_commands(self, cmds):
            calls.append(cmds)

        async def delete_webhook(self, drop_pending_updates=False):
            pass

    async def fake_start_polling(self, bot, **kwargs):
        assert calls, "команды должны быть зарегистрированы до polling"
        raise KeyboardInterrupt

    monkeypatch.setattr(main_mod.Dispatcher, "start_polling", fake_start_polling)
    monkeypatch.setattr(main_mod, "init_stores", lambda db: None)
    monkeypatch.setattr(main_mod, "build_bot", lambda token, proxy=None: FakeBot())
    monkeypatch.setattr(main_mod, "build_dispatcher", lambda token: main_mod.Dispatcher())
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("BOT_TOKEN", "123:test")
    monkeypatch.delenv("BOT_PROXY", raising=False)
    main_mod.main()  # KeyboardInterrupt проглатывается


def test_studied_today_uses_progress_dates(tmp_path):
    """Изучавшие сегодня собираются из activity_dates всех пользователей."""
    from src.bot.__main__ import studied_today_ids
    from src.agent.store import LessonStore
    from src.bot.progress import ProgressStore

    db = tmp_path / "lessons.db"
    LessonStore(db).close()
    ps = ProgressStore(db)
    ps.mark_completed(7, "l1", correct=4, total=4, xp=10)
    ps.mark_completed(9, "l2", correct=4, total=4, xp=10)
    ids = studied_today_ids(ps)
    ps.close()
    assert set(ids) == {7, 9}, "оба занимались сегодня"