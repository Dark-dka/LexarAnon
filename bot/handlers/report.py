"""
Report handler: user complaints.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.types import Message
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from apps.reports.models import Report
from bot.services.matchmaking import matchmaking
from bot.keyboards import main_menu
from bot import texts
from apps.analytics.services import track

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == '🚨 Жалоба')
@router.message(F.text == '🚨 Пожаловаться')
async def report_partner(message: Message, bot: Bot):
    """Report the current chat partner."""
    telegram_id = message.from_user.id

    session = await matchmaking.get_active_session(telegram_id)
    if not session:
        await message.answer(texts.REPORT_NO_CHAT, reply_markup=main_menu)
        return

    partner_tid = await matchmaking.get_partner_telegram_id(telegram_id)
    if not partner_tid:
        await message.answer(texts.RELAY_FAILED)
        return

    from_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    against_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=partner_tid)

    await sync_to_async(Report.objects.create)(
        from_user=from_user,
        against_user=against_user,
        chat_session=session,
        reason='Жалоба через кнопку бота (автоматическая)',
    )

    await matchmaking.end_session(telegram_id)

    await track(telegram_id, 'report_sent', session_id=session.id)

    await message.answer(texts.REPORT_SENT, reply_markup=main_menu)

    try:
        await bot.send_message(
            partner_tid,
            texts.CHAT_ENDED_BY_PARTNER,
            reply_markup=main_menu,
        )
    except Exception as e:
        logger.warning(f'Failed to notify partner {partner_tid}: {e}')

    logger.info(f'Report created: {telegram_id} → {partner_tid}')
