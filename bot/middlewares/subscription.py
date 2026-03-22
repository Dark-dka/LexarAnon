"""
Subscription middleware.
Checks that the user is subscribed to all active RequiredChannels and has
confirmed launching all active RequiredBots before allowing them to
interact with the bot.

Channel check: real Telegram API verification (fail-closed).
Bot check: persistent DB-based self-confirmation (no real server-side verification).
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
ALWAYS_ALLOWED_CALLBACKS = {'check_subscription', 'check_bots', 'inline_search'}
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
    Intercepts every message/callback and ensures the user:
    1. Is subscribed to all active RequiredChannels (real Telegram API check).
    2. Has confirmed launching all active RequiredBots (DB-persistent self-confirm).
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
            if any(event.data.startswith(p) for p in ALWAYS_ALLOWED_CALLBACK_PREFIXES):
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

        # ── 1. Check channel subscriptions (real Telegram API) ─────────
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
                    if member.status not in ('member', 'administrator', 'creator'):
                        not_subscribed.append(channel)
                except (TelegramBadRequest, TelegramForbiddenError) as e:
                    # Fail-closed: can't verify → block
                    logger.warning(
                        f'Channel check failed (middleware): '
                        f'channel={channel.channel_username} user={user.id} '
                        f'error={type(e).__name__}: {e}'
                    )
                    not_subscribed.append(channel)
                except Exception as e:
                    logger.error(
                        f'Unexpected channel check error (middleware): '
                        f'channel={channel.channel_username} user={user.id} '
                        f'error={type(e).__name__}: {e}'
                    )
                    not_subscribed.append(channel)

            if not_subscribed:
                # Determine progress step
                has_bots = await sync_to_async(RequiredBot.objects.filter(is_active=True).exists)()
                progress = texts.PROGRESS_1_OF_3 if has_bots else texts.PROGRESS_1_OF_3

                if isinstance(event, CallbackQuery):
                    try:
                        await event.message.edit_text(
                            texts.SUBSCRIPTION_REQUIRED.format(progress=progress),
                            reply_markup=subscribe_keyboard(not_subscribed),
                        )
                    except Exception:
                        await event.message.answer(
                            texts.SUBSCRIPTION_REQUIRED.format(progress=progress),
                            reply_markup=subscribe_keyboard(not_subscribed),
                        )
                else:
                    await event.answer(
                        texts.SUBSCRIPTION_REQUIRED.format(progress=progress),
                        reply_markup=subscribe_keyboard(not_subscribed),
                    )
                return  # Block

        # ── 2. Check required bots (DB-persistent self-confirm) ────────
        bots_qs = RequiredBot.objects.filter(is_active=True)
        required_bots = await sync_to_async(list)(bots_qs)

        if required_bots:
            from apps.users.models import TelegramUser as TU, BotClickEvent
            try:
                tg_user = await sync_to_async(TU.objects.get)(telegram_id=user.id)
            except TU.DoesNotExist:
                return await handler(event, data)

            latest_bot = await sync_to_async(
                bots_qs.order_by('-created_at').first
            )()

            needs_check = (
                tg_user.bots_confirmed_at is None
                or (latest_bot and tg_user.bots_confirmed_at < latest_bot.created_at)
            )

            if needs_check:
                # Load confirmed bots from DB
                confirmed = set(await sync_to_async(list)(
                    BotClickEvent.objects.filter(
                        user=tg_user,
                        self_confirmed_at__isnull=False,
                    ).values_list('bot_username', flat=True)
                ))

                # Determine progress step
                has_channels = await sync_to_async(RequiredChannel.objects.filter(is_active=True).exists)()
                step = 2 if has_channels else 1
                progress = f'▪▪▫ Шаг {step} из 3'

                if isinstance(event, CallbackQuery):
                    try:
                        await event.message.edit_text(
                            texts.BOTS_REQUIRED.format(progress=progress),
                            reply_markup=bots_keyboard(required_bots, confirmed=confirmed),
                        )
                    except Exception:
                        await event.message.answer(
                            texts.BOTS_REQUIRED.format(progress=progress),
                            reply_markup=bots_keyboard(required_bots, confirmed=confirmed),
                        )
                else:
                    await event.answer(
                        texts.BOTS_REQUIRED.format(progress=progress),
                        reply_markup=bots_keyboard(required_bots, confirmed=confirmed),
                    )
                return  # Block

        # ── All checks passed ────────────────────────────────────────────
        return await handler(event, data)

