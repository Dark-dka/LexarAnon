"""
User sync service: creates or updates TelegramUser from Telegram user data.
Supports optional referrer_id for referral tracking (only on first registration).
"""
import logging
from typing import Optional

from aiogram.types import User as TelegramUserData
from aiogram import Bot
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from bot.services.media import download_profile_photo

logger = logging.getLogger(__name__)


async def sync_user(
    tg_user: TelegramUserData,
    bot: Bot,
    referrer_id: Optional[int] = None,
) -> tuple[TelegramUser, bool]:
    """
    Create or update a TelegramUser from Telegram user data.
    Also downloads and updates the profile photo.

    Returns (user, created) tuple.
    If referrer_id is provided and the user is new — links referred_by.
    """
    defaults = {
        'username': tg_user.username,
        'first_name': tg_user.first_name,
        'last_name': tg_user.last_name,
        'language_code': tg_user.language_code,
        'is_active': True,
    }

    user, created = await sync_to_async(TelegramUser.objects.update_or_create)(
        telegram_id=tg_user.id,
        defaults=defaults,
    )

    # Set referrer only on new registration (and only if not self-referral)
    if created and referrer_id and referrer_id != tg_user.id:
        try:
            referrer = await sync_to_async(TelegramUser.objects.get)(
                telegram_id=referrer_id
            )
            user.referred_by = referrer
            await sync_to_async(user.save)(update_fields=['referred_by'])
            logger.info(f'User {user} referred by {referrer}')
        except TelegramUser.DoesNotExist:
            logger.warning(f'Referrer {referrer_id} not found in DB')

    # Download / update profile photo
    photo_path = await download_profile_photo(bot, tg_user.id)
    if photo_path:
        user.profile_photo = photo_path
        await sync_to_async(user.save)(update_fields=['profile_photo'])

    action = 'Created' if created else 'Updated'
    logger.info(f'{action} user: {user}')
    return user, created
