"""
/start handler, gender selection, profile, settings, rating,
subscription/bots check, how-it-works.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, Rating
from apps.users.models import RequiredChannel, RequiredBot, ChannelSubscriptionEvent
from bot.services.user_sync import sync_user
from bot.keyboards import (
    main_menu, gender_select, rate_keyboard, subscribe_keyboard,
    bots_keyboard, search_now_keyboard, search_again_keyboard,
    searching_menu, chat_menu,
)
from bot import texts
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apps.analytics.services import track

router = Router()
logger = logging.getLogger(__name__)

GENDER_LABELS = {
    'male': '👦 Парень',
    'female': '👧 Девушка',
    None: '❓ Не указан',
}

# ── In-memory per-bot confirmations ──────────────────────────────────────
_user_bot_confirmations: dict[int, set[str]] = {}


# ═══════════════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Handle /start command, including deep-link referral (start=ref_CODE)."""
    tg_user = message.from_user
    telegram_id = tg_user.id

    # Parse campaign deep link
    campaign_code: str | None = None
    args = message.text.split() if message.text else []
    if len(args) > 1 and args[1].startswith('ref_'):
        campaign_code = args[1][4:]

    user, created = await sync_user(tg_user, bot, campaign_code=campaign_code)

    await track(telegram_id, 'start_opened', campaign_code=campaign_code or '', is_new=created)

    if user.is_blocked:
        await message.answer(texts.BLOCKED)
        return

    name = tg_user.first_name or 'Анон'

    if not user.gender:
        await message.answer(texts.WELCOME.format(name=name))
        await message.answer(texts.GENDER_ASK, reply_markup=gender_select)
        await track(telegram_id, 'gender_selection_shown')
    else:
        await message.answer(
            texts.WELCOME_BACK.format(name=name),
            reply_markup=main_menu,
        )
        await track(telegram_id, 'main_menu_shown')


# ═══════════════════════════════════════════════════════════════════════
#  Gender selection
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith('gender_'))
async def on_gender_select(callback: CallbackQuery):
    gender = callback.data.replace('gender_', '')
    telegram_id = callback.from_user.id

    user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    user.gender = gender
    await sync_to_async(user.save)(update_fields=['gender'])

    emoji = '👦' if gender == 'male' else '👧'
    name = callback.from_user.first_name or 'Анон'

    await track(telegram_id, 'gender_selected', gender=gender)

    await callback.message.edit_text(
        texts.GENDER_SET.format(emoji=emoji),
    )
    await callback.message.answer(
        texts.WELCOME_BACK.format(name=name),
        reply_markup=main_menu,
    )
    await track(telegram_id, 'main_menu_shown')
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  Rating callbacks
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith('rate_'))
async def on_rate(callback: CallbackQuery):
    parts = callback.data.split('_')
    action = parts[1]
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

    user1_tid = await sync_to_async(lambda: session.user1.telegram_id)()
    user2_tid = await sync_to_async(lambda: session.user2.telegram_id)()

    if user1_tid == telegram_id:
        to_user = await sync_to_async(lambda: session.user2)()
    elif user2_tid == telegram_id:
        to_user = await sync_to_async(lambda: session.user1)()
    else:
        await callback.answer('Ошибка.')
        return

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

    await track(telegram_id, 'partner_rated', is_like=is_like, session_id=session_id)

    text = texts.RATED_LIKE if is_like else texts.RATED_DISLIKE
    await callback.message.edit_text(text)
    await callback.message.answer('🔍 Готов к новому чату?', reply_markup=search_again_keyboard)
    await callback.answer('👍' if is_like else '👎')


