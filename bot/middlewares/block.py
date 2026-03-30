"""
Global block middleware.
Prevents blocked users from doing anything.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser

logger = logging.getLogger(__name__)

class BlockMiddleware(BaseMiddleware):
    """
    Checks if user is blocked. If yes, intercepts the event and sends alert.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        
        # Determine the Telegram user
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            
        if user:
            # Check DB
            def _is_blocked():
                db_user = TelegramUser.objects.filter(telegram_id=user.id).first()
                return db_user.is_blocked if db_user else False

            is_blocked = await sync_to_async(_is_blocked)()
            
            if is_blocked:
                # Alert and intercept
                if isinstance(event, Message):
                    await event.answer("🚫 <b>Ваш аккаунт заблокирован.</b>\nК сожалению, вы не можете пользоваться ботом.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Аккаунт заблокирован", show_alert=True)
                return  # Do not propagate to handlers

        return await handler(event, data)
