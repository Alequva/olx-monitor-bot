import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from db.database import init_db, get_all_active_users
from bot.handlers import router
from scheduler import BotScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def handle_health(request):
    return web.Response(text="ok")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health-check server started on port %d", port)


async def main():
    logger.info("Initializing database...")
    init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = BotScheduler(bot)
    scheduler.start()

    asyncio.create_task(run_web_server())

    for user in get_all_active_users():
        try:
            await bot.send_message(
                user["chat_id"],
                "🔄 Bot was restarted. Send /start to refresh the menu.",
            )
        except Exception:
            pass

    logger.info("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
