"""
Chat handler: message relay + stop/next with like/dislike prompt.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.types import Message
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from apps.chat.models import Message as DBMessage
from bot.services.matchmaking import matchmaking
from bot.services.media import download_and_save
from bot.keyboards import main_menu, chat_menu, rate_keyboard, searching_menu
from bot import texts
from apps.analytics.services import track
from bot.admin.services import touch_activity

router = Router()
logger = logging.getLogger(__name__)


async def _save_message(session_id, sender_tid, msg_type, text=None, file_path=None, telegram_file_id=None):
    sender = await sync_to_async(TelegramUser.objects.get)(telegram_id=sender_tid)
    await sync_to_async(DBMessage.objects.create)(
        chat_session_id=session_id,
        sender=sender,
        message_type=msg_type,
        text=text,
        file=file_path or '',
        telegram_file_id=telegram_file_id or '',
    )
    await touch_activity(sender_tid)


async def _check_session(message: Message):
    telegram_id = message.from_user.id
    session = await matchmaking.get_active_session(telegram_id)
    if not session:
        await message.answer(texts.NOT_IN_CHAT, reply_markup=main_menu)
        return None
    partner_tid = await matchmaking.get_partner_telegram_id(telegram_id)
    if not partner_tid:
        return None
    return session, partner_tid


# ── Stop chat ────────────────────────────────────────────────────────────

@router.message(F.text == '⏹ Стоп')
@router.message(F.text == '⏹ Остановить')
async def stop_chat(message: Message, bot: Bot):
    """Stop the current chat session and prompt for rating."""
    telegram_id = message.from_user.id
    result = await matchmaking.end_session(telegram_id)

    if result:
        partner_tid, session = result

        await track(telegram_id, 'chat_finished', session_id=session.id)
        await track(partner_tid, 'partner_left', session_id=session.id)

        await message.answer(texts.CHAT_ENDED_BY_YOU, reply_markup=main_menu)
        await message.answer(texts.RATE_PROMPT, reply_markup=rate_keyboard(session.id))

        try:
            await bot.send_message(partner_tid, texts.CHAT_ENDED_BY_PARTNER, reply_markup=main_menu)
            await bot.send_message(partner_tid, texts.RATE_PROMPT, reply_markup=rate_keyboard(session.id))
        except Exception as e:
            logger.warning(f'Failed to notify partner {partner_tid}: {e}')
    else:
        await message.answer(texts.NOT_IN_CHAT, reply_markup=main_menu)


# ── Next partner ─────────────────────────────────────────────────────────

@router.message(F.text == '⏭ Дальше')
@router.message(F.text == '⏭ Следующий')
async def next_partner(message: Message, bot: Bot):
    """End current chat, prompt rating, and search for a new partner."""
    telegram_id = message.from_user.id

    result = await matchmaking.end_session(telegram_id)
    if result:
        partner_tid, session = result

        await track(telegram_id, 'chat_finished', session_id=session.id)
        await track(partner_tid, 'partner_left', session_id=session.id)

        try:
            await bot.send_message(partner_tid, texts.CHAT_ENDED_BY_PARTNER, reply_markup=main_menu)
            await bot.send_message(partner_tid, texts.RATE_PROMPT, reply_markup=rate_keyboard(session.id))
        except Exception as e:
            logger.warning(f'Failed to notify partner {partner_tid}: {e}')

    await track(telegram_id, 'next_search_started')

    # Search for new partner
    match_result = await matchmaking.add_to_queue(telegram_id)

    if match_result is None:
        await message.answer(texts.SEARCHING_NEXT, reply_markup=searching_menu)
    else:
        partner_user, new_session = match_result
        new_partner_tid = await sync_to_async(lambda: partner_user.telegram_id)()

        await track(telegram_id, 'match_found', session_id=new_session.id)
        await track(new_partner_tid, 'match_found', session_id=new_session.id)

        await message.answer(texts.PARTNER_FOUND, reply_markup=chat_menu)
        await bot.send_message(new_partner_tid, texts.PARTNER_FOUND_SHORT, reply_markup=chat_menu)


# ── Text relay ───────────────────────────────────────────────────────────

@router.message(F.text)
async def relay_text(message: Message, bot: Bot):
    telegram_id = message.from_user.id
    if message.text in ('🔍 Найти собеседника', '❌ Отменить поиск',
                         '🚨 Жалоба', '🚨 Пожаловаться',
                         '👤 Профиль', '⚙️ Настройки', '⚙️ Настройки поиска',
                         'ℹ️ Как это работает'):
        return

    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result

    await _save_message(session.id, telegram_id, 'text', text=message.text)
    await track(telegram_id, 'message_sent', type='text')

    try:
        await bot.send_message(partner_tid, message.text)
    except Exception as e:
        logger.error(f'Relay text failed: {e}')
        await message.answer(texts.RELAY_FAILED)


# ── Photo relay ──────────────────────────────────────────────────────────

@router.message(F.photo)
async def relay_photo(message: Message, bot: Bot):
    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result
    telegram_id = message.from_user.id
    file_id = message.photo[-1].file_id

    try:
        file_path = await download_and_save(bot, file_id, 'photo')
    except Exception:
        file_path = None

    await _save_message(session.id, telegram_id, 'photo', text=message.caption,
                        file_path=file_path, telegram_file_id=file_id)
    await track(telegram_id, 'message_sent', type='photo')
    try:
        await bot.send_photo(partner_tid, photo=file_id, caption=message.caption)
    except Exception as e:
        logger.error(f'Relay photo failed: {e}')


# ── Video relay ──────────────────────────────────────────────────────────

@router.message(F.video)
async def relay_video(message: Message, bot: Bot):
    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result
    telegram_id = message.from_user.id
    file_id = message.video.file_id

    try:
        file_path = await download_and_save(bot, file_id, 'video')
    except Exception:
        file_path = None

    await _save_message(session.id, telegram_id, 'video', text=message.caption,
                        file_path=file_path, telegram_file_id=file_id)
    await track(telegram_id, 'message_sent', type='video')
    try:
        await bot.send_video(partner_tid, video=file_id, caption=message.caption)
    except Exception as e:
        logger.error(f'Relay video failed: {e}')


# ── Voice relay ──────────────────────────────────────────────────────────

@router.message(F.voice)
async def relay_voice(message: Message, bot: Bot):
    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result
    telegram_id = message.from_user.id
    file_id = message.voice.file_id

    try:
        file_path = await download_and_save(bot, file_id, 'voice')
    except Exception:
        file_path = None

    await _save_message(session.id, telegram_id, 'voice',
                        file_path=file_path, telegram_file_id=file_id)
    await track(telegram_id, 'message_sent', type='voice')
    try:
        await bot.send_voice(partner_tid, voice=file_id)
    except Exception as e:
        logger.error(f'Relay voice failed: {e}')


# ── Document relay ───────────────────────────────────────────────────────

@router.message(F.document)
async def relay_document(message: Message, bot: Bot):
    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result
    telegram_id = message.from_user.id
    file_id = message.document.file_id

    try:
        file_path = await download_and_save(bot, file_id, 'document', message.document.file_name)
    except Exception:
        file_path = None

    await _save_message(session.id, telegram_id, 'document', text=message.caption,
                        file_path=file_path, telegram_file_id=file_id)
    await track(telegram_id, 'message_sent', type='document')
    try:
        await bot.send_document(partner_tid, document=file_id, caption=message.caption)
    except Exception as e:
        logger.error(f'Relay document failed: {e}')


# ── Sticker relay ────────────────────────────────────────────────────────

@router.message(F.sticker)
async def relay_sticker(message: Message, bot: Bot):
    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result
    telegram_id = message.from_user.id
    file_id = message.sticker.file_id

    await _save_message(session.id, telegram_id, 'sticker', telegram_file_id=file_id)
    await track(telegram_id, 'message_sent', type='sticker')
    try:
        await bot.send_sticker(partner_tid, sticker=file_id)
    except Exception as e:
        logger.error(f'Relay sticker failed: {e}')


# ── Video note relay ─────────────────────────────────────────────────────

@router.message(F.video_note)
async def relay_video_note(message: Message, bot: Bot):
    result = await _check_session(message)
    if not result:
        return
    session, partner_tid = result
    telegram_id = message.from_user.id
    file_id = message.video_note.file_id

    try:
        file_path = await download_and_save(bot, file_id, 'video_note')
    except Exception:
        file_path = None

    await _save_message(session.id, telegram_id, 'video_note',
                        file_path=file_path, telegram_file_id=file_id)
    await track(telegram_id, 'message_sent', type='video_note')
    try:
        await bot.send_video_note(partner_tid, video_note=file_id)
    except Exception as e:
        logger.error(f'Relay video_note failed: {e}')
