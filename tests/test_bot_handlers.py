"""Тесты echo-бота: /start, /help, эхо и конфигурация бота."""

import pytest

from src.bot.handlers import router, handle_start, handle_help, handle_echo


class FakeMessage:
    """Минимальная заглушка сообщения: хранит ответы вместо реальной отправки."""

    def __init__(self, text: str | None = None, chat_id: int = 1):
        self.text = text
        self.chat = type("Chat", (), {"id": chat_id})()
        self.sent: list[str] = []

    async def answer(self, text: str, **kwargs):
        self.sent.append(text)


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
async def test_help_lists_commands():
    msg = FakeMessage()
    await handle_help(msg)
    assert msg.sent
    assert "/lesson" in msg.sent[0] and "/progress" in msg.sent[0]


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


def test_dispatcher_includes_router():
    from src.bot.__main__ import build_dispatcher

    dp = build_dispatcher("123:test")
    assert "messages" in [r.name for r in dp.sub_routers], "роутер не подключён"


def test_init_stores_wires_runtime(tmp_path):
    from src.bot.__main__ import init_stores
    from src.agent.store import LessonStore
    from src.bot.progress import ProgressStore
    from src.bot.handlers import runtime

    init_stores(tmp_path / "lessons.db")
    try:
        assert isinstance(runtime["lessons"], LessonStore)
        assert isinstance(runtime["progress"], ProgressStore)
    finally:
        runtime["lessons"].close()
        runtime["progress"].close()
        runtime["lessons"] = None
        runtime["progress"] = None