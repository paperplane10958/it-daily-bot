"""Точка входа IT Daily Bot: polling, конфиг из .env."""

import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.bot.handlers import router as message_router


def build_dispatcher(token: str) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(message_router)
    return dp


def build_bot(token: str) -> Bot:
    return Bot(token=token)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("BOT_TOKEN не задан: создай .env по образцу .env.example и добавь токен бота")

    bot = build_bot(token)
    dp = build_dispatcher(token)

    async def run() -> None:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    asyncio.run(run())


if __name__ == "__main__":
    main()