"""
Subscription middleware.
Checks that the user is subscribed to all active RequiredChannels and has
confirmed launching all active RequiredBots before allowing them to
interact with the bot.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from asgiref.sync import sync_to_async

from apps.users.models import RequiredChannel, RequiredBot
from bot import texts
from bot.keyboards import subscribe_keyboard, bots_keyboard

logger = logging.getLogger(__name__)

# Callbacks that are always allowed through (even without subscription)
ALWAYS_ALLOWED_CALLBACKS = {'check_subscription', 'check_bots'}

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
    Intercepts every message/callback and ensures the user:
    1. Is subscribed to all active RequiredChannels.
    2. Has confirmed launching all active RequiredBots.
    If any check fails — sends the corresponding prompt and stops the handler chain.
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

        # ── 1. Check channel subscriptions ───────────────────────────────────
        channels = await sync_to_async(list)(
            RequiredChannel.objects.filter(is_active=True)
        )

        if channels:
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

            if not_subscribed:
                # User is missing at least one channel subscription — send prompt
                kb = subscribe_keyboard(not_subscribed)
                if isinstance(event, Message):
                    await event.answer(texts.SUBSCRIPTION_REQUIRED, reply_markup=kb)
                elif isinstance(event, CallbackQuery):
                    await event.message.answer(texts.SUBSCRIPTION_REQUIRED, reply_markup=kb)
                    await event.answer()
                return None  # Stop handler chain

        # ── 2. Check required bots ────────────────────────────────────────────
        required_bots = await sync_to_async(list)(
            RequiredBot.objects.filter(is_active=True).order_by('-created_at')
        )

        if required_bots:
            latest_bot_added_at = required_bots[0].created_at

            # Fetch user's confirmation timestamp from DB
            try:
                from apps.users.models import TelegramUser
                db_user = await sync_to_async(TelegramUser.objects.get)(
                    telegram_id=user.id
                )
                confirmed_at = db_user.bots_confirmed_at
            except Exception:
                confirmed_at = None

            # Block only if user never confirmed OR confirmed before a newer bot was added
            needs_confirm = (
                confirmed_at is None or
                confirmed_at < latest_bot_added_at
            )

            if needs_confirm:
                kb = bots_keyboard(required_bots)
                if isinstance(event, Message):
                    await event.answer(texts.BOTS_REQUIRED, reply_markup=kb)
                elif isinstance(event, CallbackQuery):
                    await event.message.answer(texts.BOTS_REQUIRED, reply_markup=kb)
                    await event.answer()
                return None  # Stop handler chain

        return await handler(event, data)
