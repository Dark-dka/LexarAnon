"""
Subscription middleware.
Checks that the user is subscribed to all active RequiredChannels before
allowing them to interact with the bot.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from asgiref.sync import sync_to_async

from apps.users.models import RequiredChannel
from bot import texts
from bot.keyboards import subscribe_keyboard

logger = logging.getLogger(__name__)

# Callbacks that are always allowed through (even without subscription)
ALWAYS_ALLOWED_CALLBACKS = {'check_subscription'}

# Reply button texts that always pass through (cancel search, stop/next chat, report)
ALWAYS_ALLOWED_TEXTS = {
    '❌ Отменить поиск',
    '⏹ Остановить',
    '⏭ Следующий',
    '🚨 Пожаловаться',
}

# Commands that always pass through
ALWAYS_ALLOWED_COMMANDS = {'/start', '/help'}


class SubscriptionMiddleware(BaseMiddleware):
    """
    Intercepts every message/callback and ensures the user is subscribed
    to all active RequiredChannels. If not — sends the subscription prompt
    and stops the handler chain.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Resolve user and bot from the event
        if isinstance(event, CallbackQuery):
            user = event.from_user
            # Always let whitelisted callbacks through
            if event.data in ALWAYS_ALLOWED_CALLBACKS:
                return await handler(event, data)
        elif isinstance(event, Message):
            user = event.from_user
            # Always let control buttons and commands through
            if event.text in ALWAYS_ALLOWED_TEXTS:
                return await handler(event, data)
            if event.text and event.text.split()[0] in ALWAYS_ALLOWED_COMMANDS:
                return await handler(event, data)
        else:
            return await handler(event, data)

        bot: Bot = data['bot']

        # Fetch active channels from DB
        channels = await sync_to_async(list)(
            RequiredChannel.objects.filter(is_active=True)
        )

        if not channels:
            return await handler(event, data)

        # Check subscription to every channel
        not_subscribed = []
        for channel in channels:
            try:
                member = await bot.get_chat_member(
                    chat_id=channel.channel_username,
                    user_id=user.id,
                )
                # Statuses that count as "subscribed"
                if member.status not in ('member', 'administrator', 'creator'):
                    not_subscribed.append(channel)
            except (TelegramBadRequest, TelegramForbiddenError) as e:
                logger.warning(
                    f'Cannot check subscription for {channel.channel_username}: {e}'
                )
                # If we can't check — let the user through to avoid false blocks
                continue
            except Exception as e:
                logger.error(
                    f'Unexpected error checking subscription for {channel.channel_username}: {e}'
                )
                continue

        if not not_subscribed:
            return await handler(event, data)

        # User is missing at least one subscription — send prompt
        kb = subscribe_keyboard(not_subscribed)

        if isinstance(event, Message):
            await event.answer(texts.SUBSCRIPTION_REQUIRED, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.message.answer(texts.SUBSCRIPTION_REQUIRED, reply_markup=kb)
            await event.answer()

        return None  # Stop handler chain
