import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from db.database import init_db, get_all_active_users
from bot.handlers import router, run_backfill
from scheduler import BotScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, scheduler: BotScheduler):
    users = get_all_active_users()
    if users:
        logger.info("Starting backfill for %d user(s)...", len(users))
        sent = await run_backfill(bot)
        logger.info("Backfill complete: %d listings sent", sent)
    scheduler.start()
    logger.info("Bot is ready")


async def main():
    logger.info("Initializing database...")
    init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = BotScheduler(bot)

    dp.startup.register(lambda: on_startup(bot, scheduler))

    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
