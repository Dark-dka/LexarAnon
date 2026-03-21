"""
Reply keyboards for the Telegram bot.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


# Main menu keyboard
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🔍 Найти собеседника')],
        [
            KeyboardButton(text='👤 Профиль'),
            KeyboardButton(text='⚙️ Настройки поиска'),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# Chat keyboard (during active chat)
chat_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text='⏹ Остановить'),
            KeyboardButton(text='⏭ Следующий'),
        ],
        [
            KeyboardButton(text='🚨 Пожаловаться'),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# Searching keyboard
searching_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='❌ Отменить поиск')],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)

# Gender selection
gender_select = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='👦 Я парень', callback_data='gender_male'),
            InlineKeyboardButton(text='👧 Я девушка', callback_data='gender_female'),
        ],
    ],
)

# Search gender preference
search_gender_select = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text='👦 Парней', callback_data='search_male'),
            InlineKeyboardButton(text='👧 Девушек', callback_data='search_female'),
        ],
        [
            InlineKeyboardButton(text='🔀 Всех', callback_data='search_any'),
        ],
    ],
)

# Like / Dislike after chat
def rate_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='👍', callback_data=f'rate_like_{session_id}'),
                InlineKeyboardButton(text='👎', callback_data=f'rate_dislike_{session_id}'),
            ],
        ],
    )


# Subscription required keyboard — built dynamically from DB channels
def subscribe_keyboard(channels) -> InlineKeyboardMarkup:
    """Build an inline keyboard with a button for every required channel + a check button."""
    rows = [
        [InlineKeyboardButton(text=f'📢 {ch.title}', url=ch.invite_link)]
        for ch in channels
    ]
    rows.append(
        [InlineKeyboardButton(text='✅ Проверить подписку', callback_data='check_subscription')]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# Required bots keyboard — built dynamically from DB bots
def bots_keyboard(bots, confirmed: set[str] | None = None) -> InlineKeyboardMarkup:
    """
    Build an inline keyboard for required bots.
    Each bot gets two buttons: open URL + individual confirm.
    confirmed = set of bot_usernames the user has already confirmed.
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

