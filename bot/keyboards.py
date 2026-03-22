"""
Reply and inline keyboards for the Telegram bot.
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


# ── Main menu ────────────────────────────────────────────────────────────

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🔍 Найти собеседника')],
        [
            KeyboardButton(text='👤 Профиль'),
            KeyboardButton(text='ℹ️ Как это работает'),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# ── Chat menu (during active chat) ──────────────────────────────────────

chat_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='⏹ Стоп'),
            KeyboardButton(text='⏭ Дальше'),
        ],
        [KeyboardButton(text='🚨 Жалоба')],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# ── Searching menu ──────────────────────────────────────────────────────

searching_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='❌ Отменить поиск')],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


# ── Rating ───────────────────────────────────────────────────────────────

def rate_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='👍', callback_data=f'rate_like_{session_id}'),
                InlineKeyboardButton(text='👎', callback_data=f'rate_dislike_{session_id}'),
            ],
        ],
    )


# ── After rating — nudge to search again ────────────────────────────────

search_again_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Найти нового собеседника', callback_data='inline_search')],
    ],
)

# ── After activation complete — nudge to first search ────────────────────

search_now_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Начать поиск', callback_data='inline_search')],
    ],
)

# ── Profile actions ──────────────────────────────────────────────────────

profile_actions_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text='🔍 Найти собеседника', callback_data='inline_search')],
    ],
)


# ── Required channels keyboard ──────────────────────────────────────────

def subscribe_keyboard(channels) -> InlineKeyboardMarkup:
    """Button for every required channel + check button."""
    rows = [
        [InlineKeyboardButton(text=f'📢 {ch.title}', url=ch.invite_link)]
        for ch in channels
    ]
    rows.append(
        [InlineKeyboardButton(text='✅ Я подписался', callback_data='check_subscription')]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Required bots keyboard ──────────────────────────────────────────────

def bots_keyboard(bots, confirmed: set[str] | None = None) -> InlineKeyboardMarkup:
    """
    Two buttons per bot: open URL + individual confirm.
    confirmed = set of bot_usernames already confirmed.
    """
    if confirmed is None:
        confirmed = set()

    rows = []
    for bot in bots:
        username = bot.bot_username.lstrip('@')
        is_done = username in confirmed
        tick = '✅' if is_done else '☑️'
        rows.append([
            InlineKeyboardButton(text=f'🤖 {bot.title}', url=bot.invite_link),
            InlineKeyboardButton(
                text=f'{tick} Запустил',
                callback_data=f'bot_done_{username}',
            ),
        ])

    rows.append(
        [InlineKeyboardButton(text='🎯 Готово', callback_data='check_bots')]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
