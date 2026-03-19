"""
User sync service: creates or updates TelegramUser from Telegram user data.
"""
import logging
from aiogram.types import User as TelegramUserData
from aiogram import Bot
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from bot.services.media import download_profile_photo

logger = logging.getLogger(__name__)


async def sync_user(tg_user: TelegramUserData, bot: Bot) -> TelegramUser:
    """
    Create or update a TelegramUser from Telegram user data.
    Also downloads and updates the profile photo.
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

    # Download / update profile photo
    photo_path = await download_profile_photo(bot, tg_user.id)
    if photo_path:
        user.profile_photo = photo_path
        await sync_to_async(user.save)(update_fields=['profile_photo'])

    action = 'Created' if created else 'Updated'
    logger.info(f'{action} user: {user}')
    return user
