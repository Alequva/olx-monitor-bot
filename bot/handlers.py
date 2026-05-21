import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile

from db.database import (
    register_user, get_user, update_user,
    is_post_sent, mark_post_sent, get_all_active_users,
)
from scraper.olx import scrape_for_user
from bot.keyboards import (
    ad_keyboard, interval_keyboard,
    category_keyboard, rooms_keyboard,
)

logger = logging.getLogger(__name__)
router = Router()


class FilterSetup(StatesGroup):
    category = State()
    price_min = State()
    price_max = State()
    location = State()
    rooms = State()


@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    register_user(user_id, chat_id)

    await message.answer(
        "👋 Welcome to OLX.uz Monitor Bot!\n\n"
        "I will periodically check OLX.uz for new rental listings "
        "and send them to you instantly.\n\n"
        "Commands:\n"
        "/filters — Set your search filters\n"
        "/search_now — Run a search immediately\n"
        "/status — View current filter settings\n"
        "/interval — Change check frequency\n\n"
        "Start by setting up your filters with /filters"
    )


@router.message(Command("filters"))
async def cmd_filters(message: Message, state: FSMContext):
    await state.set_state(FilterSetup.category)
    await message.answer(
        "Select listing category:",
        reply_markup=category_keyboard(),
    )


@router.callback_query(FilterSetup.category, F.data.startswith("cat:"))
async def filter_category(cq: CallbackQuery, state: FSMContext):
    cat = cq.data.split(":", 1)[1]
    await state.update_data(category=cat)
    await state.set_state(FilterSetup.price_min)
    await cq.message.edit_text(
        "Enter minimum price in USD (or send 0 for no minimum):\n"
        "Example: 200"
    )
    await cq.answer()


@router.message(FilterSetup.price_min)
async def filter_price_min(message: Message, state: FSMContext):
    val = parse_int(message.text)
    if val is None or val < 0:
        await message.answer("Please enter a valid number (0 or more):")
        return
    await state.update_data(price_min=val)
    await state.set_state(FilterSetup.price_max)
    await message.answer(
        "Enter maximum price in USD (or send 0 for no maximum):\n"
        "Example: 500"
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
        "Enter city name (or send 'any' for all locations):\n"
        "Example: Tashkent"
    )


@router.message(FilterSetup.location)
async def filter_location(message: Message, state: FSMContext):
    loc = message.text.strip()
    if loc.lower() in ("any", "skip", "-", ""):
        loc = ""
    await state.update_data(location=loc)
    await state.set_state(FilterSetup.rooms)
    await message.answer(
        "Select number of rooms:",
        reply_markup=rooms_keyboard(),
    )


@router.callback_query(FilterSetup.rooms, F.data.startswith("rooms:"))
async def filter_rooms(cq: CallbackQuery, state: FSMContext):
    rooms = cq.data.split(":", 1)[1]
    if rooms == "any":
        rooms = ""

    await state.update_data(rooms=rooms)
    data = await state.get_data()

    user_id = cq.from_user.id
    update_user(
        user_id,
        category=data.get("category", "arenda-dolgosrochnaya"),
        price_min=data.get("price_min", 0),
        price_max=data.get("price_max", 0),
        location=data.get("location", ""),
        rooms=data.get("rooms", ""),
    )

    await state.clear()
    summary = format_filters(data)
    await cq.message.edit_text(
        f"✅ Filters saved!\n\n{summary}\n\n"
        "Use /search_now to run a search with these filters."
    )
    await cq.answer()


@router.message(Command("search_now"))
async def cmd_search_now(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Please set up filters first with /filters")
        return

    await message.answer("🔍 Searching OLX.uz... This may take a moment.")

    ads = await scrape_for_user(
        category=user["category"],
        price_min=user["price_min"],
        price_max=user["price_max"],
        location=user["location"],
        rooms=user["rooms"],
        backfill=False,
    )

    new_count = 0
    for ad in ads:
        if is_post_sent(user_id, ad.post_url):
            continue
        await send_ad(message.bot, message.chat.id, ad)
        mark_post_sent(user_id, ad.post_url, ad.title)
        new_count += 1

    if new_count == 0:
        await message.answer("No new listings found matching your filters.")
    else:
        await message.answer(f"✅ Sent {new_count} new listing(s).")


@router.message(Command("status"))
async def cmd_status(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("No filters set. Use /filters to configure.")
        return
    await message.answer(format_filters(user))


@router.message(Command("interval"))
async def cmd_interval(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        await message.answer("Please set up filters first with /filters")
        return

    await message.answer(
        f"Current interval: every {user['interval_m']} minutes\n\n"
        "Select new check frequency:",
        reply_markup=interval_keyboard(),
    )


@router.callback_query(F.data.startswith("interval:"))
async def set_interval(cq: CallbackQuery):
    minutes = int(cq.data.split(":", 1)[1])
    user_id = cq.from_user.id
    update_user(user_id, interval_m=minutes)
    await cq.message.edit_text(
        f"✅ Check interval set to every {minutes} minutes."
    )
    await cq.answer()


async def send_ad(bot, chat_id: int, ad):
    caption = (
        f"<b>{ad.title}</b>\n\n"
        f"💰 <b>Price:</b> {format_price(ad.price_uzs, ad.price_usd)}\n"
        f"📍 <b>Location:</b> {ad.location}\n"
        f"📅 {ad.formatted_date} | <i>posted {ad.days_ago}</i>"
    )

    if ad.image_url:
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=ad.image_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=ad_keyboard(ad.post_url),
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
                backfill=False,
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


async def run_backfill(bot) -> int:
    users = get_all_active_users()
    total_sent = 0
    for user in users:
        try:
            await bot.send_message(
                user["chat_id"],
                "🔄 Backfilling listings from the last 7 days..."
            )
            ads = await scrape_for_user(
                category=user["category"],
                price_min=user["price_min"],
                price_max=user["price_max"],
                location=user["location"],
                rooms=user["rooms"],
                backfill=True,
            )
            new_count = 0
            for ad in ads:
                if is_post_sent(user["user_id"], ad.post_url):
                    continue
                await send_ad(bot, user["chat_id"], ad)
                mark_post_sent(user["user_id"], ad.post_url, ad.title)
                new_count += 1
            total_sent += new_count
            if new_count == 0:
                await bot.send_message(
                    user["chat_id"],
                    "✅ Backfill complete — no matching listings found in the last 7 days."
                )
            else:
                await bot.send_message(
                    user["chat_id"],
                    f"✅ Backfill complete — found {new_count} matching listing(s)."
                )
        except Exception as e:
            logger.error("Backfill error for user %d: %s", user["user_id"], e)
    return total_sent


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

    return (
        f"📋 <b>Your Filters</b>\n"
        f"• Category: {cat}\n"
        f"• Price: {'$' + str(pmin) if isinstance(pmin, int) else pmin}"
        f" - {'$' + str(pmax) if isinstance(pmax, int) else pmax}\n"
        f"• Location: {loc}\n"
        f"• Rooms: {rooms}\n"
        f"• Check interval: every {interval} min"
    )


def parse_int(text: str) -> int | None:
    text = text.strip().replace(",", "").replace(" ", "")
    try:
        return int(float(text))
    except (ValueError, TypeError):
        return None
