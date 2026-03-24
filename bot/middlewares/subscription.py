"""
Subscription middleware.
Checks channels + bots in ONE combined message.

Channel check: real Telegram API (fail-open on error — warns admin in logs).
Bot check: DB-based self-confirmation.
"""
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from asgiref.sync import sync_to_async

from apps.users.models import RequiredChannel, RequiredBot
from bot import texts
from bot.keyboards import activation_keyboard

logger = logging.getLogger(__name__)

# Callbacks that are always allowed through
ALWAYS_ALLOWED_CALLBACKS = {'check_activation', 'check_subscription', 'check_bots', 'inline_search'}
ALWAYS_ALLOWED_CALLBACK_PREFIXES = {'bot_done_', 'adm:'}

# Reply button texts that always pass through
ALWAYS_ALLOWED_TEXTS = {
    '❌ Отменить поиск',
    '⏹ Стоп',
    '⏹ Остановить',
    '⏭ Дальше',
    '⏭ Следующий',
    '🚨 Жалоба',
    '🚨 Пожаловаться',
}

# Commands that always pass through
ALWAYS_ALLOWED_COMMANDS = {'/start', '/help', '/begu'}


class SubscriptionMiddleware(BaseMiddleware):
    """
    Single-pass check: shows ONE message with all required channels + bots.
    Only blocks if there are unsubscribed channels or unconfirmed bots.
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
            if event.data in ALWAYS_ALLOWED_CALLBACKS:
                return await handler(event, data)
            if any(event.data.startswith(p) for p in ALWAYS_ALLOWED_CALLBACK_PREFIXES):
                return await handler(event, data)
        elif isinstance(event, Message):
            user = event.from_user
            if event.text in ALWAYS_ALLOWED_TEXTS:
                return await handler(event, data)
            if event.text and event.text.split()[0] in ALWAYS_ALLOWED_COMMANDS:
                return await handler(event, data)
        else:
            return await handler(event, data)

        bot: Bot = data['bot']

        # Load required channels and bots
        channels = await sync_to_async(list)(
            RequiredChannel.objects.filter(is_active=True)
        )
        required_bots = await sync_to_async(list)(
            RequiredBot.objects.filter(is_active=True)
        )

        # If nothing required — pass through
        if not channels and not required_bots:
            return await handler(event, data)

        # ── Check channels (fail-open on API error) ───────────────────
        not_subscribed_channels = []
        if channels:
            for channel in channels:
                try:
                    member = await bot.get_chat_member(
                        chat_id=channel.channel_username,
                        user_id=user.id,
                    )
                    if member.status not in ('member', 'administrator', 'creator'):
                        not_subscribed_channels.append(channel)
                except (TelegramBadRequest, TelegramForbiddenError) as e:
                    # Fail-OPEN: if we can't check the channel, skip it
                    # (bot is not admin in channel — can't verify)
                    logger.warning(
                        f'Channel check failed (skipping): '
                        f'channel={channel.channel_username} user={user.id} '
                        f'error={type(e).__name__}: {e}'
                    )
                except Exception as e:
                    logger.error(
                        f'Unexpected channel check error (skipping): '
                        f'channel={channel.channel_username} user={user.id} '
                        f'error={type(e).__name__}: {e}'
                    )

        # ── Check bots (DB confirmation) ──────────────────────────────
        needs_bot_check = False
        confirmed_bots = set()

        if required_bots:
            from apps.users.models import TelegramUser as TU, BotClickEvent
            try:
                tg_user = await sync_to_async(TU.objects.get)(telegram_id=user.id)

                latest_bot = await sync_to_async(
                    RequiredBot.objects.filter(is_active=True).order_by('-created_at').first
                )()

                needs_bot_check = (
                    tg_user.bots_confirmed_at is None
                    or (latest_bot and tg_user.bots_confirmed_at < latest_bot.created_at)
                )

                if needs_bot_check:
                    confirmed_bots = set(await sync_to_async(list)(
                        BotClickEvent.objects.filter(
                            user=tg_user,
                            self_confirmed_at__isnull=False,
                        ).values_list('bot_username', flat=True)
                    ))
            except TU.DoesNotExist:
                return await handler(event, data)

        # ── Decide if we need to block ────────────────────────────────
        if not not_subscribed_channels and not needs_bot_check:
            return await handler(event, data)

        # Build combined message
        show_channels = not_subscribed_channels if not_subscribed_channels else None
        show_bots = required_bots if needs_bot_check else None

        kb = activation_keyboard(
            channels=show_channels,
            bots=show_bots,
            confirmed_bots=confirmed_bots,
        )

        if isinstance(event, CallbackQuery):
            try:
                await event.message.edit_text(
                    texts.ACTIVATION_REQUIRED,
                    reply_markup=kb,
                )
            except Exception:
                await event.message.answer(
                    texts.ACTIVATION_REQUIRED,
                    reply_markup=kb,
                )
        else:
            await event.answer(
                texts.ACTIVATION_REQUIRED,
                reply_markup=kb,
            )
        return  # Block
