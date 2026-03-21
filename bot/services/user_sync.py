"""
User sync service: creates or updates TelegramUser from Telegram user data.
Supports optional campaign_code for referral campaign tracking (only on first registration).
"""
import logging
from typing import Optional

from aiogram.types import User as TelegramUserData
from aiogram import Bot
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, ReferralCampaign
from bot.services.media import download_profile_photo

logger = logging.getLogger(__name__)


async def sync_user(
    tg_user: TelegramUserData,
    bot: Bot,
    campaign_code: Optional[str] = None,
) -> tuple[TelegramUser, bool]:
    """
    Create or update a TelegramUser from Telegram user data.
    Also downloads and updates the profile photo.

    Returns (user, created) tuple.
    If campaign_code is provided and user is new — links campaign.
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

    # Link campaign only on new registration
    if created and campaign_code:
        try:
            campaign = await sync_to_async(ReferralCampaign.objects.get)(
                code=campaign_code, is_active=True
            )
            user.campaign = campaign
            await sync_to_async(user.save)(update_fields=['campaign'])
            logger.info(f'User {user} came from campaign [{campaign_code}]')
        except ReferralCampaign.DoesNotExist:
            logger.warning(f'Campaign code "{campaign_code}" not found or inactive')

    # Download / update profile photo
    photo_path = await download_profile_photo(bot, tg_user.id)
    if photo_path:
        user.profile_photo = photo_path
        await sync_to_async(user.save)(update_fields=['profile_photo'])

    action = 'Created' if created else 'Updated'
    logger.info(f'{action} user: {user}')
    return user, created
