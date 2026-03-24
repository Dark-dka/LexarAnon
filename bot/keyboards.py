"""
Bot keyboards — main menu, subscribe, bots, search, rating, profile.
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


# ── Main menu (reply keyboard) ──────────────────────────────────────────

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🔍 Найти собеседника')],
        [
            KeyboardButton(text='👤 Профиль'),
            KeyboardButton(text='ℹ️ Как это работает'),
        ],
    ],
    resize_keyboard=True,
)


# ── Chat controls ───────────────────────────────────────────────────────

chat_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='⏹ Стоп'),
            KeyboardButton(text='⏭ Дальше'),
        ],
        [KeyboardButton(text='🚨 Пожаловаться')],
    ],
    resize_keyboard=True,
)


# ── Search controls ─────────────────────────────────────────────────────

searching_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text='❌ Отменить поиск')]],
    resize_keyboard=True,
)


# ── Search prompt keyboards ─────────────────────────────────────────────

search_now_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Найти собеседника', callback_data='inline_search')],
    ],
)

search_again_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Найти ещё', callback_data='inline_search')],
    ],
)


# ── Rating keyboard ─────────────────────────────────────────────────────

def rate_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='👍', callback_data=f'rate_like_{session_id}'),
                InlineKeyboardButton(text='👎', callback_data=f'rate_dislike_{session_id}'),
            ],
        ],
    )


# ── Profile actions ─────────────────────────────────────────────────────

profile_actions_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Найти собеседника', callback_data='inline_search')],
    ],
)


# ── Combined activation keyboard (channels + bots in one) ───────────────

def activation_keyboard(
    channels=None, bots=None, confirmed_bots: set[str] | None = None,
) -> InlineKeyboardMarkup:
    """
    Single keyboard for all activation steps:
    - Channel subscribe links
    - Bot open links + individual confirm buttons
    - One unified ✅ check button
    """
    if confirmed_bots is None:
        confirmed_bots = set()

    rows = []

    # Channel links
    if channels:
        for ch in channels:
            rows.append([InlineKeyboardButton(text=f'📢 {ch.title}', url=ch.invite_link)])

    # Bot links + confirm
    if bots:
        for bot in bots:
            username = bot.bot_username.lstrip('@')
            is_done = username in confirmed_bots
            tick = '✅' if is_done else '☑️'
            rows.append([
                InlineKeyboardButton(text=f'🤖 {bot.title}', url=bot.invite_link),
                InlineKeyboardButton(
                    text=f'{tick} Отметить',
                    callback_data=f'bot_done_{username}',
                ),
            ])

    rows.append(
        [InlineKeyboardButton(text='✅ Проверить и продолжить', callback_data='check_activation')]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Keep old names as aliases for backwards compatibility
def subscribe_keyboard(channels) -> InlineKeyboardMarkup:
    return activation_keyboard(channels=channels)


def bots_keyboard(bots, confirmed: set[str] | None = None) -> InlineKeyboardMarkup:
    return activation_keyboard(bots=bots, confirmed_bots=confirmed)

