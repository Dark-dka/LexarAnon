"""
Fallback handler — catch-all for unrecognized messages.
MUST be registered LAST so specific handlers take priority.
"""
import logging

from aiogram import Router
from aiogram.types import Message
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from bot.keyboards import main_menu
from bot import texts

router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def fallback_handler(message: Message):
    """Restore main menu keyboard for any unrecognized text."""
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    if user.is_blocked:
        await message.answer(texts.BLOCKED)
        return

    await message.answer(texts.FALLBACK, reply_markup=main_menu)

