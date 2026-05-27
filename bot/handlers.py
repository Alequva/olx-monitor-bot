import logging
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from config import PAGE_SIZE
from db.database import (
    register_user, get_user, update_user,
    is_post_sent, mark_post_sent, get_all_active_users,
)
from scraper.olx import scrape_for_user
from scraper.parser import ParsedAd, make_telegram_link
from bot.keyboards import (
    main_menu_keyboard,
    ad_keyboard, interval_reply_keyboard,
    category_reply_keyboard, cities_reply_keyboard,
    rooms_reply_keyboard, get_price_keyboard,
    gender_reply_keyboard,
    backlog_reply_keyboard,
    load_more_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()

_search_cache: dict[int, dict] = {}

_RESTART_MSG = (
    "🔄 Bot was restarted on the server.\n"
    "Send /start to restore your settings and access the menu."
)


class FilterSetup(StatesGroup):
    category = State()
    price_min = State()
    price_max = State()
    location = State()
    rooms = State()
    gender = State()


class IntervalSetup(StatesGroup):
    waiting = State()


class BacklogSetup(StatesGroup):
    waiting = State()


INTERVAL_OPTIONS = {
    "15min": 15, "30min": 30, "1h": 60, "3h": 180,
    "6h": 360, "12h": 720, "24h": 1440,
}

BACKLOG_OPTIONS = {
    "1 day": 1, "3 days": 3, "7 days": 7,
    "14 days": 14, "30 days": 30,
}

CATEGORY_MAP = {
    "Long-term rent": "arenda-dolgosrochnaya",
    "Sale": "prodazha",
    "Rooms": "komnaty",
}

CITY_MAP = {
    "Tashkent": "tashkent", "Samarkand": "samarkand",
    "Bukhara": "bukhara", "Fergana": "fergana",
    "Namangan": "namangan", "Andijan": "andijan",
    "Kokand": "kokand", "Nukus": "nukus",
    "Urgench": "urgench", "Navoi": "navoi",
    "Jizzakh": "jizzakh", "Qarshi": "qarshi",
    "Termez": "termez", "Gulistan": "gulistan",
}

ROOMS_MAP = {
    "1 room": "1", "2 rooms": "2", "3 rooms": "3",
    "4+ rooms": "4+", "Any": "",
}

GENDER_MAP = {
    "For women": "women",
    "For men": "men",
    "No preference": "any",
}


# ── Menu text handlers ────────────────────────────────────────


async def _show_menu(message: Message, text: str = "", state: FSMContext | None = None):
    if state:
        await state.clear()
    await message.answer(
        text or "🏠 <b>OLX.uz Monitor</b>\n\nUse the menu below:",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "🔍 Set Filters")
async def menu_filters(message: Message, state: FSMContext):
    await state.set_state(FilterSetup.category)
    await message.answer(
        "📋 <b>Listing Categories</b>\n\n"
        "• <b>Long-term rent</b> — Apartments and houses for monthly rental\n"
        "• <b>Sale</b> — Apartments and houses for purchase\n"
        "• <b>Rooms</b> — Individual rooms in shared apartments",
        parse_mode="HTML",
    )
    await message.answer(
        "Select listing category:",
        reply_markup=category_reply_keyboard(),
    )


@router.message(FilterSetup.category, F.text.in_(list(CATEGORY_MAP.keys())))
async def filter_category(message: Message, state: FSMContext):
    cat = CATEGORY_MAP[message.text]
    await state.update_data(category=cat)
    await state.set_state(FilterSetup.price_min)
    await message.answer(
        "Select or enter minimum price in USD (or send 0 for no minimum):\n"
        "Example: 200",
        reply_markup=get_price_keyboard(cat),
    )


@router.message(FilterSetup.category)
async def filter_category_invalid(message: Message):
    await message.answer("Please choose a category from the keyboard above.")


@router.message(F.text == "⏰ Interval")
async def menu_interval(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await _show_menu(message, _RESTART_MSG)
        return

    await state.set_state(IntervalSetup.waiting)
    await message.answer(
        f"⏰ Current interval: every {user['interval_m']} minutes\n\n"
        "Select new check frequency:",
        reply_markup=interval_reply_keyboard(),
    )


@router.message(IntervalSetup.waiting, F.text.in_(list(INTERVAL_OPTIONS.keys())))
async def set_interval_reply(message: Message, state: FSMContext):
    minutes = INTERVAL_OPTIONS[message.text]
    update_user(message.from_user.id, interval_m=minutes)
    await state.clear()
    await message.answer(
        f"✅ Check interval set to every {minutes} minutes.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(IntervalSetup.waiting)
async def set_interval_invalid(message: Message):
    await message.answer("Please choose an interval from the keyboard above.")


@router.message(F.text == "📅 Backlog Days")
async def menu_backlog(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await _show_menu(message, _RESTART_MSG)
        return
    await state.set_state(BacklogSetup.waiting)
    await message.answer(
        "📅 How far back should I search for listings?",
        reply_markup=backlog_reply_keyboard(),
    )


@router.message(BacklogSetup.waiting, F.text.in_(list(BACKLOG_OPTIONS.keys())))
async def set_backlog_reply(message: Message, state: FSMContext):
    days = BACKLOG_OPTIONS[message.text]
    update_user(message.from_user.id, backlog_days=days)
    await state.clear()
    await message.answer(
        f"✅ Will search up to {days} day{'s' if days > 1 else ''} back.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(BacklogSetup.waiting)
async def set_backlog_invalid(message: Message):
    await message.answer("Please choose an option from the keyboard above.")


@router.message(F.text == "🔎 Search Now")
async def menu_search(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await _show_menu(message, _RESTART_MSG)
        return

    msg = await message.answer("🔍 Searching OLX.uz for the best deals...")

    ads = await scrape_for_user(
        category=user["category"],
        price_min=user["price_min"],
        price_max=user["price_max"],
        location=user["location"],
        rooms=user["rooms"],
        backlog_days=user["backlog_days"],
        gender_pref=user["gender_pref"],
        single_page=False,
    )

    if not ads:
        await msg.edit_text(
            "No listings found matching your filters in the last "
            f"{user['backlog_days']} day(s).",
        )
        return

    ads.sort(key=lambda a: (
        a.price_usd if a.price_usd is not None else float("inf")
    ))

    _search_cache[user_id] = {
        "results": ads,
        "offset": 0,
        "chat_id": message.chat.id,
    }

    await _send_batch(message.bot, user_id)


@router.message(F.text == "📋 Status")
async def menu_status(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await _show_menu(message, _RESTART_MSG)
        return

    await message.answer(
        format_filters(user),
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# ── /start ────────────────────────────────────────────────────


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    chat_id = message.chat.id
    register_user(user_id, chat_id)

    await message.answer(
        "🏠 <b>OLX.uz Monitor</b>\n\n"
        "I will check OLX.uz for new listings and send them to you.\n"
        "Use the menu below to get started.",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# ── Filters FSM (price + remaining) ───────────────────────────


@router.message(FilterSetup.price_min, F.text == "Write custom")
async def filter_price_min_custom(message: Message, state: FSMContext):
    await message.answer(
        "Enter minimum price in USD (or send 0 for no minimum):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(FilterSetup.price_min)
async def filter_price_min(message: Message, state: FSMContext):
    val = parse_int(message.text)
    if val is None or val < 0:
        await message.answer("Please enter a valid number (0 or more):")
        return
    data = await state.get_data()
    await state.update_data(price_min=val)
    await state.set_state(FilterSetup.price_max)
    await message.answer(
        "Enter maximum price in USD (or send 0 for no maximum):\n"
        "Example: 500",
        reply_markup=get_price_keyboard(data.get("category", "")),
    )


@router.message(FilterSetup.price_max, F.text == "Write custom")
async def filter_price_max_custom(message: Message, state: FSMContext):
    await message.answer(
        "Enter maximum price in USD (or send 0 for no maximum):",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(FilterSetup.price_max)
async def filter_price_max(message: Message, state: FSMContext):
    val = parse_int(message.text)
    if val is None or val < 0:
        await message.answer("Please enter a valid number (0 or more):")
        return
    data = await state.get_data()
    price_min = data.get("price_min", 0)
    if val > 0 and price_min > val:
        await message.answer(
            f"Maximum (${val}) must be greater than minimum (${price_min}). Try again:"
        )
        return
    await state.update_data(price_max=val)
    await state.set_state(FilterSetup.location)
    await message.answer(
        "Select city:",
        reply_markup=cities_reply_keyboard(),
    )


@router.message(FilterSetup.location, F.text.in_(list(CITY_MAP.keys()) + ["Any (skip)"]))
async def filter_location(message: Message, state: FSMContext):
    loc = CITY_MAP.get(message.text, "")
    await state.update_data(location=loc)
    await state.set_state(FilterSetup.rooms)
    await message.answer(
        "Select number of rooms:",
        reply_markup=rooms_reply_keyboard(),
    )


@router.message(FilterSetup.location)
async def filter_location_invalid(message: Message):
    await message.answer("Please choose a city from the keyboard above.")


@router.message(FilterSetup.rooms, F.text.in_(list(ROOMS_MAP.keys())))
async def filter_rooms(message: Message, state: FSMContext):
    rooms = ROOMS_MAP[message.text]
    await state.update_data(rooms=rooms)
    await state.set_state(FilterSetup.gender)
    await message.answer(
        "Any gender preference for the flatmates?",
        reply_markup=gender_reply_keyboard(),
    )


@router.message(FilterSetup.gender, F.text.in_(list(GENDER_MAP.keys())))
async def filter_gender(message: Message, state: FSMContext):
    gender_pref = GENDER_MAP[message.text]
    await state.update_data(gender_pref=gender_pref)
    data = await state.get_data()

    user_id = message.from_user.id
    register_user(user_id, message.chat.id)
    update_user(
        user_id,
        category=data.get("category", "arenda-dolgosrochnaya"),
        price_min=data.get("price_min", 0),
        price_max=data.get("price_max", 0),
        location=data.get("location", ""),
        rooms=data.get("rooms", ""),
        gender_pref=gender_pref,
    )

    await state.clear()
    summary = format_filters(data)
    await message.answer(
        f"✅ Filters saved!\n\n{summary}",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


@router.message(FilterSetup.gender)
async def filter_gender_invalid(message: Message):
    await message.answer("Please choose a gender preference from the keyboard above.")


@router.message(FilterSetup.rooms)
async def filter_rooms_invalid(message: Message):
    await message.answer("Please choose a room option from the keyboard above.")


# ── Command fallbacks ─────────────────────────────────────────


@router.message(Command("backlog"))
async def cmd_backlog(message: Message, state: FSMContext):
    await state.set_state(BacklogSetup.waiting)
    await message.answer(
        "📅 How far back should I search for listings?",
        reply_markup=backlog_reply_keyboard(),
    )


@router.message(Command("search_now"))
async def cmd_search_now(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await _show_menu(message, _RESTART_MSG)
        return

    msg = await message.answer("🔍 Searching OLX.uz for the best deals...")

    ads = await scrape_for_user(
        category=user["category"],
        price_min=user["price_min"],
        price_max=user["price_max"],
        location=user["location"],
        rooms=user["rooms"],
        backlog_days=user["backlog_days"],
        gender_pref=user["gender_pref"],
        single_page=False,
    )

    if not ads:
        await msg.edit_text(
            "No listings found matching your filters in the last "
            f"{user['backlog_days']} day(s).",
        )
        return

    ads.sort(key=lambda a: (
        a.price_usd if a.price_usd is not None else float("inf")
    ))

    _search_cache[user_id] = {
        "results": ads,
        "offset": 0,
        "chat_id": message.chat.id,
    }

    await _send_batch(message.bot, user_id)


@router.message(Command("interval"))
async def cmd_interval(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await _show_menu(message, _RESTART_MSG)
        return
    await state.set_state(IntervalSetup.waiting)
    await message.answer(
        f"⏰ Current interval: every {user['interval_m']} minutes\n\n"
        "Select new check frequency:",
        reply_markup=interval_reply_keyboard(),
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer(_RESTART_MSG, reply_markup=main_menu_keyboard())
        return
    await message.answer(
        format_filters(user),
        parse_mode="HTML",
    )


# ── Search pagination ─────────────────────────────────────────


@router.callback_query(F.data.startswith("load_more:"))
async def load_more(cq: CallbackQuery):
    user_id = int(cq.data.split(":", 1)[1])
    if user_id not in _search_cache:
        await cq.answer("Search results expired. Run /search again.", show_alert=True)
        return

    await cq.answer()
    await _send_batch(cq.bot, user_id)


async def _send_batch(bot, user_id: int):
    cache = _search_cache.get(user_id)
    if not cache:
        return

    results = cache["results"]
    offset = cache["offset"]
    batch = results[offset:offset + PAGE_SIZE]

    if not batch:
        await bot.send_message(
            cache["chat_id"],
            "No more listings to show.",
        )
        del _search_cache[user_id]
        return

    cache["offset"] = offset + len(batch)

    total = len(results)
    shown = cache["offset"]

    header = (
        f"Showing {shown - len(batch) + 1}–{min(shown, total)} of {total} "
        f"cheapest listings\n"
        f"{'─' * 20}\n"
    )

    lines = []
    for i, ad in enumerate(batch, start=offset + 1):
        price = format_price(ad.price_uzs, ad.price_usd)
        ad_lines = [f"<b>{i}.</b> <a href='{ad.post_url}'>{ad.title}</a>"]
        ad_lines.append(f"💰 {price}")
        ad_lines.append(f"📍 {ad.location}")
        ad_lines.append(f"📅 {ad.days_ago}")
        if ad.phone:
            ad_lines.append(f'📞 <a href="{make_telegram_link(ad.phone)}">Write in Telegram</a>')
        if ad.preferred_phone:
            ad_lines.append(f'📞 <a href="{make_telegram_link(ad.preferred_phone)}">Write in Telegram</a>')
        ad_lines.append("─" * 25)
        lines.append("\n".join(ad_lines))

    text = header + "\n".join(lines)

    if shown < total:
        kb = load_more_keyboard(user_id, total, shown)
        text += "\n\n"
    else:
        kb = None
        text += "\n\n✅ All listings shown."

    await bot.send_message(
        cache["chat_id"],
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=kb,
    )


# ── Send helpers ──────────────────────────────────────────────


async def send_ad(bot, chat_id: int, ad):
    title_line = f"<b>{ad.title}</b>"
    price_line = f"💰 <b>Price:</b> {format_price(ad.price_uzs, ad.price_usd)}"
    location_line = f"📍 <b>Location:</b> {ad.location}"
    date_line = f"📅 {ad.formatted_date} | <i>posted {ad.days_ago}</i>"

    extra = []
    if ad.phone:
        extra.append(f'📞 <a href="{make_telegram_link(ad.phone)}">Write in Telegram</a>')
    if ad.preferred_phone:
        extra.append(f'📞 <a href="{make_telegram_link(ad.preferred_phone)}">Write in Telegram</a>')

    parts = [title_line, "", price_line, location_line, date_line] + extra
    caption = "\n".join(parts)

    if ad.image_url:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=ad.image_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=ad_keyboard(ad.post_url, make_telegram_link(ad.phone) if ad.phone else ""),
            )
            return
        except Exception:
            pass

    await bot.send_message(
        chat_id=chat_id,
        text=f"{caption}\n\n🔗 {ad.post_url}",
        parse_mode="HTML",
        disable_web_page_preview=False,
        reply_markup=ad_keyboard(ad.post_url),
    )


async def run_periodic_check(bot) -> int:
    users = get_all_active_users()
    total_new = 0
    for user in users:
        try:
            ads = await scrape_for_user(
                category=user["category"],
                price_min=user["price_min"],
                price_max=user["price_max"],
                location=user["location"],
                rooms=user["rooms"],
                backlog_days=user["backlog_days"],
                gender_pref=user["gender_pref"],
                single_page=True,
            )
            new_count = 0
            for ad in ads:
                if is_post_sent(user["user_id"], ad.post_url):
                    continue
                await send_ad(bot, user["chat_id"], ad)
                mark_post_sent(user["user_id"], ad.post_url, ad.title)
                new_count += 1
            total_new += new_count
            if new_count > 0:
                logger.info(
                    "Sent %d new listings to user %d",
                    new_count, user["user_id"],
                )
        except Exception as e:
            logger.error("Error checking for user %d: %s", user["user_id"], e)
    return total_new


def format_price(uzs, usd) -> str:
    parts = []
    if uzs is not None:
        parts.append(f"{uzs:,.0f} сум")
    if usd is not None:
        parts.append(f"${usd:,.2f}")
    return " / ".join(parts) if parts else "N/A"


def format_filters(data) -> str:
    if hasattr(data, "keys"):
        data = dict(data)
    cat_labels = {
        "arenda-dolgosrochnaya": "Long-term rent",
        "prodazha": "Sale",
        "q-комнаты": "Rooms",
    }
    cat = cat_labels.get(data.get("category", ""), data.get("category", "Not set"))
    pmin = data.get("price_min", 0) or "No min"
    pmax = data.get("price_max", 0) or "No max"
    loc = data.get("location", "") or "Any"
    rooms = data.get("rooms", "") or "Any"
    interval = data.get("interval_m", 30)
    backlog = data.get("backlog_days", 7)
    gender_labels = {"women": "For women", "men": "For men", "any": "No preference"}
    gender = gender_labels.get(data.get("gender_pref", "any"), "No preference")

    return (
        f"📋 <b>Your Filters</b>\n"
        f"• Category: {cat}\n"
        f"• Price: {'$' + str(pmin) if isinstance(pmin, int) else pmin}"
        f" - {'$' + str(pmax) if isinstance(pmax, int) else pmax}\n"
        f"• Location: {loc}\n"
        f"• Rooms: {rooms}\n"
        f"• Preference: {gender}\n"
        f"• Lookback: {backlog} day{'s' if backlog > 1 else ''}\n"
        f"• Check interval: every {interval} min"
    )


def parse_int(text: str) -> int | None:
    text = text.strip().replace(",", "").replace(" ", "")
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None
