"""
/start handler, profile, rating, subscription/bots check, how-it-works.
Gender selection has been removed from the onboarding and settings flow.
"""
import logging

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, Rating
from apps.users.models import RequiredChannel, RequiredBot, ChannelSubscriptionEvent, BotClickEvent
from bot.services.user_sync import sync_user
from bot.keyboards import (
    main_menu, rate_keyboard, subscribe_keyboard,
    bots_keyboard, search_now_keyboard, search_again_keyboard,
    searching_menu, chat_menu, profile_actions_keyboard,
)
from bot import texts
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apps.analytics.services import track
from bot.admin.services import touch_activity

router = Router()
logger = logging.getLogger(__name__)


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
    await touch_activity(telegram_id)

    if user.is_blocked:
        await message.answer(texts.BLOCKED)
        return

    name = tg_user.first_name or 'Анон'

    if created:
        await message.answer(
            texts.WELCOME.format(name=name),
            reply_markup=main_menu,
        )
    else:
        await message.answer(
            texts.WELCOME_BACK.format(name=name),
            reply_markup=main_menu,
        )

    await track(telegram_id, 'main_menu_shown')


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
        await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start')
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

async def _build_profile_text(user, telegram_id):
    """Build the profile card text."""
    from apps.chat.models import ChatSession
    from django.db.models import Q
    from bot.services.ranks import get_rank, get_next_rank, rank_label

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

    from bot.services.matchmaking import matchmaking
    if matchmaking.is_in_chat(telegram_id):
        status_line = texts.PROFILE_STATUS_IN_CHAT
    elif matchmaking.is_in_queue(telegram_id):
        status_line = texts.PROFILE_STATUS_SEARCHING
    else:
        status_line = texts.PROFILE_STATUS_IDLE

    # Rank info
    r_label = rank_label(chats_count)
    nxt = get_next_rank(chats_count)
    if nxt:
        left, nxt_emoji, nxt_title = nxt
        next_rank_line = f'⏭ До {nxt_emoji} {nxt_title}: <b>{left}</b> чатов'
    else:
        next_rank_line = '🏆 Максимальный ранг!'

    return texts.PROFILE.format(
        display_name=user.display_name,
        rank_line=r_label,
        next_rank_line=next_rank_line,
        chats_count=chats_count,
        likes=likes,
        dislikes=dislikes,
        status_line=status_line,
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
    await touch_activity(telegram_id)

    profile_text = await _build_profile_text(user, telegram_id)
    await message.answer(profile_text, reply_markup=profile_actions_keyboard)


# ═══════════════════════════════════════════════════════════════════════
#  Settings (minimal — no gender)
# ═══════════════════════════════════════════════════════════════════════

@router.message(F.text == '⚙️ Настройки')
@router.message(F.text == '⚙️ Настройки поиска')
async def cmd_settings(message: Message):
    await track(message.from_user.id, 'settings_opened')
    await message.answer(texts.SETTINGS, reply_markup=main_menu)


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

@router.callback_query(F.data.in_({'check_activation', 'check_subscription'}))
async def on_check_activation(callback: CallbackQuery, bot: Bot):
    """Unified check: channels (fail-open) + bots (DB confirm)."""
    user_id = callback.from_user.id
    await track(user_id, 'activation_check_clicked')

    # ── Check channels ──
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
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            # Fail-open: bot isn't admin in channel, skip check
            logger.warning(
                f'Channel check failed (skipping): {channel.channel_username} '
                f'user={user_id} error={type(e).__name__}: {e}'
            )
        except Exception as e:
            logger.error(
                f'Unexpected channel check error (skipping): {channel.channel_username} '
                f'user={user_id} error={type(e).__name__}: {e}'
            )

    # ── Check bots ──
    required_bots = await sync_to_async(list)(
        RequiredBot.objects.filter(is_active=True)
    )
    missing_bots = []
    if required_bots:
        try:
            tg_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user_id)
        except TelegramUser.DoesNotExist:
            await callback.answer('Нажми /start', show_alert=True)
            return

        confirmed = set(await sync_to_async(list)(
            BotClickEvent.objects.filter(
                user=tg_user,
                self_confirmed_at__isnull=False,
            ).values_list('bot_username', flat=True)
        ))
        required_usernames = {b.bot_username.lstrip('@') for b in required_bots}
        missing_bots = list(required_usernames - confirmed)

    # ── Result ──
    if not_subscribed or missing_bots:
        problems = []
        if not_subscribed:
            problems.append('подписка на каналы')
        if missing_bots:
            problems.append('боты не отмечены')
        await callback.answer(
            f'❌ Не всё выполнено: {", ".join(problems)}',
            show_alert=True,
        )
        # Refresh keyboard with current state
        from bot.keyboards import activation_keyboard
        kb = activation_keyboard(
            channels=not_subscribed if not_subscribed else None,
            bots=required_bots if missing_bots else None,
            confirmed_bots=confirmed if required_bots else set(),
        )
        try:
            await callback.message.edit_text(
                texts.ACTIVATION_REQUIRED,
                reply_markup=kb,
            )
        except Exception:
            pass
        return

    # All checks passed — save confirmation
    if required_bots:
        try:
            from django.utils import timezone
            tg_user.bots_confirmed_at = timezone.now()
            await sync_to_async(tg_user.save)(update_fields=['bots_confirmed_at'])
        except Exception as e:
            logger.warning(f'Could not save bots_confirmed_at: {e}')

    await track(user_id, 'activation_passed')

    await callback.message.edit_text(texts.BOTS_CONFIRMED)
    await callback.message.answer(
        '🚀 Всё готово! Найди первого собеседника:',
        reply_markup=search_now_keyboard,
    )
    await callback.answer('🎉')


