"""
Referral analytics services — per-campaign stats, funnel, quality scoring.
"""
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser, ReferralCampaign
from apps.chat.models import ChatSession
from apps.reports.models import Report


# ── Campaign list with key metrics ────────────────────────────────────

async def get_campaign_list(page: int = 0, per_page: int = 8) -> tuple[list, int]:
    """Paginated campaigns with basic metrics."""
    now = timezone.now()
    d3 = now - timedelta(days=3)

    def _q():
        qs = ReferralCampaign.objects.all().order_by('-created_at')
        total = qs.count()
        campaigns = list(qs[page * per_page:(page + 1) * per_page])

        result = []
        for c in campaigns:
            users = TelegramUser.objects.filter(campaign=c)
            total_users = users.count()
            alive = users.filter(last_activity_at__gte=d3).count()

            # First chat conversion
            user_ids = list(users.values_list('telegram_id', flat=True))
            first_chat = 0
            if user_ids:
                from apps.analytics.models import UserEvent
                first_chat = UserEvent.objects.filter(
                    user__telegram_id__in=user_ids,
                    event_type='chat_started',
                ).values('user').distinct().count()

            conv = round(first_chat / max(total_users, 1) * 100, 1)

            result.append({
                'campaign': c,
                'total_users': total_users,
                'alive': alive,
                'first_chat': first_chat,
                'conversion': conv,
            })

        return result, total

    return await sync_to_async(_q)()


# ── Full campaign card ────────────────────────────────────────────────

async def get_campaign_card(campaign_id: int) -> dict | None:
    """Full stats for a single campaign."""
    now = timezone.now()
    d1 = now - timedelta(days=1)
    d3 = now - timedelta(days=3)
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    def _q():
        try:
            c = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return None

        users = TelegramUser.objects.filter(campaign=c)
        total_users = users.count()

        # New users
        new_1d = users.filter(created_at__gte=d1).count()
        new_7d = users.filter(created_at__gte=d7).count()
        new_30d = users.filter(created_at__gte=d30).count()

        # Activity
        alive_1d = users.filter(last_activity_at__gte=d1).count()
        alive_7d = users.filter(last_activity_at__gte=d7).count()
        dead_3d = users.filter(
            Q(last_activity_at__lt=d3) | Q(last_activity_at__isnull=True)
        ).count()
        dead_30d = users.filter(
            Q(last_activity_at__lt=d30) | Q(last_activity_at__isnull=True)
        ).count()

        # Funnel (all-time)
        user_ids = list(users.values_list('telegram_id', flat=True))

        funnel = {}
        if user_ids:
            from apps.analytics.models import UserEvent
            stages = [
                'required_channels_passed', 'required_bots_passed',
                'search_started', 'match_found',
                'chat_started', 'next_search_started',
            ]
            for stage in stages:
                funnel[stage] = UserEvent.objects.filter(
                    user__telegram_id__in=user_ids,
                    event_type=stage,
                ).values('user').distinct().count()

        # Quality
        total_closed = ChatSession.objects.filter(
            Q(user1__campaign=c) | Q(user2__campaign=c),
            status='closed',
        ).count()
        avg_chats = round(total_closed / max(total_users, 1), 1)

        reports_sent = Report.objects.filter(
            from_user__campaign=c,
        ).count()
        reports_received = Report.objects.filter(
            against_user__campaign=c,
        ).count()

        # Quality score (0-100)
        quality = _calc_quality(
            total_users, alive_7d, dead_3d,
            funnel.get('chat_started', 0),
            funnel.get('next_search_started', 0),
            reports_received,
        )

        return {
            'campaign': c,
            'total': total_users,
            'new_1d': new_1d, 'new_7d': new_7d, 'new_30d': new_30d,
            'alive_1d': alive_1d, 'alive_7d': alive_7d,
            'dead_3d': dead_3d, 'dead_30d': dead_30d,
            'funnel': funnel,
            'avg_chats': avg_chats,
            'reports_sent': reports_sent,
            'reports_received': reports_received,
            'quality': quality,
        }

    return await sync_to_async(_q)()


