"""
Admin panel data services — stats queries, segments, funnel.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, RequiredChannel, RequiredBot, BotClickEvent, ChannelSubscriptionEvent
from apps.chat.models import ChatSession
from apps.reports.models import Report


async def get_stats() -> dict:
    """Aggregate all dashboard stats."""
    now = timezone.now()
    d1 = now - timedelta(days=1)
    d3 = now - timedelta(days=3)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    def _q():
        total = TelegramUser.objects.count()
        new_1d = TelegramUser.objects.filter(created_at__gte=d1).count()
        new_7d = TelegramUser.objects.filter(created_at__gte=d7).count()
        new_30d = TelegramUser.objects.filter(created_at__gte=d30).count()

        alive_1d = TelegramUser.objects.filter(last_activity_at__gte=d1).count()
        alive_7d = TelegramUser.objects.filter(last_activity_at__gte=d7).count()
        alive_30d = TelegramUser.objects.filter(last_activity_at__gte=d30).count()

        dead_3d = TelegramUser.objects.filter(
            Q(last_activity_at__lt=d3) | Q(last_activity_at__isnull=True)
        ).count()
        dead_30d = TelegramUser.objects.filter(
            Q(last_activity_at__lt=d30) | Q(last_activity_at__isnull=True)
        ).count()

        blocked = TelegramUser.objects.filter(is_blocked=True).count()

        chats_today = ChatSession.objects.filter(
            status='closed', ended_at__gte=d1
        ).count()
        chats_7d = ChatSession.objects.filter(
            status='closed', ended_at__gte=d7
        ).count()
        active_chats = ChatSession.objects.filter(status='active').count()

        reports_today = Report.objects.filter(created_at__gte=d1).count()
        reports_7d = Report.objects.filter(created_at__gte=d7).count()

        # Avg chats per user
        total_closed = ChatSession.objects.filter(status='closed').count()
        avg_chats = round(total_closed / max(total, 1), 1)

        return {
            'total': total,
            'new_1d': new_1d, 'new_7d': new_7d, 'new_30d': new_30d,
            'alive_1d': alive_1d, 'alive_7d': alive_7d, 'alive_30d': alive_30d,
            'dead_3d': dead_3d, 'dead_30d': dead_30d,
            'blocked': blocked,
            'active_chats': active_chats,
            'chats_today': chats_today, 'chats_7d': chats_7d,
            'reports_today': reports_today, 'reports_7d': reports_7d,
            'avg_chats': avg_chats,
        }

    return await sync_to_async(_q)()


async def get_users_list(segment: str, page: int = 0, per_page: int = 10) -> tuple[list, int]:
    """Get paginated user list by segment. Returns (users, total_count)."""
    now = timezone.now()
    d1 = now - timedelta(days=1)
    d3 = now - timedelta(days=3)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    def _q():
        qs = TelegramUser.objects.all()
        if segment == 'recent':
            qs = qs.order_by('-created_at')
        elif segment == 'alive_1d':
            qs = qs.filter(last_activity_at__gte=d1).order_by('-last_activity_at')
        elif segment == 'alive_7d':
            qs = qs.filter(last_activity_at__gte=d7).order_by('-last_activity_at')
        elif segment == 'dead_3d':
            qs = qs.filter(
                Q(last_activity_at__lt=d3) | Q(last_activity_at__isnull=True)
            ).order_by('-created_at')
        elif segment == 'dead_30d':
            qs = qs.filter(
                Q(last_activity_at__lt=d30) | Q(last_activity_at__isnull=True)
            ).order_by('-created_at')
        elif segment == 'blocked':
            qs = qs.filter(is_blocked=True).order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')

        total = qs.count()
        items = list(qs[page * per_page:(page + 1) * per_page])
        return items, total

    return await sync_to_async(_q)()


async def get_user_card(telegram_id: int) -> dict | None:
    """Get full user card data."""
    def _q():
        try:
            u = TelegramUser.objects.get(telegram_id=telegram_id)
        except TelegramUser.DoesNotExist:
            return None

        chats = ChatSession.objects.filter(
            Q(user1=u) | Q(user2=u)
        ).count()
        closed_chats = ChatSession.objects.filter(
            Q(user1=u) | Q(user2=u), status='closed'
        ).count()
        likes = u.ratings_received.filter(is_like=True).count()
        dislikes = u.ratings_received.filter(is_like=False).count()
        reports_on = u.reports_received.count()
        reports_by = u.reports_sent.count()

        return {
            'user': u,
            'chats': chats,
            'closed_chats': closed_chats,
            'likes': likes,
            'dislikes': dislikes,
            'reports_on': reports_on,
            'reports_by': reports_by,
        }

    return await sync_to_async(_q)()


async def search_user(query: str) -> list:
    """Search users by telegram_id or username."""
    def _q():
        if query.isdigit():
            return list(TelegramUser.objects.filter(telegram_id=int(query))[:5])
        q = query.lstrip('@')
        return list(TelegramUser.objects.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q)
        )[:10])

    return await sync_to_async(_q)()


async def get_chats_list(status: str, page: int = 0, per_page: int = 8) -> tuple[list, int]:
    """Get paginated chat sessions."""
    def _q():
        qs = ChatSession.objects.select_related('user1', 'user2')
        if status == 'active':
            qs = qs.filter(status='active').order_by('-created_at')
        else:
            qs = qs.filter(status='closed').order_by('-ended_at')
        total = qs.count()
        items = list(qs[page * per_page:(page + 1) * per_page])
        return items, total

    return await sync_to_async(_q)()


async def get_reports_list(page: int = 0, per_page: int = 8) -> tuple[list, int]:
    """Get paginated reports."""
    def _q():
        qs = Report.objects.select_related(
            'from_user', 'against_user', 'chat_session'
        ).order_by('-created_at')
        total = qs.count()
        items = list(qs[page * per_page:(page + 1) * per_page])
        return items, total

    return await sync_to_async(_q)()


async def get_funnel(days: int = 7) -> list[tuple[str, int]]:
    """Get funnel data for the given period."""
    from apps.analytics.models import UserEvent

    since = timezone.now() - timedelta(days=days)

    STAGES = [
        ('start_opened', 'Открыл /start'),
        ('required_channels_shown', 'Каналы показаны'),
        ('required_channels_passed', 'Каналы пройдены'),
        ('required_bots_shown', 'Боты показаны'),
        ('required_bots_passed', 'Боты пройдены'),
        ('main_menu_shown', 'Главное меню'),
        ('search_started', 'Начал поиск'),
        ('match_found', 'Найден партнёр'),
        ('chat_started', 'Чат начат'),
        ('chat_finished', 'Чат завершён'),
        ('next_search_started', 'Следующий поиск'),
    ]

    def _q():
        results = []
        for event_type, label in STAGES:
            count = UserEvent.objects.filter(
                event_type=event_type,
                created_at__gte=since,
            ).values('user').distinct().count()
            results.append((label, count))
        return results

    return await sync_to_async(_q)()


async def get_media_list(page: int = 0, per_page: int = 8) -> tuple[list, int]:
    """Get paginated media messages."""
    from apps.chat.models import Message

    def _q():
        qs = Message.objects.exclude(
            message_type='text'
        ).select_related('sender', 'chat_session').order_by('-created_at')
        total = qs.count()
        items = list(qs[page * per_page:(page + 1) * per_page])
        return items, total

    return await sync_to_async(_q)()


async def touch_activity(telegram_id: int):
    """Update last_activity_at for a user."""
    def _q():
        TelegramUser.objects.filter(telegram_id=telegram_id).update(
            last_activity_at=timezone.now()
        )
    await sync_to_async(_q)()


async def get_subscription_stats() -> dict:
    """Aggregate stats for required channels and required bots pass-through."""
    def _q():
        total_users = TelegramUser.objects.count()

        # ── Channels ─────────────────────────────────
        active_channels = list(RequiredChannel.objects.filter(is_active=True))
        ch_count = len(active_channels)

        # Users who passed channels = have ChannelSubscriptionEvent for ALL active channels
        ch_passed = 0
        if active_channels:
            from django.db.models import Count as Cnt
            ch_usernames = [c.channel_username for c in active_channels]
            ch_passed = (
                ChannelSubscriptionEvent.objects
                .filter(channel_username__in=ch_usernames)
                .values('user')
                .annotate(cnt=Cnt('channel_username', distinct=True))
                .filter(cnt__gte=ch_count)
                .count()
            )

        # Per-channel subscription counts
        ch_breakdown = []
        for ch in active_channels:
            sub_count = ChannelSubscriptionEvent.objects.filter(
                channel_username=ch.channel_username,
            ).count()
            ch_breakdown.append({
                'title': ch.title,
                'username': ch.channel_username,
                'subs': sub_count,
            })

        # ── Bots ─────────────────────────────────────
        active_bots = list(RequiredBot.objects.filter(is_active=True))
        bot_count = len(active_bots)

        # Users who confirmed bots
        bots_confirmed = TelegramUser.objects.filter(
            bots_confirmed_at__isnull=False,
        ).count()

        # Total click events and self-confirm events
        total_clicks = BotClickEvent.objects.count()
        total_confirms = BotClickEvent.objects.filter(
            self_confirmed_at__isnull=False,
        ).count()

        # Per-bot breakdown
        bot_breakdown = []
        for b in active_bots:
            username = b.bot_username.lstrip('@')
            clicks = BotClickEvent.objects.filter(bot_username=username).count()
            confirms = BotClickEvent.objects.filter(
                bot_username=username,
                self_confirmed_at__isnull=False,
            ).count()
            bot_breakdown.append({
                'title': b.title,
                'username': username,
                'clicks': clicks,
                'confirms': confirms,
            })

        # Stuck: users who haven't confirmed bots yet
        stuck_on_bots = 0
        if active_bots:
            stuck_on_bots = TelegramUser.objects.filter(
                bots_confirmed_at__isnull=True,
            ).count()

        return {
            'total_users': total_users,
            'ch_count': ch_count,
            'ch_passed': ch_passed,
            'ch_breakdown': ch_breakdown,
            'bot_count': bot_count,
            'bots_confirmed': bots_confirmed,
            'total_clicks': total_clicks,
            'total_confirms': total_confirms,
            'bot_breakdown': bot_breakdown,
            'stuck_on_bots': stuck_on_bots,
        }

    return await sync_to_async(_q)()

