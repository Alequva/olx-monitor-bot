from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Set Filters")],
            [KeyboardButton(text="⏰ Interval"), KeyboardButton(text="📅 Backlog Days")],
            [KeyboardButton(text="🔎 Search Now"), KeyboardButton(text="📋 Status")],
        ],
        resize_keyboard=True,
    )


def ad_keyboard(post_url: str, telegram_url: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="View on OLX", url=post_url)
    if telegram_url:
        builder.button(text="Write in Telegram", url=telegram_url)
    return builder.as_markup()


def interval_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="15min"), KeyboardButton(text="30min"), KeyboardButton(text="1h")],
            [KeyboardButton(text="3h"), KeyboardButton(text="6h"), KeyboardButton(text="12h"), KeyboardButton(text="24h")],
        ],
        resize_keyboard=True,
    )


def category_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Long-term rent")],
            [KeyboardButton(text="Sale")],
            [KeyboardButton(text="Rooms")],
        ],
        resize_keyboard=True,
    )


def cities_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Tashkent"), KeyboardButton(text="Samarkand")],
            [KeyboardButton(text="Bukhara"), KeyboardButton(text="Fergana")],
            [KeyboardButton(text="Namangan"), KeyboardButton(text="Andijan")],
            [KeyboardButton(text="Kokand"), KeyboardButton(text="Nukus")],
            [KeyboardButton(text="Urgench"), KeyboardButton(text="Navoi")],
            [KeyboardButton(text="Jizzakh"), KeyboardButton(text="Qarshi")],
            [KeyboardButton(text="Termez"), KeyboardButton(text="Gulistan")],
            [KeyboardButton(text="Any (skip)")],
        ],
        resize_keyboard=True,
    )


def rooms_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 room"), KeyboardButton(text="2 rooms")],
            [KeyboardButton(text="3 rooms"), KeyboardButton(text="4+ rooms")],
            [KeyboardButton(text="Any")],
        ],
        resize_keyboard=True,
    )


def rent_price_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="0"), KeyboardButton(text="100"), KeyboardButton(text="200"), KeyboardButton(text="300")],
            [KeyboardButton(text="500"), KeyboardButton(text="800"), KeyboardButton(text="1000"), KeyboardButton(text="1500")],
            [KeyboardButton(text="Write custom")],
        ],
        resize_keyboard=True,
    )


def sale_price_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="0"), KeyboardButton(text="5000"), KeyboardButton(text="10000"), KeyboardButton(text="15000")],
            [KeyboardButton(text="20000"), KeyboardButton(text="30000"), KeyboardButton(text="40000"), KeyboardButton(text="50000")],
            [KeyboardButton(text="Write custom")],
        ],
        resize_keyboard=True,
    )


def get_price_keyboard(category: str = "") -> ReplyKeyboardMarkup:
    if category in ("prodazha", "sale"):
        return sale_price_reply_keyboard()
    return rent_price_reply_keyboard()


def gender_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="For women")],
            [KeyboardButton(text="For men")],
            [KeyboardButton(text="No preference")],
        ],
        resize_keyboard=True,
    )


def backlog_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1 day"), KeyboardButton(text="3 days"), KeyboardButton(text="7 days")],
            [KeyboardButton(text="14 days"), KeyboardButton(text="30 days")],
        ],
        resize_keyboard=True,
    )


def load_more_keyboard(user_id: int, total: int, shown: int) -> InlineKeyboardMarkup:
    remaining = total - shown
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"Load next 10 ({remaining} left)",
        callback_data=f"load_more:{user_id}",
    )
    return builder.as_markup()