# ═══════════════════════════════════════════════════════════════════════
#  Required bots — per-bot confirm
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith('bot_done_'))
async def on_bot_done(callback: CallbackQuery):
    """Individual bot mark — saves click to DB (persistent)."""
    user_id = callback.from_user.id
    bot_username = callback.data.replace('bot_done_', '')

    # Get or create DB user
    try:
        tg_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start', show_alert=True)
        return

    # Save click to DB (persistent, survives restart)
    from django.utils import timezone
    click, created = await sync_to_async(
        BotClickEvent.objects.get_or_create
    )(
        user=tg_user,
        bot_username=bot_username,
        defaults={'self_confirmed_at': timezone.now()},
    )
    if not click.self_confirmed_at:
        click.self_confirmed_at = timezone.now()
        await sync_to_async(click.save)(update_fields=['self_confirmed_at'])

    await track(user_id, 'required_bot_confirmed', bot_username=bot_username)

    # Reload confirmed set from DB
    confirmed = set(await sync_to_async(list)(
        BotClickEvent.objects.filter(
            user=tg_user,
            self_confirmed_at__isnull=False,
        ).values_list('bot_username', flat=True)
    ))

    bots = await sync_to_async(list)(
        RequiredBot.objects.filter(is_active=True)
    )

    # Determine progress text
    has_channels = await sync_to_async(RequiredChannel.objects.filter(is_active=True).exists)()
    current_step = 2 if has_channels else 1
    progress = f'▪▪▫ Шаг {current_step} из 3'

    try:
        await callback.message.edit_text(
            texts.BOTS_REQUIRED.format(progress=progress),
            reply_markup=bots_keyboard(bots, confirmed=confirmed),
        )
    except TelegramBadRequest:
        pass

    await callback.answer(f'✅ {bot_username} отмечен')


@router.callback_query(F.data == 'check_bots')
async def on_check_bots(callback: CallbackQuery):
    """Final check — all bots must be individually marked in DB."""
    user_id = callback.from_user.id

    try:
        tg_user = await sync_to_async(TelegramUser.objects.get)(telegram_id=user_id)
    except TelegramUser.DoesNotExist:
        await callback.answer('Нажми /start', show_alert=True)
        return

    bots = await sync_to_async(list)(
        RequiredBot.objects.filter(is_active=True)
    )

    required_usernames = {b.bot_username.lstrip('@') for b in bots}

    # Check DB for confirmed clicks
    confirmed = set(await sync_to_async(list)(
        BotClickEvent.objects.filter(
            user=tg_user,
            self_confirmed_at__isnull=False,
        ).values_list('bot_username', flat=True)
    ))

    missing = required_usernames - confirmed

    if missing:
        await callback.answer(texts.BOTS_NOT_ALL_CLICKED, show_alert=True)
        return

    # Save bots_confirmed_at timestamp
    try:
        from django.utils import timezone
        tg_user.bots_confirmed_at = timezone.now()
        await sync_to_async(tg_user.save)(update_fields=['bots_confirmed_at'])
    except Exception as e:
        logger.warning(f'Could not save bots_confirmed_at: {e}')

    await track(user_id, 'required_bots_passed')

    await callback.message.edit_text(texts.BOTS_CONFIRMED)
    await callback.message.answer(
        '🚀 Всё готово! Найди первого собеседника:',
        reply_markup=search_now_keyboard,
    )
    await callback.answer('🎉')