def _calc_quality(total, alive_7d, dead_3d, chats, returns, reports) -> int:
    """Simple quality score 0-100."""
    if total == 0:
        return 0

    alive_pct = alive_7d / total  # 0-1
    chat_pct = chats / total      # 0-1
    return_pct = returns / max(chats, 1)  # 0-1
    report_penalty = min(reports / max(total, 1), 0.5)  # 0-0.5

    score = (
        alive_pct * 30 +       # 30% weight: are users alive?
        chat_pct * 30 +        # 30% weight: did they chat?
        return_pct * 25 +      # 25% weight: did they return?
        (1 - report_penalty) * 15  # 15% weight: low reports = good
    )

    return min(100, max(0, round(score * 100 / 100)))


# ── Campaign funnel with periods ──────────────────────────────────────

async def get_campaign_funnel(campaign_id: int, days: int = 0) -> list[tuple[str, int]]:
    """Funnel for a specific campaign. days=0 means all time."""
    def _q():
        try:
            c = ReferralCampaign.objects.get(id=campaign_id)
        except ReferralCampaign.DoesNotExist:
            return []

        user_ids = list(
            TelegramUser.objects.filter(campaign=c)
            .values_list('telegram_id', flat=True)
        )
        if not user_ids:
            return []

        from apps.analytics.models import UserEvent

        STAGES = [
            ('start_opened', 'Открыл /start'),
            ('required_channels_passed', 'Каналы пройдены'),
            ('required_bots_passed', 'Боты пройдены'),
            ('main_menu_shown', 'Главное меню'),
            ('search_started', 'Начал поиск'),
            ('match_found', 'Найден партнёр'),
            ('chat_started', 'Чат начат'),
            ('chat_finished', 'Чат завершён'),
            ('next_search_started', 'Следующий поиск'),
        ]

        results = []
        for event_type, label in STAGES:
            qs = UserEvent.objects.filter(
                user__telegram_id__in=user_ids,
                event_type=event_type,
            )
            if days > 0:
                since = timezone.now() - timedelta(days=days)
                qs = qs.filter(created_at__gte=since)
            count = qs.values('user').distinct().count()
            results.append((label, count))

        return results

    return await sync_to_async(_q)()


# ── Top campaigns ─────────────────────────────────────────────────────

async def get_top_campaigns(limit: int = 10) -> dict:
    """Top campaigns by various metrics."""
    now = timezone.now()
    d3 = now - timedelta(days=3)

    def _q():
        campaigns = list(ReferralCampaign.objects.all())
        if not campaigns:
            return {'by_users': [], 'by_alive': [], 'by_chats': [], 'by_quality': []}

        data = []
        from apps.analytics.models import UserEvent

        for c in campaigns:
            users = TelegramUser.objects.filter(campaign=c)
            total = users.count()
            if total == 0:
                continue

            alive = users.filter(last_activity_at__gte=d3).count()

            user_ids = list(users.values_list('telegram_id', flat=True))
            chats = UserEvent.objects.filter(
                user__telegram_id__in=user_ids,
                event_type='chat_started',
            ).values('user').distinct().count()

            returns = UserEvent.objects.filter(
                user__telegram_id__in=user_ids,
                event_type='next_search_started',
            ).values('user').distinct().count()

            reports = Report.objects.filter(against_user__campaign=c).count()

            quality = _calc_quality(total, alive, 0, chats, returns, reports)
            conv = round(chats / total * 100, 1)

            data.append({
                'campaign': c,
                'total': total,
                'alive': alive,
                'chats': chats,
                'conv': conv,
                'quality': quality,
            })

        by_users = sorted(data, key=lambda x: x['total'], reverse=True)[:limit]
        by_alive = sorted(data, key=lambda x: x['alive'], reverse=True)[:limit]
        by_chats = sorted(data, key=lambda x: x['chats'], reverse=True)[:limit]
        by_quality = sorted(data, key=lambda x: x['quality'], reverse=True)[:limit]

        return {
            'by_users': by_users,
            'by_alive': by_alive,
            'by_chats': by_chats,
            'by_quality': by_quality,
        }

    return await sync_to_async(_q)()


# ── Campaign users list ───────────────────────────────────────────────

async def get_campaign_users(campaign_id: int, page: int = 0, per_page: int = 8) -> tuple[list, int]:
    """Paginated users from a campaign."""
    def _q():
        qs = TelegramUser.objects.filter(
            campaign_id=campaign_id
        ).order_by('-created_at')
        total = qs.count()
        items = list(qs[page * per_page:(page + 1) * per_page])
        return items, total

    return await sync_to_async(_q)()
