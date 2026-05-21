# OLX.uz Telegram Monitor Bot

A Telegram bot that periodically scrapes [OLX.uz](https://www.olx.uz) for rental/sale/room listings and sends new matching posts directly to your Telegram — with images, price, date, and a direct link.

## Features

- **Automated scraping** — periodically fetches new listings from OLX.uz
- **Smart filters** — filter by category (rent/sale/rooms), price range, city, room count, and gender preference
- **Reply keybord** — persistent bottom bar replaces text input for all main actions
- **Instant delivery** — each new matching listing is sent immediately as a photo message with details
- **Deduplication** — tracks sent posts in SQLite so you never see the same listing twice
- **Docker support** — easy deployment with docker-compose
- **Configurable check interval** — 15min to 24h, settable via keyboard

## Architecture

```
olx-monitor-bot/
├── main.py                 # Entry point — starts bot + scheduler + startup notification
├── config.py               # Env-based configuration
├── .env                    # Bot token (not committed)
├── .env.example            # Template for env vars
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container build
├── docker-compose.yml      # Container orchestration
├── scraper/
│   ├── olx.py              # Fetch OLX listing pages + local filtering
│   ├── parser.py           # Parse HTML ad cards → structured data
│   └── filters.py          # Search URL builder + price/location/gender filters
├── bot/
│   ├── handlers.py         # All bot logic — commands, FSM, pagination, periodic checks
│   └── keyboards.py        # Reply keyboards (main menu, interval, backlog, cities, etc.)
├── db/
│   └── database.py         # SQLite CRUD operations
└── scheduler.py            # APScheduler — periodic checks

data/                       # SQLite DB persisted here (gitignored)
```

### Data Flow

```
[OLX.uz] → scraper fetches listing pages (no OLX-side filters) →
  parses each <div data-cy="l-card"> → extracts all card text →
  applies filters locally: price, location, gender, date →
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
cd olx-monitor-bot

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your BOT_TOKEN

python main.py
```

### 3. Docker

```bash
cp .env.example .env
# Edit .env with your BOT_TOKEN

docker compose up -d
docker compose logs -f
docker compose down
```

## Bot Usage

### Reply Keyboard (persistent bottom bar)

| Button | Action |
|---|---|
| 🔍 Set Filters | Starts interactive filter setup: category → price min → price max → city → rooms → gender |
| ⏰ Interval | Opens interval reply keyboard (15min / 30min / 1h / 3h / 6h / 12h / 24h) |
| 📅 Backlog Days | Opens backlog reply keyboard (1 / 3 / 7 / 14 / 30 days) |
| 🔎 Search Now | Searches OLX with current filters → shows 10 cheapest with "Load next 10" inline button |
| 📋 Status | Shows current filter configuration |

### Command Fallbacks

All actions are also triggerable via `/start`, `/search_now`, `/interval`, `/backlog`, `/status`.

### Filter Flow Details

1. **Category** — Description of each type shown, then reply keyboard: Long-term rent / Sale / Rooms
2. **Price min** — Dynamic reply keyboard: rent shows 0 / 100 / 200 / 300 / 500 / 800 / 1000 / 1500; sale shows 0 / 5000 / 10000 / 15000 / 20000 / 30000 / 40000 / 50000 + "Write custom"
3. **Price max** — Same pattern
4. **City** — Reply keyboard: 14 cities sorted by population + Any (skip)
5. **Rooms** — Reply keyboard: 1 / 2 / 3 / 4+ / Any
6. **Gender preference** — Reply keyboard: For women / For men / No preference

### Gender Filter

Scans both title and description for gender-specific prefixes (word-boundary matched):

| Women prefixes | Men prefixes |
|---|---|
| `девуш`, `девоч`, `женщ`, `киз`, `айол`, `аёл` | `мальч`, `паре`, `парн`, `муж`, `йигит`, `эркак`, `бола`, `болла` |

Uses Russian, Uzbek Latin, and Uzbek Cyrillic (Russian alphabet) variants.

- Listing matches only women keywords → shown only to women users
- Listing matches only men keywords → shown only to men users
- Matches both or neither → shown to everyone

## How Scraping Works

1. The bot builds a bare OLX search URL (category + page only — no price/rooms/location filters):
   ```
   https://www.olx.uz/nedvizhimost/kvartiry/arenda-dolgosrochnaya/
   ?search[order]=created_at:desc&page=1
   ```

2. All filtering (price, location, gender) is done **locally in Python** after parsing. OLX URL-side price/rooms filters trigger "extended_search_no_results_last_resort" and produce cross-category garbage.

3. Each listing card (`<div data-cy="l-card">`) is parsed for:
   - Full card text (title + description excerpt + any text)
   - Image URL
   - Price (UZS → USD at ~12,000 rate)
   - Location + date (Russian + Uzbek date parsing)
   - Post URL

4. Non-duplicate, in-range, matching listings are sent to Telegram.

## Database

**File:** `data/bot.db` (SQLite)

### Schema

**`users`** — stores user preferences:
- `user_id`, `chat_id`, `category`, `price_min`, `price_max`, `location`, `rooms`
- `interval_m`, `backlog_days`, `gender_pref` (TEXT: any/women/men)
- `is_active`, `created_at`

**`sent_posts`** — deduplication:
- `user_id` + `post_url` (unique)
- `post_title`, `sent_at`

## Changelog

### 2026-05-21 — v1 — Initial Implementation

- [x] Project scaffolded with full directory structure
- [x] Database: users + sent_posts tables
- [x] Scraper: OLX page fetching, HTML parsing, Russian date parsing
- [x] Filter engine: category, price range, location, rooms
- [x] Bot handlers: /start, /filters (inline FSM), /search_now, /status, /interval
- [x] Scheduler: periodic checks via APScheduler
- [x] Docker build + docker-compose
- [x] Local git repo initialized

### 2026-05-21 — v2 — Bugfixes

- [x] Fixed `komnaty` category URL (was 404, now /q-комнаты/)
- [x] Added city name translations for location filter
- [x] Fixed `sqlite3.Row` `.get()` AttributeError in `format_filters`
- [x] Fixed startup coroutine not being awaited

### 2026-05-21 — v3 — Pagination + Backlog

- [x] `/search_now`: 10 cheapest listings + "Load next 10" inline button
- [x] `/backlog` command with inline keyboard (1/3/7/14/30 days)
- [x] Search results cached in memory for pagination
- [x] `backlog_days` column added to users table

### 2026-05-21 — v4 — Reply Keyboards + UI Overhaul

- [x] All menus changed from inline to reply keyboards (persistent bottom bar)
- [x] `/start` shows main menu keyboard instead of raw text
- [x] Category explanation text shown before selection
- [x] City selection via reply keyboard (14 cities, population order)
- [x] Interval & Backlog now use reply keyboards
- [x] Filter flow: category → price → city → rooms → gender
- [x] Price input uses dynamic reply keyboard (rent presets vs sale presets) + "Write custom"
- [x] Removed startup backfill (no scan on launch)
- [x] Startup notification: bot sends "/start" to active users on restart
- [x] Removed all price/rooms/location filters from OLX search URLs — filtered locally only

### 2026-05-21 — v5 — Gender Filter

- [x] `gender_pref` column added to users table (TEXT DEFAULT 'any')
- [x] `gender_matches()` function with prefix matching across Russian/Uzbek Latin/Uzbek Cyrillic
- [x] Word-boundary regex to avoid false positives ("пара" ≠ "паре")
- [x] Keyword prefixes: девуш, девоч, женщ, киз, айол, аёл / мальч, парен, парн, муж, йигит, эркак, бола, болла
- [x] ParsedAd.description field (extracts full card text for broader matching)
- [x] Gender reply keyboard in filter flow (For women / For men / No preference)
- [x] Status display includes preference line

### 2026-05-21 — v6 — Gender & Price Keyboard Fixes

- [x] Added `девоч` to women prefixes (catches "девочек", "девочка", "девочки")
- [x] Changed men prefix `паре` → `парен` (eliminates false positive "семейной паре", still matches "парень"/"паренек")
- [x] Dynamic price keyboard — sale category shows higher presets (0 / 5k / 10k / 15k / 20k / 30k / 40k / 50k), rent shows original low presets
- [x] Startup notification: bot sends "/start" to active users on restart

## Planned Fixes

- [ ] **Language selection**: Future feature — toggle bot UI between English/Russian/Uzbek
- [ ] **Individual listing scraping**: Optional — fetch full description from individual listing pages for more accurate gender matching (currently uses card excerpt only)

## License

MIT
