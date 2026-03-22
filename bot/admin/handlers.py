"""
Telegram Admin Panel — all handlers for /begu admin interface.
Protected by AdminFilter (telegram_id check).
"""
import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from asgiref.sync import sync_to_async

from bot.admin.filters import AdminFilter, is_admin
from bot.admin.states import AddChannelFSM, AddBotFSM
from bot.admin import keyboards as kb
from bot.admin import services

from apps.users.models import TelegramUser, RequiredChannel, RequiredBot
from bot.services.matchmaking import matchmaking

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 8


# ═══════════════════════════════════════════════════════════════════════
#  /begu — entry point
# ═══════════════════════════════════════════════════════════════════════

@router.message(Command('begu'), AdminFilter())
async def cmd_begu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        '🔐 <b>Admin Panel</b>\n\nВыбери раздел 👇',
        reply_markup=kb.admin_main_menu,
    )


@router.message(Command('begu'))
async def cmd_begu_denied(message: Message):
    """Non-admin tried /begu."""
    await message.answer('🚫')


# ═══════════════════════════════════════════════════════════════════════
#  Navigation
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:menu', AdminFilter())
async def on_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        '🔐 <b>Admin Panel</b>\n\nВыбери раздел 👇',
        reply_markup=kb.admin_main_menu,
    )
    await callback.answer()


@router.callback_query(F.data == 'adm:close', AdminFilter())
async def on_admin_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer('Закрыто')


# ═══════════════════════════════════════════════════════════════════════
#  📊 Stats
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:stats', AdminFilter())
async def on_stats(callback: CallbackQuery):
    s = await services.get_stats()

    q_size = matchmaking.queue_size

    text = (
        '📊 <b>Статистика</b>\n'
        '\n'
        f'👥 Всего: <b>{s["total"]}</b>\n'
        f'🆕 Новые: <b>{s["new_1d"]}</b> / {s["new_7d"]} / {s["new_30d"]}\n'
        f'   <i>(сегодня / 7д / 30д)</i>\n'
        '\n'
        f'🟢 Живые: <b>{s["alive_1d"]}</b> / {s["alive_7d"]} / {s["alive_30d"]}\n'
        f'💀 Мёртвые: <b>{s["dead_3d"]}</b> (3д+) / {s["dead_30d"]} (30д+)\n'
        f'🚫 Заблок: <b>{s["blocked"]}</b>\n'
        '\n'
        f'🔍 В поиске: <b>{q_size}</b>\n'
        f'💬 Активных чатов: <b>{s["active_chats"]}</b>\n'
        f'✅ Завершено: <b>{s["chats_today"]}</b> / {s["chats_7d"]}\n'
        f'   <i>(сегодня / 7д)</i>\n'
        '\n'
        f'🚨 Жалобы: <b>{s["reports_today"]}</b> / {s["reports_7d"]}\n'
        f'📈 Ср. чатов/юзер: <b>{s["avg_chats"]}</b>'
    )

    await callback.message.edit_text(text, reply_markup=kb.back_button())
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  👥 Users
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:users', AdminFilter())
async def on_users_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    total = await sync_to_async(TelegramUser.objects.count)()
    await callback.message.edit_text(
        f'👥 <b>Пользователи</b> — {total}\n\nВыбери сегмент 👇',
        reply_markup=kb.users_menu,
    )
    await callback.answer()


@router.callback_query(F.data.startswith('adm:users:search'), AdminFilter())
async def on_users_search_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state('admin_user_search')
    await callback.message.edit_text(
        '🔍 Введи Telegram ID или @username:',
        reply_markup=kb.back_button('adm:users'),
    )
    await callback.answer()


