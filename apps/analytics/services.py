"""
Async-safe analytics tracking service.
Usage:
    from apps.analytics.services import track
    await track(telegram_id, 'start_opened', campaign_code='abc')
"""
import logging
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


async def track(telegram_id: int, event_type: str, **meta):
    """
    Fire-and-forget event tracking.
    Never raises — silently logs errors so it never breaks handlers.
    """
    try:
        from apps.analytics.models import UserEvent
        from apps.users.models import TelegramUser

        user = await sync_to_async(
            TelegramUser.objects.filter(telegram_id=telegram_id).first
        )()
        if not user:
            return

        await sync_to_async(UserEvent.objects.create)(
            user=user,
            event_type=event_type,
            meta=meta or {},
        )
    except Exception as e:
        logger.warning(f'Analytics track error ({event_type}): {e}')