# ═══════════════════════════════════════════════════════════════════════
#  Inline search trigger (from inline buttons)
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'inline_search')
async def on_inline_search(callback: CallbackQuery, bot: Bot):
    """Start search from an inline button (after activation or rating)."""
    telegram_id = callback.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
        return

    if not user.gender:
        await callback.answer('Сначала укажи пол!', show_alert=True)
        return

    from bot.services.matchmaking import matchmaking

    if matchmaking.is_in_chat(telegram_id):
        await callback.answer('Ты уже в чате!', show_alert=True)
        return

    if matchmaking.is_in_queue(telegram_id):
        await callback.answer('Поиск уже идёт!', show_alert=True)
        return

    await track(telegram_id, 'search_started')

    result = await matchmaking.add_to_queue(telegram_id)

    if result is None:
        await callback.message.answer(texts.SEARCHING, reply_markup=searching_menu)
    else:
        partner_user, session = result
        partner_tid = await sync_to_async(lambda: partner_user.telegram_id)()

        await track(telegram_id, 'match_found', session_id=session.id)
        await track(telegram_id, 'chat_started', session_id=session.id)
        await track(partner_tid, 'match_found', session_id=session.id)
        await track(partner_tid, 'chat_started', session_id=session.id)

        await callback.message.answer(texts.PARTNER_FOUND, reply_markup=chat_menu)
        await bot.send_message(partner_tid, texts.PARTNER_FOUND_SHORT, reply_markup=chat_menu)

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════

SEARCH_LABELS = {
    'male': '👦 Парней',
    'female': '👧 Девушек',
    None: '🔀 Всех',
}


async def _build_profile_text(user, telegram_id):
    """Build the rich profile card text."""
    from apps.chat.models import ChatSession
    from django.db.models import Q

    likes = await sync_to_async(
        user.ratings_received.filter(is_like=True).count
    )()
    dislikes = await sync_to_async(
        user.ratings_received.filter(is_like=False).count
    )()
    chats_count = await sync_to_async(
        ChatSession.objects.filter(
            Q(user1=user) | Q(user2=user),
            status='closed',
        ).count
    )()

    joined = user.created_at.strftime('%d.%m.%Y')

    from bot.services.matchmaking import matchmaking
    if matchmaking.is_in_chat(telegram_id):
        status_line = texts.PROFILE_STATUS_IN_CHAT
    elif matchmaking.is_in_queue(telegram_id):
        status_line = texts.PROFILE_STATUS_SEARCHING
    else:
        status_line = texts.PROFILE_STATUS_IDLE

    return texts.PROFILE.format(
        display_name=user.display_name,
        telegram_id=user.telegram_id,
        gender_label=GENDER_LABELS.get(user.gender),
        search_label=SEARCH_LABELS.get(user.search_gender),
        chats_count=chats_count,
        likes=likes,
        dislikes=dislikes,
        joined=joined,
        status_line=status_line,
    )


async def _build_settings_text(user):
    """Build the settings screen text."""
    return texts.SETTINGS.format(
        gender_label=GENDER_LABELS.get(user.gender),
        search_label=SEARCH_LABELS.get(user.search_gender),
    )


# ═══════════════════════════════════════════════════════════════════════
#  Profile
# ═══════════════════════════════════════════════════════════════════════

@router.message(Command('profile'))
@router.message(F.text == '👤 Профиль')
async def cmd_profile(message: Message):
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    await track(telegram_id, 'profile_opened')

    from bot.keyboards import profile_actions_keyboard
    profile_text = await _build_profile_text(user, telegram_id)
    await message.answer(profile_text, reply_markup=profile_actions_keyboard)


@router.callback_query(F.data == 'back_to_profile')
async def on_back_to_profile(callback: CallbackQuery):
    """Navigate back to profile from settings."""
    telegram_id = callback.from_user.id
    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
        return

    from bot.keyboards import profile_actions_keyboard
    profile_text = await _build_profile_text(user, telegram_id)
    await callback.message.edit_text(profile_text, reply_markup=profile_actions_keyboard)
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  Settings
# ═══════════════════════════════════════════════════════════════════════

@router.message(F.text == '⚙️ Настройки')
@router.message(F.text == '⚙️ Настройки поиска')
async def cmd_settings(message: Message):
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    await track(telegram_id, 'settings_opened')

    from bot.keyboards import settings_keyboard
    settings_text = await _build_settings_text(user)
    await message.answer(settings_text, reply_markup=settings_keyboard)


