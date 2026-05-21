from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def ad_keyboard(post_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="View on OLX", url=post_url)
    return builder.as_markup()


def interval_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for minutes in [15, 30, 60, 180, 360, 720, 1440]:
        label = f"{minutes // 60}h" if minutes >= 60 else f"{minutes}min"
        builder.button(text=label, callback_data=f"interval:{minutes}")
    builder.adjust(4)
    return builder.as_markup()


def category_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Long-term rent", callback_data="cat:arenda-dolgosrochnaya")
    builder.button(text="Sale", callback_data="cat:prodazha")
    builder.button(text="Rooms", callback_data="cat:komnaty")
    builder.adjust(1)
    return builder.as_markup()


def rooms_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 room", callback_data="rooms:1")
    builder.button(text="2 rooms", callback_data="rooms:2")
    builder.button(text="3 rooms", callback_data="rooms:3")
    builder.button(text="4+ rooms", callback_data="rooms:4+")
    builder.button(text="Any (skip)", callback_data="rooms:any")
    builder.adjust(2)
    return builder.as_markup()


def backlog_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in [1, 3, 7, 14, 30]:
        builder.button(text=f"{days} day{'s' if days > 1 else ''}", callback_data=f"backlog:{days}")
    builder.adjust(3)
    return builder.as_markup()


def load_more_keyboard(user_id: int, total: int, shown: int) -> InlineKeyboardMarkup:
    remaining = total - shown
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"Load next 10 ({remaining} left)",
        callback_data=f"load_more:{user_id}",
    )
    return builder.as_markup()
