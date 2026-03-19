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
