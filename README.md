# OLX.uz Telegram Monitor Bot

A Telegram bot that periodically scrapes [OLX.uz](https://www.olx.uz) for rental/sale listings and sends new matching posts directly to your Telegram — with images, price, date, and a direct link.

## Features

- **Automated scraping** — periodically fetches new listings from OLX.uz
- **Smart filters** — filter by category (rent/sale/rooms), price range, city, and room count
- **Instant delivery** — each new matching listing is sent immediately as a photo message with details
- **7-day backfill** — on first run, sends all matching listings from the past 7 days
- **Deduplication** — tracks sent posts in SQLite so you never see the same listing twice
- **Docker support** — easy deployment with docker-compose
- **Configurable check interval** — 15min to 24h, settable via bot command

## Architecture

```
olx-monitor-bot/
├── main.py                 # Entry point — starts bot + scheduler
├── config.py               # Env-based configuration
├── .env                    # Bot token (not committed)
├── .env.example            # Template for env vars
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
├── docker-compose.yml      # Container orchestration
├── scraper/
│   ├── olx.py              # Fetch OLX listing pages
│   ├── parser.py           # Parse HTML ad cards → structured data
│   └── filters.py          # Build search URLs from user filters
├── bot/
│   ├── handlers.py         # /start, /filters, /search_now, /status, /interval
│   └── keyboards.py        # Inline "View on OLX" button + filter keyboards
├── db/
│   └── database.py         # SQLite CRUD operations
└── scheduler.py            # APScheduler — periodic checks

data/                       # SQLite DB persisted here (gitignored)
```

### Data Flow

```
[OLX.uz] → scraper fetches listing pages → parses ad cards →
  extracts: image, title, price, date, location, link →
  checks DB for duplicates → sends new posts to Telegram
```

### Tech Stack

| Component | Library | Purpose |
|---|---|---|
| Bot framework | `aiogram 3` | Async Telegram bot API |
| HTTP client | `httpx` | Async page fetching |
| HTML parsing | `BeautifulSoup4` + `lxml` | Card extraction |
| Scheduling | `APScheduler` | Periodic scanning |
| Database | `SQLite` (built-in) | Dedup + user storage |

## Setup

### 1. Prerequisites

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### 2. Local Run

```bash
# Clone / copy the project
cd olx-monitor-bot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure your bot token
cp .env.example .env
# Edit .env and add your BOT_TOKEN

# Run
python main.py
```

### 3. Docker

```bash
# Copy and configure
cp .env.example .env
# Edit .env with your BOT_TOKEN

# Build and run
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + command overview |
| `/filters` | Interactive filter setup (category → price → location → rooms) |
| `/search_now` | Run an immediate search with current filters |
| `/status` | Show current filter configuration |
| `/interval` | Change periodic check frequency |

### Filter Options

**Category:**
- Long-term rent (`arenda-dolgosrochnaya`)
- Sale (`prodazha`)
- Rooms (`komnaty`)

**Price:** Enter min/max in USD. OLX prices in UZS are converted at ~12,000 UZS/USD.

**Location:** City name filter (e.g., "Tashkent", "Samarkand"). Leave empty for all.

**Rooms:** 1, 2, 3, or 4+.

## How Scraping Works

1. The bot builds an OLX search URL from your filters:
   ```
   https://www.olx.uz/nedvizhimost/kvartiry/arenda-dolgosrochnaya/
   ?search[filter_float_price:from]=200
   &search[filter_float_price:to]=500
   &search[order]=created_at:desc
   &page=1
   ```

2. The listing page is fetched and parsed. Each ad card (`<div data-cy="l-card">`) is extracted for:
   - Image URL (from `<img>` tag)
   - Title (from link text)
   - Price (in UZS or USD)
   - Location + date text
   - Post URL (from `<a href>`)

3. Russian date strings are parsed:
   - `Сегодня в 04:41` → today
   - `Вчера в 15:30` → yesterday
   - `19 мая 2026 г.` → absolute date

4. Listings are filtered by user criteria and checked against the sent_posts database.

5. New matching listings are sent to Telegram as photo messages with an inline "View on OLX" button.

## Database

**File:** `data/bot.db` (SQLite)

### Schema

**`users`** — stores user preferences:
- `user_id` — Telegram user ID (PK)
- `chat_id` — Telegram chat ID for sending messages
- `category` — listing category slug
- `price_min` / `price_max` — price range in USD
- `location` — city filter string
- `rooms` — rooms filter
- `interval_m` — check frequency in minutes
- `is_active` — whether user is active

**`sent_posts`** — deduplication:
- `user_id` + `post_url` (unique constraint)
- `post_title` — for reference
- `sent_at` — timestamp

## Changelog / Progress

### 2026-05-21 — Initial Implementation

- [x] Project scaffolded with full directory structure
- [x] Database layer: users + sent_posts tables
- [x] Scraper: OLX page fetching, HTML parsing, Russian date parsing
- [x] Filter engine: category, price range, location, rooms
- [x] Bot handlers: /start, /filters (interactive), /search_now, /status, /interval
- [x] Scheduler: periodic checks via APScheduler
- [x] Docker build + docker-compose
- [x] 7-day backfill on first run
- [x] Deduplication (SQLite)
- [x] Local git repo initialized

### 2026-05-21 — Bugfixes

- [x] Fixed `komnaty` category URL (was 404, now uses search query `/q-комнаты/`)
- [x] Added city name translations for location filter (Tashkent→Ташкент, etc.)
- [x] Fixed `sqlite3.Row` `.get()` AttributeError in `format_filters`
- [x] Fixed startup coroutine not being awaited

## License

MIT
