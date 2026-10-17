"""Точка входа IT Daily Bot: polling, конфиг из .env."""

import asyncio
import logging
import os
import sys
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from dotenv import load_dotenv

import datetime as dt

from src.bot.handlers import router as message_router
from src.bot.handlers import runtime
from src.bot.reader import LessonReader
from src.bot.progress import ProgressStore
from src.bot.reminders import ReminderStore, run_reminder_tick


def init_stores(db_path) -> None:
    """Открыть stores уроков/прогресса/напоминаний и отдать их хендлерам (runtime)."""
    runtime["lessons"] = LessonReader(db_path)
    runtime["progress"] = ProgressStore(db_path)
    runtime["reminders"] = ReminderStore(db_path)


def studied_today_ids(progress: ProgressStore) -> set[int]:
    """id всех, кто завершал урок сегодня (для фильтра напоминаний)."""
    today = dt.date.today().isoformat()
    rows = progress.conn.execute(
        "SELECT DISTINCT user_id FROM progress WHERE substr(updated_at, 1, 10) = ?",
        (today,),
    ).fetchall()
    return {r["user_id"] for r in rows}


async def reminder_loop(bot, interval_seconds: int = 60) -> None:
    """Раз в interval_seconds проверять, кому пора напомнить об уроке.

    Тихо умирает при отмене (остановка бота); ошибки тика логируются, цикл живёт.
    """
    reminders = runtime["reminders"]
    progress = runtime["progress"]
    if reminders is None or progress is None:
        return
    while True:
        try:
            now = dt.datetime.now()
            sent = await run_reminder_tick(bot, reminders, now, studied_today_ids(progress))
            if sent:
                logging.info("напоминания: отправлено %d", sent)
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("ошибка тика напоминаний")
        await asyncio.sleep(interval_seconds)


def build_dispatcher(token: str) -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(message_router)
    return dp


BOT_COMMANDS = [
    BotCommand(command="lesson", description="Пройти следующий урок"),
    BotCommand(command="progress", description="Прогресс, XP и стрик"),
    BotCommand(command="cards", description="Карточки терминов"),
    BotCommand(command="remind", description="Ежедневное напоминание"),
    BotCommand(command="help", description="Справка"),
]


async def set_bot_commands(bot) -> None:
    """Зарегистрировать команды: синяя меню-кнопка Telegram (список у поля ввода)."""
    await bot.set_my_commands(BOT_COMMANDS)


def build_bot(token: str, proxy: str | None = None) -> Bot:
    """Бот с опциональным SOCKS/HTTP-прокси (BOT_PROXY в .env).

    В сетях, где api.telegram.org недоступен напрямую, нужен прокси:
    BOT_PROXY=socks5://localhost:1080
    """
    props = DefaultBotProperties(parse_mode="HTML")  # рендер урока шлёт HTML-теги
    if proxy:
        parsed = urlparse(proxy)
        scheme = parsed.scheme.lower()
        if scheme.startswith("socks"):
            from aiogram.client.session.aiohttp import AiohttpSession

            session = AiohttpSession(proxy=proxy)
            return Bot(token=token, session=session, default=props)
        return Bot(token=token, default=props)  # http(s) aiogram поймёт через env сам
    return Bot(token=token, default=props)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    token = os.getenv("BOT_TOKEN")
    if not token:
        sys.exit("BOT_TOKEN не задан: создай .env по образцу .env.example и добавь токен бота")

    proxy = os.getenv("BOT_PROXY") or None
    if proxy:
        logging.info("использую прокси для Telegram: %s", proxy)

    init_stores(os.getenv("LESSONS_DB", "data/lessons.db"))
    bot = build_bot(token, proxy)
    dp = build_dispatcher(token)

    async def run() -> None:
        reminder_task = asyncio.create_task(reminder_loop(bot))
        try:
            await set_bot_commands(bot)
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
        finally:
            reminder_task.cancel()

    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()