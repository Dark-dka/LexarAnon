"""
Inline keyboards for Telegram admin panel.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

PER_PAGE = 8


# ── Main admin menu ────────────────────────────────────────────────────

admin_main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='📊 Статистика', callback_data='adm:stats'),
        InlineKeyboardButton(text='👥 Пользователи', callback_data='adm:users'),
    ],
    [
        InlineKeyboardButton(text='📢 Каналы', callback_data='adm:channels'),
        InlineKeyboardButton(text='🤖 Боты', callback_data='adm:bots'),
    ],
    [
        InlineKeyboardButton(text='💬 Чаты', callback_data='adm:chats'),
        InlineKeyboardButton(text='🖼 Медиа', callback_data='adm:media'),
    ],
    [
        InlineKeyboardButton(text='🚨 Жалобы', callback_data='adm:reports'),
        InlineKeyboardButton(text='📈 Воронка', callback_data='adm:funnel'),
    ],
    [InlineKeyboardButton(text='❌ Закрыть', callback_data='adm:close')],
])


# ── Users sub-menu ──────────────────────────────────────────────────────

users_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='🆕 Новые', callback_data='adm:users:recent:0'),
        InlineKeyboardButton(text='🟢 Живые 24ч', callback_data='adm:users:alive_1d:0'),
    ],
    [
        InlineKeyboardButton(text='🟡 Живые 7д', callback_data='adm:users:alive_7d:0'),
        InlineKeyboardButton(text='💀 Мёртвые 3д+', callback_data='adm:users:dead_3d:0'),
    ],
    [
        InlineKeyboardButton(text='☠️ Мёртвые 30д+', callback_data='adm:users:dead_30d:0'),
        InlineKeyboardButton(text='🚫 Заблок.', callback_data='adm:users:blocked:0'),
    ],
    [InlineKeyboardButton(text='🔍 Поиск', callback_data='adm:users:search')],
    [InlineKeyboardButton(text='⬅️ Меню', callback_data='adm:menu')],
])


# ── Chats sub-menu ──────────────────────────────────────────────────────

chats_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='🟢 Активные', callback_data='adm:chats:active:0'),
        InlineKeyboardButton(text='🔴 Завершённые', callback_data='adm:chats:closed:0'),
    ],
    [InlineKeyboardButton(text='⬅️ Меню', callback_data='adm:menu')],
])


# ── Funnel periods ──────────────────────────────────────────────────────

funnel_menu = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='Сегодня', callback_data='adm:funnel:1'),
        InlineKeyboardButton(text='7 дней', callback_data='adm:funnel:7'),
        InlineKeyboardButton(text='30 дней', callback_data='adm:funnel:30'),
    ],
    [InlineKeyboardButton(text='⬅️ Меню', callback_data='adm:menu')],
])


# ── Helpers ──────────────────────────────────────────────────────────────

def back_button(callback_data: str = 'adm:menu') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='⬅️ Назад', callback_data=callback_data)],
    ])


def pagination_kb(prefix: str, page: int, total: int, per_page: int = PER_PAGE,
                   back_cb: str = 'adm:menu') -> InlineKeyboardMarkup:
    """Build pagination row + back button."""
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text='◀️', callback_data=f'{prefix}:{page - 1}'))
    if (page + 1) * per_page < total:
        buttons.append(InlineKeyboardButton(text='▶️', callback_data=f'{prefix}:{page + 1}'))

    rows = []
    if buttons:
        rows.append(buttons)
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_card_kb(telegram_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    """Buttons for user card."""
    block_btn = InlineKeyboardButton(
        text='🔓 Разблокировать' if is_blocked else '🔒 Заблокировать',
        callback_data=f'adm:user:toggle_block:{telegram_id}',
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [block_btn],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='adm:users')],
    ])


def channel_card_kb(channel_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_btn = InlineKeyboardButton(
        text='🔴 Выключить' if is_active else '🟢 Включить',
        callback_data=f'adm:ch:toggle:{channel_id}',
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [toggle_btn],
        [InlineKeyboardButton(text='🗑 Удалить', callback_data=f'adm:ch:delete:{channel_id}')],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='adm:channels')],
    ])


def bot_card_kb(bot_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_btn = InlineKeyboardButton(
        text='🔴 Выключить' if is_active else '🟢 Включить',
        callback_data=f'adm:bt:toggle:{bot_id}',
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [toggle_btn],
        [InlineKeyboardButton(text='🗑 Удалить', callback_data=f'adm:bt:delete:{bot_id}')],
        [InlineKeyboardButton(text='⬅️ Назад', callback_data='adm:bots')],
    ])


def confirm_delete_kb(prefix: str, obj_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='✅ Да, удалить', callback_data=f'{prefix}:confirm_del:{obj_id}'),
            InlineKeyboardButton(text='❌ Отмена', callback_data=f'{prefix[:-1]}s'),
        ],
    ])


def channels_list_kb(channels, page: int = 0) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        status = '🟢' if ch.is_active else '🔴'
        rows.append([InlineKeyboardButton(
            text=f'{status} {ch.title}',
            callback_data=f'adm:ch:view:{ch.id}',
        )])
    rows.append([InlineKeyboardButton(text='➕ Добавить канал', callback_data='adm:ch:add')])
    rows.append([InlineKeyboardButton(text='⬅️ Меню', callback_data='adm:menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def bots_list_kb(bots, page: int = 0) -> InlineKeyboardMarkup:
    rows = []
    for b in bots:
        status = '🟢' if b.is_active else '🔴'
        rows.append([InlineKeyboardButton(
            text=f'{status} {b.title}',
            callback_data=f'adm:bt:view:{b.id}',
        )])
    rows.append([InlineKeyboardButton(text='➕ Добавить бота', callback_data='adm:bt:add')])
    rows.append([InlineKeyboardButton(text='⬅️ Меню', callback_data='adm:menu')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
