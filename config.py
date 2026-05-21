import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in .env file")

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bot.db")

SCRAPER_DELAY = 1.5
MAX_PAGES_BACKFILL = 50
DEFAULT_INTERVAL_MINUTES = 30
DEFAULT_BACKLOG_DAYS = 7
PAGE_SIZE = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