@router.message(
    F.text,
    AdminFilter(),
    StateFilter(
        'admin_user_search',
        AddChannelFSM.title, AddChannelFSM.username, AddChannelFSM.invite_link,
        AddBotFSM.title, AddBotFSM.username, AddBotFSM.invite_link,
    ),
)
async def on_admin_text_input(message: Message, state: FSMContext):
    """Handle text input for admin FSM states only."""
    current = await state.get_state()

    if current == 'admin_user_search':
        await _handle_user_search(message, state)
    elif current == AddChannelFSM.title:
        await _handle_channel_title(message, state)
    elif current == AddChannelFSM.username:
        await _handle_channel_username(message, state)
    elif current == AddChannelFSM.invite_link:
        await _handle_channel_link(message, state)
    elif current == AddBotFSM.title:
        await _handle_bot_title(message, state)
    elif current == AddBotFSM.username:
        await _handle_bot_username(message, state)
    elif current == AddBotFSM.invite_link:
        await _handle_bot_link(message, state)


async def _handle_user_search(message: Message, state: FSMContext):
    await state.clear()
    users = await services.search_user(message.text.strip())
    if not users:
        await message.answer('Не найдено.', reply_markup=kb.back_button('adm:users'))
        return
    lines = []
    for u in users:
        lines.append(f'• <code>{u.telegram_id}</code> — {u.display_name}')
    text = '🔍 <b>Результаты:</b>\n\n' + '\n'.join(lines)
    # Create inline buttons for each user
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = [[InlineKeyboardButton(
        text=f'{u.display_name}',
        callback_data=f'adm:user:card:{u.telegram_id}',
    )] for u in users]
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='adm:users')])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.regexp(r'^adm:users:(\w+):(\d+)$'), AdminFilter())
async def on_users_list(callback: CallbackQuery):
    """Show paginated user list by segment."""
    parts = callback.data.split(':')
    segment = parts[2]
    page = int(parts[3])

    SEGMENT_NAMES = {
        'recent': '🆕 Новые',
        'alive_1d': '🟢 Живые 24ч',
        'alive_7d': '🟡 Живые 7д',
        'dead_3d': '💀 Мёртвые 3д+',
        'dead_30d': '☠️ Мёртвые 30д+',
        'blocked': '🚫 Заблокированные',
    }

    users, total = await services.get_users_list(segment, page, PAGE_SIZE)
    name = SEGMENT_NAMES.get(segment, segment)

    lines = [f'{name} — <b>{total}</b>\n']
    for i, u in enumerate(users, start=page * PAGE_SIZE + 1):
        act = ''
        if u.last_activity_at:
            act = f' · {u.last_activity_at:%d.%m %H:%M}'
        lines.append(f'{i}. <code>{u.telegram_id}</code> {u.display_name}{act}')

    text = '\n'.join(lines) if lines else 'Пусто.'

    from aiogram.types import InlineKeyboardButton
    # Build user selection + pagination
    rows = [[InlineKeyboardButton(
        text=f'{u.display_name}',
        callback_data=f'adm:user:card:{u.telegram_id}',
    )] for u in users]

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text='◀️', callback_data=f'adm:users:{segment}:{page - 1}'))
    if (page + 1) * PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text='▶️', callback_data=f'adm:users:{segment}:{page + 1}'))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data='adm:users')])

    from aiogram.types import InlineKeyboardMarkup
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


