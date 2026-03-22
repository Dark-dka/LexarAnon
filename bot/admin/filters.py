"""
Admin access filter — checks telegram_id against TELEGRAM_ADMIN_IDS.
"""
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from bot.config import TELEGRAM_ADMIN_IDS


class AdminFilter(BaseFilter):
    """Only allows messages/callbacks from admin telegram IDs."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else 0
        return user_id in TELEGRAM_ADMIN_IDS


def is_admin(telegram_id: int) -> bool:
    """Helper function for inline checks."""
    return telegram_id in TELEGRAM_ADMIN_IDS
