import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from db.database import get_all_active_users

logger = logging.getLogger(__name__)


class BotScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self._tasks = {}

    def start(self):
        self._schedule_all()
        self.scheduler.start()
        logger.info("Scheduler started")

    def _schedule_all(self):
        users = get_all_active_users()
        for user in users:
            self.add_user_task(user["user_id"], user["interval_m"])

    def add_user_task(self, user_id: int, interval_m: int):
        key = f"check_{user_id}"
        if key in self._tasks:
            self.scheduler.remove_job(key)

        self.scheduler.add_job(
            self._run_check,
            trigger=IntervalTrigger(minutes=interval_m),
            id=key,
            replace_existing=True,
            kwargs={"user_id": user_id},
        )
        self._tasks[key] = True

    def remove_user_task(self, user_id: int):
        key = f"check_{user_id}"
        if key in self._tasks:
            self.scheduler.remove_job(key)
            del self._tasks[key]

    async def _run_check(self, user_id: int):
        from bot.handlers import run_periodic_check
        try:
            await run_periodic_check(self.bot)
        except Exception as e:
            logger.error("Periodic check error for user %d: %s", user_id, e)

    def shutdown(self):
        self.scheduler.shutdown(wait=False)