# ── User card ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith('adm:user:card:'), AdminFilter())
async def on_user_card(callback: CallbackQuery):
    tid = int(callback.data.split(':')[-1])
    data = await services.get_user_card(tid)
    if not data:
        await callback.answer('Не найден', show_alert=True)
        return

    u = data['user']
    act = u.last_activity_at.strftime('%d.%m.%Y %H:%M') if u.last_activity_at else 'нет'
    status = '🚫 Заблокирован' if u.is_blocked else '✅ Активен'
    campaign = u.campaign.name if u.campaign else '—'

    # Live status
    from bot.services.matchmaking import matchmaking
    if matchmaking.is_in_chat(u.telegram_id):
        live = '💬 в чате'
    elif matchmaking.is_in_queue(u.telegram_id):
        live = '🔍 в поиске'
    else:
        live = '🟢 свободен'

    text = (
        f'👤 <b>Карточка пользователя</b>\n'
        f'\n'
        f'🆔 <code>{u.telegram_id}</code>\n'
        f'📛 {u.display_name}\n'
        f'👤 @{u.username or "—"}\n'
        f'\n'
        f'📅 Регистрация: {u.created_at:%d.%m.%Y}\n'
        f'⏰ Активность: {act}\n'
        f'📡 Статус: {status}\n'
        f'🎯 Сейчас: {live}\n'
        f'📣 Кампания: {campaign}\n'
        f'\n'
        f'💬 Чатов: {data["chats"]} (завершено: {data["closed_chats"]})\n'
        f'👍 {data["likes"]} / 👎 {data["dislikes"]}\n'
        f'🚨 Жалоб на него: {data["reports_on"]} / от него: {data["reports_by"]}'
    )

    await callback.message.edit_text(text, reply_markup=kb.user_card_kb(u.telegram_id, u.is_blocked))
    await callback.answer()


@router.callback_query(F.data.startswith('adm:user:toggle_block:'), AdminFilter())
async def on_toggle_block(callback: CallbackQuery):
    tid = int(callback.data.split(':')[-1])

    def _toggle():
        u = TelegramUser.objects.get(telegram_id=tid)
        u.is_blocked = not u.is_blocked
        u.save(update_fields=['is_blocked'])
        return u.is_blocked

    new_state = await sync_to_async(_toggle)()

    emoji = '🔒' if new_state else '🔓'
    await callback.answer(f'{emoji} {"Заблокирован" if new_state else "Разблокирован"}', show_alert=True)

    # Refresh card
    data = await services.get_user_card(tid)
    if data:
        u = data['user']
        # Re-render (reuse on_user_card logic via edit)
        callback.data = f'adm:user:card:{tid}'
        await on_user_card(callback)


# ═══════════════════════════════════════════════════════════════════════
#  📢 Channels
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:channels', AdminFilter())
async def on_channels(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    channels = await sync_to_async(list)(RequiredChannel.objects.all())
    await callback.message.edit_text(
        f'📢 <b>Обязательные каналы</b> — {len(channels)}',
        reply_markup=kb.channels_list_kb(channels),
    )
    await callback.answer()


@router.callback_query(F.data.startswith('adm:ch:view:'), AdminFilter())
async def on_channel_card(callback: CallbackQuery):
    ch_id = int(callback.data.split(':')[-1])
    ch = await sync_to_async(RequiredChannel.objects.get)(id=ch_id)

    from apps.users.models import ChannelSubscriptionEvent
    subs = await sync_to_async(
        ChannelSubscriptionEvent.objects.filter(channel_username=ch.channel_username).count
    )()

    status = '🟢 Активен' if ch.is_active else '🔴 Выключен'

    text = (
        f'📢 <b>{ch.title}</b>\n'
        f'\n'
        f'📛 {ch.channel_username}\n'
        f'🔗 {ch.invite_link}\n'
        f'📊 Статус: {status}\n'
        f'📅 Добавлен: {ch.created_at:%d.%m.%Y}\n'
        f'👥 Подписок: {subs}'
    )

    await callback.message.edit_text(text, reply_markup=kb.channel_card_kb(ch.id, ch.is_active))
    await callback.answer()


@router.callback_query(F.data.startswith('adm:ch:toggle:'), AdminFilter())
async def on_channel_toggle(callback: CallbackQuery):
    ch_id = int(callback.data.split(':')[-1])

    def _t():
        ch = RequiredChannel.objects.get(id=ch_id)
        ch.is_active = not ch.is_active
        ch.save(update_fields=['is_active'])
        return ch.is_active

    new = await sync_to_async(_t)()
    await callback.answer(f'{"🟢 Включен" if new else "🔴 Выключен"}', show_alert=True)
    callback.data = f'adm:ch:view:{ch_id}'
    await on_channel_card(callback)


@router.callback_query(F.data.startswith('adm:ch:delete:'), AdminFilter())
async def on_channel_delete_ask(callback: CallbackQuery):
    ch_id = int(callback.data.split(':')[-1])
    ch = await sync_to_async(RequiredChannel.objects.get)(id=ch_id)
    await callback.message.edit_text(
        f'❗ Удалить канал <b>{ch.title}</b>?',
        reply_markup=kb.confirm_delete_kb('adm:ch', ch.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith('adm:ch:confirm_del:'), AdminFilter())
async def on_channel_delete_confirm(callback: CallbackQuery):
    ch_id = int(callback.data.split(':')[-1])
    await sync_to_async(RequiredChannel.objects.filter(id=ch_id).delete)()
    await callback.answer('✅ Удалён', show_alert=True)
    callback.data = 'adm:channels'
    await on_channels(callback, FSMContext(
        storage=callback.bot.get('fsm_storage'),
        key=None,
    ) if False else None)
    # Simpler: just reload channels
    channels = await sync_to_async(list)(RequiredChannel.objects.all())
    await callback.message.edit_text(
        f'📢 <b>Обязательные каналы</b> — {len(channels)}',
        reply_markup=kb.channels_list_kb(channels),
    )


# ── Add channel FSM ──────────────────────────────────────────────────────

@router.callback_query(F.data == 'adm:ch:add', AdminFilter())
async def on_channel_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannelFSM.title)
    await callback.message.edit_text(
        '📢 <b>Добавить канал</b>\n\nВведи название:',
        reply_markup=kb.back_button('adm:channels'),
    )
    await callback.answer()


async def _handle_channel_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddChannelFSM.username)
    await message.answer('Введи @username канала (с @):')


