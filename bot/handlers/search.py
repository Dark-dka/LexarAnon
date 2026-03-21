"""
Search handler: matchmaking logic.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.types import Message
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from bot.services.matchmaking import matchmaking
from bot.keyboards import main_menu, chat_menu, searching_menu
from bot import texts
from apps.analytics.services import track

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == '🔍 Найти собеседника')
async def search_partner(message: Message, bot: Bot):
    """Start searching for a chat partner."""
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    if user.is_blocked:
        await message.answer(texts.BLOCKED)
        return

    if not user.gender:
        await message.answer(texts.NEED_GENDER)
        return

    if matchmaking.is_in_chat(telegram_id):
        await message.answer(texts.ALREADY_IN_CHAT)
        return

    if matchmaking.is_in_queue(telegram_id):
        await message.answer(texts.ALREADY_SEARCHING)
        return

    await track(telegram_id, 'search_started')

    result = await matchmaking.add_to_queue(telegram_id)

    if result is None:
        await message.answer(texts.SEARCHING, reply_markup=searching_menu)
    else:
        partner_user, session = result
        partner_tid = await sync_to_async(lambda: partner_user.telegram_id)()

        await track(telegram_id, 'match_found', session_id=session.id)
        await track(telegram_id, 'chat_started', session_id=session.id)
        await track(partner_tid, 'match_found', session_id=session.id)
        await track(partner_tid, 'chat_started', session_id=session.id)

        await message.answer(texts.PARTNER_FOUND, reply_markup=chat_menu)
        await bot.send_message(
            partner_tid,
            texts.PARTNER_FOUND_SHORT,
            reply_markup=chat_menu,
        )


@router.message(F.text == '❌ Отменить поиск')
async def cancel_search(message: Message):
    """Cancel searching for a partner."""
    telegram_id = message.from_user.id
    removed = await matchmaking.remove_from_queue(telegram_id)

    await track(telegram_id, 'search_cancelled')

    if removed:
        await message.answer(texts.SEARCH_CANCELLED, reply_markup=main_menu)
    else:
        await message.answer(texts.NOT_SEARCHING, reply_markup=main_menu)
