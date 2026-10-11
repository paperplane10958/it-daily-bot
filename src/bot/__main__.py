"""Точка входа IT Daily Bot: polling, конфиг из .env."""

import asyncio
import logging
import os
import sys
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.bot.handlers import router as message_router


def build_dispatcher(token: str) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(message_router)
    return dp


def build_bot(token: str, proxy: str | None = None) -> Bot:
    """Бот с опциональным SOCKS/HTTP-прокси (BOT_PROXY в .env).

    В сетях, где api.telegram.org недоступен напрямую, нужен прокси:
    BOT_PROXY=socks5://localhost:1080
    """
    if proxy:
        parsed = urlparse(proxy)
        scheme = parsed.scheme.lower()
        if scheme.startswith("socks"):
            from aiogram.client.session.aiohttp import AiohttpSession

            session = AiohttpSession(proxy=proxy)
            return Bot(token=token, session=session)
        return Bot(token=token)  # http(s) aiogram поймёт через env сам
    return Bot(token=token)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("BOT_TOKEN не задан: создай .env по образцу .env.example и добавь токен бота")

    proxy = os.getenv("BOT_PROXY") or None
    if proxy:
        logging.info("использую прокси для Telegram: %s", proxy)

    bot = build_bot(token, proxy)
    dp = build_dispatcher(token)

    async def run() -> None:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()