async def _handle_channel_username(message: Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await state.set_state(AddChannelFSM.invite_link)
    await message.answer('Введи invite ссылку (https://t.me/...):')


async def _handle_channel_link(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    await sync_to_async(RequiredChannel.objects.create)(
        title=data['title'],
        channel_username=data['username'],
        invite_link=message.text.strip(),
    )

    channels = await sync_to_async(list)(RequiredChannel.objects.all())
    await message.answer(
        f'✅ Канал <b>{data["title"]}</b> добавлен!\n\n'
        f'📢 <b>Обязательные каналы</b> — {len(channels)}',
        reply_markup=kb.channels_list_kb(channels),
    )


# ═══════════════════════════════════════════════════════════════════════
#  🤖 Bots
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:bots', AdminFilter())
async def on_bots(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    bots = await sync_to_async(list)(RequiredBot.objects.all())
    await callback.message.edit_text(
        f'🤖 <b>Обязательные боты</b> — {len(bots)}',
        reply_markup=kb.bots_list_kb(bots),
    )
    await callback.answer()


@router.callback_query(F.data.startswith('adm:bt:view:'), AdminFilter())
async def on_bot_card(callback: CallbackQuery):
    bt_id = int(callback.data.split(':')[-1])
    bt = await sync_to_async(RequiredBot.objects.get)(id=bt_id)

    status = '🟢 Активен' if bt.is_active else '🔴 Выключен'

    text = (
        f'🤖 <b>{bt.title}</b>\n'
        f'\n'
        f'📛 {bt.bot_username}\n'
        f'🔗 {bt.invite_link}\n'
        f'📊 Статус: {status}\n'
        f'📅 Добавлен: {bt.created_at:%d.%m.%Y}'
    )

    await callback.message.edit_text(text, reply_markup=kb.bot_card_kb(bt.id, bt.is_active))
    await callback.answer()


@router.callback_query(F.data.startswith('adm:bt:toggle:'), AdminFilter())
async def on_bot_toggle(callback: CallbackQuery):
    bt_id = int(callback.data.split(':')[-1])

    def _t():
        bt = RequiredBot.objects.get(id=bt_id)
        bt.is_active = not bt.is_active
        bt.save(update_fields=['is_active'])
        return bt.is_active

    new = await sync_to_async(_t)()
    await callback.answer(f'{"🟢 Включен" if new else "🔴 Выключен"}', show_alert=True)
    callback.data = f'adm:bt:view:{bt_id}'
    await on_bot_card(callback)


@router.callback_query(F.data.startswith('adm:bt:delete:'), AdminFilter())
async def on_bot_delete_ask(callback: CallbackQuery):
    bt_id = int(callback.data.split(':')[-1])
    bt = await sync_to_async(RequiredBot.objects.get)(id=bt_id)
    await callback.message.edit_text(
        f'❗ Удалить бота <b>{bt.title}</b>?',
        reply_markup=kb.confirm_delete_kb('adm:bt', bt.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith('adm:bt:confirm_del:'), AdminFilter())
async def on_bot_delete_confirm(callback: CallbackQuery):
    bt_id = int(callback.data.split(':')[-1])
    await sync_to_async(RequiredBot.objects.filter(id=bt_id).delete)()
    await callback.answer('✅ Удалён', show_alert=True)
    bots = await sync_to_async(list)(RequiredBot.objects.all())
    await callback.message.edit_text(
        f'🤖 <b>Обязательные боты</b> — {len(bots)}',
        reply_markup=kb.bots_list_kb(bots),
    )


# ── Add bot FSM ──────────────────────────────────────────────────────────

@router.callback_query(F.data == 'adm:bt:add', AdminFilter())
async def on_bot_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddBotFSM.title)
    await callback.message.edit_text(
        '🤖 <b>Добавить бота</b>\n\nВведи название:',
        reply_markup=kb.back_button('adm:bots'),
    )
    await callback.answer()


async def _handle_bot_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddBotFSM.username)
    await message.answer('Введи @username бота (с @):')


async def _handle_bot_username(message: Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await state.set_state(AddBotFSM.invite_link)
    await message.answer('Введи ссылку на бота (https://t.me/...):')


async def _handle_bot_link(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    await sync_to_async(RequiredBot.objects.create)(
        title=data['title'],
        bot_username=data['username'],
        invite_link=message.text.strip(),
    )

    bots = await sync_to_async(list)(RequiredBot.objects.all())
    await message.answer(
        f'✅ Бот <b>{data["title"]}</b> добавлен!\n\n'
        f'🤖 <b>Обязательные боты</b> — {len(bots)}',
        reply_markup=kb.bots_list_kb(bots),
    )


# ═══════════════════════════════════════════════════════════════════════
#  💬 Chats
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:chats', AdminFilter())
async def on_chats_menu(callback: CallbackQuery):
    from apps.chat.models import ChatSession
    active = await sync_to_async(ChatSession.objects.filter(status='active').count)()
    closed = await sync_to_async(ChatSession.objects.filter(status='closed').count)()
    await callback.message.edit_text(
        f'💬 <b>Чаты</b>\n\n🟢 Активные: {active}\n🔴 Завершённые: {closed}',
        reply_markup=kb.chats_menu,
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r'^adm:chats:(active|closed):(\d+)$'), AdminFilter())
async def on_chats_list(callback: CallbackQuery):
    parts = callback.data.split(':')
    status = parts[2]
    page = int(parts[3])

    chats, total = await services.get_chats_list(status, page, PAGE_SIZE)

    label = '🟢 Активные' if status == 'active' else '🔴 Завершённые'
    lines = [f'{label} — <b>{total}</b>\n']

    for s in chats:
        u1 = await sync_to_async(lambda: s.user1.display_name)()
        u2 = await sync_to_async(lambda: s.user2.display_name)()
        date = s.created_at.strftime('%d.%m %H:%M')
        msgs = await sync_to_async(s.messages.count)()
        lines.append(f'• {date} | {u1} ↔ {u2} | 💬{msgs}')

    text = '\n'.join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=kb.pagination_kb(f'adm:chats:{status}', page, total, PAGE_SIZE, 'adm:chats'),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  🖼 Media
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:media', AdminFilter())
async def on_media(callback: CallbackQuery):
    await _show_media_page(callback, 0)


@router.callback_query(F.data.startswith('adm:media:'), AdminFilter())
async def on_media_page(callback: CallbackQuery):
    page = int(callback.data.split(':')[-1])
    await _show_media_page(callback, page)


async def _show_media_page(callback: CallbackQuery, page: int):
    items, total = await services.get_media_list(page, PAGE_SIZE)

    lines = [f'🖼 <b>Медиа</b> — {total}\n']
    for m in items:
        sender = await sync_to_async(lambda: m.sender.display_name)()
        date = m.created_at.strftime('%d.%m %H:%M')
        t = m.get_message_type_display()
        lines.append(f'• {date} | {t} | {sender}')

    text = '\n'.join(lines) if items else '🖼 Медиа нет.'

    await callback.message.edit_text(
        text,
        reply_markup=kb.pagination_kb('adm:media', page, total, PAGE_SIZE),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  🚨 Reports
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:reports', AdminFilter())
async def on_reports(callback: CallbackQuery):
    await _show_reports_page(callback, 0)


@router.callback_query(F.data.startswith('adm:reports:'), AdminFilter())
async def on_reports_page(callback: CallbackQuery):
    page = int(callback.data.split(':')[-1])
    await _show_reports_page(callback, page)


async def _show_reports_page(callback: CallbackQuery, page: int):
    items, total = await services.get_reports_list(page, PAGE_SIZE)

    lines = [f'🚨 <b>Жалобы</b> — {total}\n']
    for r in items:
        fr = await sync_to_async(lambda: r.from_user.display_name)()
        ag = await sync_to_async(lambda: r.against_user.display_name)()
        date = r.created_at.strftime('%d.%m %H:%M')
        reviewed = '✅' if r.is_reviewed else '⏳'
        lines.append(f'{reviewed} {date} | {fr} → {ag}')

    text = '\n'.join(lines) if items else '🚨 Жалоб нет.'

    await callback.message.edit_text(
        text,
        reply_markup=kb.pagination_kb('adm:reports', page, total, PAGE_SIZE),
    )
    await callback.answer()


# ═══════════════════════════════════════════════════════════════════════
#  📈 Funnel
# ═══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == 'adm:funnel', AdminFilter())
async def on_funnel_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        '📈 <b>Воронка</b>\n\nВыбери период 👇',
        reply_markup=kb.funnel_menu,
    )
    await callback.answer()


@router.callback_query(F.data.startswith('adm:funnel:'), AdminFilter())
async def on_funnel_data(callback: CallbackQuery):
    days = int(callback.data.split(':')[-1])
    stages = await services.get_funnel(days)

    period = {1: 'Сегодня', 7: '7 дней', 30: '30 дней'}.get(days, f'{days}д')

    lines = [f'📈 <b>Воронка — {period}</b>\n']

    first_count = stages[0][1] if stages else 0

    for i, (label, count) in enumerate(stages):
        # Conversion to previous
        if i > 0 and stages[i - 1][1] > 0:
            conv_prev = round(count / stages[i - 1][1] * 100, 1)
        else:
            conv_prev = 100.0

        # Conversion to start
        if first_count > 0:
            conv_start = round(count / first_count * 100, 1)
        else:
            conv_start = 0

        bar = '█' * max(1, int(conv_start / 10))
        lines.append(
            f'{bar} <b>{count}</b> — {label}\n'
            f'   <i>{conv_prev}% от пред. · {conv_start}% от старта</i>'
        )

    text = '\n'.join(lines)

    await callback.message.edit_text(text, reply_markup=kb.funnel_menu)
    await callback.answer()
