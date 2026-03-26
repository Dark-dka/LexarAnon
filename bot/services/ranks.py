"""
Rank system — every 100 chats, user levels up.
"""
from asgiref.sync import sync_to_async
from django.db.models import Q

from apps.users.models import TelegramUser
from apps.chat.models import ChatSession

# (min_chats, emoji, title)
RANKS = [
    (0,    '🐣', 'Новичок'),
    (500,  '👤', 'Тень'),
    (1000, '🎭', 'Маска'),
    (1500, '🌙', 'Призрак'),
    (2000, '⚡', 'Фантом'),
    (2500, '🔥', 'Легенда'),
    (3000, '💎', 'Мифический'),
    (3500, '👑', 'Бессмертный'),
]


def get_rank(chat_count: int) -> tuple[str, str, int]:
    """
    Returns (emoji, title, rank_index) for a given chat count.
    """
    result = RANKS[0]
    idx = 0
    for i, (min_chats, emoji, title) in enumerate(RANKS):
        if chat_count >= min_chats:
            result = (emoji, title, i)
            idx = i
    return result[0], result[1], idx


def get_next_rank(chat_count: int) -> tuple[int, str, str] | None:
    """
    Returns (chats_needed, emoji, title) for the next rank, or None if max.
    """
    for min_chats, emoji, title in RANKS:
        if chat_count < min_chats:
            return (min_chats - chat_count, emoji, title)
    return None


def rank_label(chat_count: int) -> str:
    """Short rank string for display, e.g. '🌀 Вихрь'"""
    emoji, title, _ = get_rank(chat_count)
    return f'{emoji} {title}'


async def get_user_chat_count(telegram_id: int) -> int:
    """Get total closed chats for a user."""
    def _q():
        try:
            user = TelegramUser.objects.get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist:
            return 0
        return ChatSession.objects.filter(
            Q(user1=user) | Q(user2=user),
            status='closed',
        ).count()
    return await sync_to_async(_q)()


async def get_user_rank(telegram_id: int) -> tuple[str, str, int, int]:
    """
    Returns (emoji, title, rank_index, chat_count) for a user.
    """
    count = await get_user_chat_count(telegram_id)
    emoji, title, idx = get_rank(count)
    return emoji, title, idx, count


async def check_rank_up(telegram_id: int) -> tuple[str, str] | None:
    """
    Check if user just ranked up (call after chat ends).
    Returns (emoji, new_title) if ranked up, None otherwise.
    """
    count = await get_user_chat_count(telegram_id)
    # Check if exactly on a boundary
    for min_chats, emoji, title in RANKS:
        if min_chats > 0 and count == min_chats:
            return emoji, title
    return None
