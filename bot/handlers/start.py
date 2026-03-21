"""
/start handler, gender selection, profile, settings.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, Rating
from apps.users.models import RequiredChannel, RequiredBot, ChannelSubscriptionEvent
from bot.services.user_sync import sync_user
from bot.keyboards import main_menu, gender_select, rate_keyboard, subscribe_keyboard, bots_keyboard
from bot import texts
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

router = Router()
logger = logging.getLogger(__name__)

GENDER_LABELS = {
    'male': '👦 Парень',
    'female': '👧 Девушка',
    None: '❓ Не указан',
}


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Handle /start command, including deep-link referrals (start=ref_USERID)."""
    tg_user = message.from_user

    # Parse referral deep link: /start ref_12345
    referrer_id: int | None = None
    args = message.text.split() if message.text else []
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            referrer_id = int(args[1][4:])
        except ValueError:
            pass

    user, created = await sync_user(tg_user, bot, referrer_id=referrer_id)

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

    # Notify referrer if this is a new user
    if created and referrer_id and referrer_id != tg_user.id:
        try:
            ref_count = await sync_to_async(
                lambda: user.referred_by.referrals.count() if user.referred_by else 0
            )()
            new_name = tg_user.first_name or f'id{tg_user.id}'
            await bot.send_message(
                chat_id=referrer_id,
                text=texts.REFERRAL_WELCOME.format(name=new_name, count=ref_count),
            )
        except Exception as e:
            logger.warning(f'Could not notify referrer {referrer_id}: {e}')


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
    name = callback.from_user.first_name or 'Анон'
    await callback.message.edit_text(
        texts.GENDER_SET.format(emoji=emoji),
    )
    await callback.message.answer(
        texts.WELCOME_BACK.format(name=name),
        reply_markup=main_menu,
    )
    await callback.answer()


# (search_gender_select removed — matching is now fully random)


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
        ]
    )

    await message.answer(
        texts.SETTINGS.format(
            gender_label=GENDER_LABELS.get(user.gender),
        ),
        reply_markup=settings_kb,
    )


@router.callback_query(F.data == 'change_gender')
async def on_change_gender(callback: CallbackQuery):
    """Re-select gender."""
    await callback.message.edit_text(texts.GENDER_ASK, reply_markup=gender_select)
    await callback.answer()

# (change_search removed — search is now fully random)


# ── Referral ────────────────────────────────────────────────────

@router.message(Command('referral'))
@router.message(F.text == '🔗 Реферальная ссылка')
async def cmd_referral(message: Message, bot: Bot):
    """Show user's referral link and invited count."""
    telegram_id = message.from_user.id

    try:
        user = await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await message.answer(texts.NEED_REGISTRATION)
        return

    bot_info = await bot.get_me()
    ref_link = f'https://t.me/{bot_info.username}?start=ref_{telegram_id}'
    count = await sync_to_async(user.referrals.count)()

    await message.answer(
        texts.REFERRAL_INFO.format(ref_link=ref_link, count=count),
        reply_markup=main_menu,
    )


# ── Subscription check ───────────────────────────────────────────────────

@router.callback_query(F.data == 'check_subscription')
async def on_check_subscription(callback: CallbackQuery, bot: Bot):
    """Re-check all active channels; let user in or prompt to subscribe."""
    user_id = callback.from_user.id

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
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        except Exception:
            pass

    if not_subscribed:
        # Still not subscribed to all — show updated keyboard
        await callback.answer(texts.SUBSCRIPTION_NOT_YET, show_alert=True)
        kb = subscribe_keyboard(not_subscribed)
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except Exception:
            pass
        return

    # All channels subscribed — log subscription events for each channel
    try:
        tg_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user_id)
        for channel in channels:
            await sync_to_async(ChannelSubscriptionEvent.objects.get_or_create)(
                user=tg_user,
                channel_username=channel.channel_username,
                defaults={'channel_title': channel.title},
            )
    except Exception:
        pass

    # Grant access
    await callback.message.edit_text(texts.SUBSCRIPTION_VERIFIED)
    await callback.answer('✅')


# ── Required bots confirmation ────────────────────────────────────────────

@router.callback_query(F.data == 'check_bots')
async def on_check_bots(callback: CallbackQuery):
    """User confirms they have launched all required bots."""
    # Check if there are still active required bots
    required_bots = await sync_to_async(list)(
        RequiredBot.objects.filter(is_active=True)
    )

    if not required_bots:
        # No active bots required any more — just close the prompt
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer('✅')
        return

    # Trust the user — show confirmation and let the middleware pass them next time
    await callback.message.edit_text(texts.BOTS_CONFIRMED)
    await callback.answer('🤖✅')
