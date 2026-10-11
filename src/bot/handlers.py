"""Обработчики сообщений echo-бота."""

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="messages")

GREETING = (
    "Привет! Я IT Daily Bot 🤖🎓\n"
    "Буду учить тебя IT каждый день по 5–15 минут — короткие уроки, "
    "квизы, стрики и XP, как в Duolingo.\n\n"
    "Я на ранней стадии разработки: пока умею только эхо.\n"
    "Команды: /start, /help"
)

HELP = (
    "Команды:\n"
    "/start — приветствие и описание бота\n"
    "/help — этот список\n\n"
    "Уроки появятся в ближайших обновениях 👷"
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(GREETING)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(HELP)


@router.message()
async def handle_echo(message: Message) -> None:
    if message.text:
        await message.answer(message.text)