@router.callback_query(F.data == 'open_settings')
async def on_open_settings(callback: CallbackQuery):
    """Navigate to settings from profile."""
    telegram_id = callback.from_user.id
    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
        return

    await track(telegram_id, 'settings_opened')

    from bot.keyboards import settings_keyboard
    settings_text = await _build_settings_text(user)
    await callback.message.edit_text(settings_text, reply_markup=settings_keyboard)
    await callback.answer()


@router.callback_query(F.data == 'back_to_settings')
async def on_back_to_settings(callback: CallbackQuery):
    """Navigate back to settings from sub-screen."""
    telegram_id = callback.from_user.id
    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
        return

    from bot.keyboards import settings_keyboard
    settings_text = await _build_settings_text(user)
    await callback.message.edit_text(settings_text, reply_markup=settings_keyboard)
    await callback.answer()


# ── Settings: Change gender ──────────────────────────────────────────────

@router.callback_query(F.data == 'settings_change_gender')
async def on_settings_change_gender(callback: CallbackQuery):
    """Show gender selection within settings flow."""
    telegram_id = callback.from_user.id
    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
        return

    await track(telegram_id, 'gender_change_started')

    from bot.keyboards import settings_gender_select
    await callback.message.edit_text(
        texts.SETTINGS_GENDER_ASK.format(current=GENDER_LABELS.get(user.gender)),
        reply_markup=settings_gender_select,
    )
    await callback.answer()


@router.callback_query(F.data.startswith('set_gender_'))
async def on_set_gender(callback: CallbackQuery):
    """Save gender change from settings."""
    gender = callback.data.replace('set_gender_', '')
    telegram_id = callback.from_user.id

    user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    user.gender = gender
    await sync_to_async(user.save)(update_fields=['gender'])

    emoji = '👦' if gender == 'male' else '👧'
    await track(telegram_id, 'gender_changed', gender=gender)

    # Show confirmation then return to settings
    from bot.keyboards import settings_keyboard
    settings_text = await _build_settings_text(user)
    await callback.message.edit_text(
        texts.SETTINGS_GENDER_SAVED.format(emoji=emoji) + '\n\n' + settings_text,
        reply_markup=settings_keyboard,
    )
    await callback.answer('✅ Сохранено')


# ── Settings: Change search preference ───────────────────────────────────

@router.callback_query(F.data == 'settings_change_search')
async def on_settings_change_search(callback: CallbackQuery):
    """Show search preference selection within settings flow."""
    telegram_id = callback.from_user.id
    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
        return

    await track(telegram_id, 'search_pref_change_started')

    from bot.keyboards import settings_search_select
    await callback.message.edit_text(
        texts.SETTINGS_SEARCH_ASK.format(current=SEARCH_LABELS.get(user.search_gender)),
        reply_markup=settings_search_select,
    )
    await callback.answer()


@router.callback_query(F.data.startswith('set_search_'))
async def on_set_search(callback: CallbackQuery):
    """Save search preference from settings."""
    pref = callback.data.replace('set_search_', '')
    telegram_id = callback.from_user.id

    user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    user.search_gender = None if pref == 'any' else pref
    await sync_to_async(user.save)(update_fields=['search_gender'])

    label = SEARCH_LABELS.get(user.search_gender)
    await track(telegram_id, 'search_pref_changed', search_gender=pref)

    from bot.keyboards import settings_keyboard
    settings_text = await _build_settings_text(user)
    await callback.message.edit_text(
        texts.SETTINGS_SEARCH_SAVED.format(label=label) + '\n\n' + settings_text,
        reply_markup=settings_keyboard,
    )
    await callback.answer('✅ Сохранено')


@router.callback_query(F.data == 'change_gender')
async def on_change_gender(callback: CallbackQuery):
    """Legacy change gender callback — redirect to settings flow."""
    await callback.message.edit_text(texts.GENDER_ASK, reply_markup=gender_select)
    await callback.answer()



# ═══════════════════════════════════════════════════════════════════════
#  How it works
# ═══════════════════════════════════════════════════════════════════════

