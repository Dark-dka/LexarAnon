"""
/start handler, gender selection, profile, settings.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, Rating
from bot.services.user_sync import sync_user
from bot.keyboards import main_menu, gender_select, search_gender_select, rate_keyboard
from bot import texts
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
logger = logging.getLogger(__name__)

GENDER_LABELS = {
    'male': '👦 Парень',
    'female': '👧 Девушка',
    None: '❓ Не указан',
}
SEARCH_LABELS = {
    'male': '👦 Парней',
    'female': '👧 Девушек',
    None: '🔀 Всех',
}


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Handle /start command."""
    tg_user = message.from_user
    exists = await sync_to_async(
        TelegramUser.objects.filter(telegram_id=tg_user.id).exists
    )()
    user = await sync_user(tg_user, bot)

    if user.is_blocked:
        await message.answer(texts.BLOCKED)
        return

    name = tg_user.first_name or 'Анон'

    if not user.gender:
        # New user or gender not set — ask gender
        await message.answer(texts.WELCOME.format(name=name))
        await message.answer(texts.GENDER_ASK, reply_markup=gender_select)
    else:
        await message.answer(
            texts.WELCOME_BACK.format(name=name),
            reply_markup=main_menu,
        )


# ── Gender selection callbacks ───────────────────────────────────────────

@router.callback_query(F.data.startswith('gender_'))
async def on_gender_select(callback: CallbackQuery):
    """Handle gender selection."""
    gender = callback.data.replace('gender_', '')  # 'male' or 'female'
    telegram_id = callback.from_user.id

    user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    user.gender = gender
    await sync_to_async(user.save)(update_fields=['gender'])

    emoji = '👦' if gender == 'male' else '👧'
    await callback.message.edit_text(
        texts.GENDER_SET.format(emoji=emoji),
        reply_markup=search_gender_select,
    )
    await callback.answer()


@router.callback_query(F.data.startswith('search_'))
async def on_search_gender_select(callback: CallbackQuery):
    """Handle search gender preference."""
    value = callback.data.replace('search_', '')  # 'male', 'female', 'any'
    telegram_id = callback.from_user.id

    user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    user.search_gender = None if value == 'any' else value
    await sync_to_async(user.save)(update_fields=['search_gender'])

    await callback.message.edit_text(
        texts.SEARCH_GENDER_SET.format(
            your_gender=user.gender_emoji,
            your_label=GENDER_LABELS.get(user.gender),
            search_label=SEARCH_LABELS.get(user.search_gender),
        ),
    )

    # Send main menu
    await callback.message.answer('👇', reply_markup=main_menu)
    await callback.answer()


# ── Rating callbacks ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith('rate_'))
async def on_rate(callback: CallbackQuery):
    """Handle like / dislike rating."""
    parts = callback.data.split('_')
    # rate_like_123 or rate_dislike_123
    action = parts[1]  # 'like' or 'dislike'
    session_id = int(parts[2])
    telegram_id = callback.from_user.id

    from apps.chat.models import ChatSession
    try:
        session = await sync_to_async(
            ChatSession.objects.select_related('user1', 'user2').get
        )(id=session_id)
    except ChatSession.DoesNotExist:
        await callback.answer('Сессия не найдена.')
        return

    from_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)

    # Determine who to rate
    user1_tid = await sync_to_async(lambda: session.user1.telegram_id)()
    user2_tid = await sync_to_async(lambda: session.user2.telegram_id)()

    if user1_tid == telegram_id:
        to_user = await sync_to_async(lambda: session.user2)()
    elif user2_tid == telegram_id:
        to_user = await sync_to_async(lambda: session.user1)()
    else:
        await callback.answer('Ошибка.')
        return

    # Check if already rated
    already = await sync_to_async(
        Rating.objects.filter(
            from_user=from_user,
            to_user=to_user,
            chat_session=session,
        ).exists
    )()

    if already:
        await callback.answer(texts.ALREADY_RATED, show_alert=True)
        return

    is_like = action == 'like'
    await sync_to_async(Rating.objects.create)(
        from_user=from_user,
        to_user=to_user,
        is_like=is_like,
        chat_session=session,
    )

    text = texts.RATED_LIKE if is_like else texts.RATED_DISLIKE
    await callback.message.edit_text(text)
    await callback.answer('👍' if is_like else '👎')


# ── Profile ──────────────────────────────────────────────────────────────

@router.message(Command('profile'))
@router.message(F.text == '👤 Профиль')
async def cmd_profile(message: Message):
    """Show user profile: gender + likes/dislikes."""
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    likes = await sync_to_async(
        user.ratings_received.filter(is_like=True).count
    )()
    dislikes = await sync_to_async(
        user.ratings_received.filter(is_like=False).count
    )()

    await message.answer(
        texts.PROFILE.format(
            gender_label=GENDER_LABELS.get(user.gender),
            search_label=SEARCH_LABELS.get(user.search_gender),
            likes=likes,
            dislikes=dislikes,
        ),
        reply_markup=main_menu,
    )


# ── Settings ─────────────────────────────────────────────────────────────

@router.message(F.text == '⚙️ Настройки поиска')
async def cmd_settings(message: Message):
    """Show search settings with options to change."""
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    settings_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔄 Изменить пол', callback_data='change_gender')],
            [InlineKeyboardButton(text='🔍 Изменить поиск', callback_data='change_search')],
        ]
    )

    await message.answer(
        texts.SETTINGS.format(
            gender_label=GENDER_LABELS.get(user.gender),
            search_label=SEARCH_LABELS.get(user.search_gender),
        ),
        reply_markup=settings_kb,
    )


@router.callback_query(F.data == 'change_gender')
async def on_change_gender(callback: CallbackQuery):
    """Re-select gender."""
    await callback.message.edit_text(texts.GENDER_ASK, reply_markup=gender_select)
    await callback.answer()


@router.callback_query(F.data == 'change_search')
async def on_change_search(callback: CallbackQuery):
    """Re-select search preference."""
    await callback.message.edit_text(texts.SEARCH_GENDER_ASK, reply_markup=search_gender_select)
    await callback.answer()