@router.message(F.text == 'ℹ️ Как это работает')
@router.message(Command('help'))
async def cmd_how_it_works(message: Message):
    await track(message.from_user.id, 'how_it_works_opened')
    await message.answer(texts.HOW_IT_WORKS, reply_markup=main_menu)


# ═══════════════════════════════════════════════════════════════════════
#  Subscription check
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'check_subscription')
async def on_check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id

    await track(user_id, 'subscription_check_clicked')

    channels = await sync_to_async(list)(
        RequiredChannel.objects.filter(is_active=True)
    )

    not_subscribed = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel.channel_username,
                user_id=user_id,
            )
            if member.status not in ('member', 'administrator', 'creator'):
                not_subscribed.append(channel)
            else:
                await sync_to_async(
                    ChannelSubscriptionEvent.objects.get_or_create
                )(
                    user_id=(await sync_to_async(
                        TelegramUser.objects.get
                    )(telegram_id=user_id)).id,
                    channel_username=channel.channel_username,
                    defaults={'channel_title': channel.title},
                )
        except (TelegramBadRequest, TelegramForbiddenError):
            not_subscribed.append(channel)
        except Exception as e:
            logger.warning(f'Subscription check error for {channel.channel_username}: {e}')
            not_subscribed.append(channel)

    if not_subscribed:
        await callback.answer(texts.SUBSCRIPTION_NOT_YET, show_alert=True)
    else:
        await track(user_id, 'required_channels_passed')

        await callback.message.edit_text(texts.SUBSCRIPTION_VERIFIED)
        await callback.answer('✅')


# ═══════════════════════════════════════════════════════════════════════
#  Required bots — per-bot confirm
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith('bot_done_'))
async def on_bot_done(callback: CallbackQuery):
    """Individual bot confirmation."""
    user_id = callback.from_user.id
    bot_username = callback.data.replace('bot_done_', '')

    confirmed = _user_bot_confirmations.setdefault(user_id, set())
    confirmed.add(bot_username)

    await track(user_id, 'required_bot_confirmed', bot_username=bot_username)

    bots = await sync_to_async(list)(
        RequiredBot.objects.filter(is_active=True)
    )

    # Determine progress text
    total_steps = 3
    has_channels = await sync_to_async(RequiredChannel.objects.filter(is_active=True).exists)()
    current_step = 2 if has_channels else 1
    progress = f'▪▪▫ Шаг {current_step} из {total_steps}'

    try:
        await callback.message.edit_text(
            texts.BOTS_REQUIRED.format(progress=progress),
            reply_markup=bots_keyboard(bots, confirmed=confirmed),
        )
    except TelegramBadRequest:
        pass

    await callback.answer(f'✅ {bot_username} подтверждён')


@router.callback_query(F.data == 'check_bots')
async def on_check_bots(callback: CallbackQuery):
    """Final check — all bots must be individually confirmed."""
    user_id = callback.from_user.id
    confirmed = _user_bot_confirmations.get(user_id, set())

    bots = await sync_to_async(list)(
        RequiredBot.objects.filter(is_active=True)
    )

    required_usernames = {b.bot_username.lstrip('@') for b in bots}
    missing = required_usernames - confirmed

    if missing:
        missing_list = ', '.join(f'@{u}' for u in missing)
        await callback.answer(
            f'❌ Не подтверждено: {missing_list}\nОткрой и запусти каждого бота!',
            show_alert=True,
        )
        return

    # Save timestamp
    try:
        from django.utils import timezone
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user_id)
        user.bots_confirmed_at = timezone.now()
        await sync_to_async(user.save)(update_fields=['bots_confirmed_at'])
    except Exception as e:
        logger.warning(f'Could not save bots_confirmed_at: {e}')

    _user_bot_confirmations.pop(user_id, None)

    await track(user_id, 'required_bots_passed')

    await callback.message.edit_text(texts.BOTS_CONFIRMED)
    await callback.message.answer(
        '🚀 Всё готово! Найди первого собеседника:',
        reply_markup=search_now_keyboard,
    )
    await callback.answer('🎉')
