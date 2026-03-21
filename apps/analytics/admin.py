"""
Analytics admin: event log + funnel summary dashboard.
"""
from datetime import timedelta

from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from .models import UserEvent, EventType


# ── Event type filter ─────────────────────────────────────────────────────

class FunnelStageFilter(admin.SimpleListFilter):
    title = 'этап воронки'
    parameter_name = 'stage'

    def lookups(self, request, model_admin):
        return [
            ('onboarding', '🟡 Онбординг'),
            ('channels', '📢 Каналы'),
            ('bots', '🤖 Боты'),
            ('core', '🔵 Ядро (поиск/чат)'),
            ('engagement', '💎 Вовлечение'),
        ]

    def queryset(self, request, queryset):
        mapping = {
            'onboarding': ['start_opened', 'gender_selection_shown', 'gender_selected'],
            'channels': ['required_channels_shown', 'subscription_check_clicked', 'required_channels_passed'],
            'bots': ['required_bots_shown', 'required_bot_confirmed', 'required_bots_passed'],
            'core': ['main_menu_shown', 'search_started', 'search_cancelled', 'match_found',
                      'chat_started', 'message_sent', 'chat_finished', 'partner_left',
                      'partner_rated', 'next_search_started', 'report_sent'],
            'engagement': ['profile_opened', 'settings_opened', 'how_it_works_opened'],
        }
        if self.value() in mapping:
            return queryset.filter(event_type__in=mapping[self.value()])
        return queryset


@admin.register(UserEvent)
class UserEventAdmin(admin.ModelAdmin):
    list_display = ['event_type_display', 'user', 'meta_short', 'created_at']
    list_filter = [FunnelStageFilter, 'event_type', 'created_at']
    search_fields = ['user__username', 'user__telegram_id', 'user__first_name']
    date_hierarchy = 'created_at'
    readonly_fields = ['user', 'event_type', 'meta', 'created_at']
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Событие')
    def event_type_display(self, obj):
        return obj.get_event_type_display()

    @admin.display(description='Мета')
    def meta_short(self, obj):
        if not obj.meta:
            return '—'
        parts = [f'{k}={v}' for k, v in obj.meta.items()]
        text = ', '.join(parts)
        if len(text) > 60:
            text = text[:57] + '...'
        return text


# ── Funnel Summary (proxy model for a stats page) ────────────────────────

class FunnelSummary(UserEvent):
    """Proxy model for the funnel dashboard in admin."""
    class Meta:
        proxy = True
        verbose_name = 'Воронка'
        verbose_name_plural = '📊 Воронка (сводка)'


FUNNEL_STEPS = [
    ('start_opened', '▶️ /start открыт'),
    ('required_channels_shown', '📢 Каналы показаны'),
    ('required_channels_passed', '✅ Каналы пройдены'),
    ('required_bots_shown', '🤖 Боты показаны'),
    ('required_bots_passed', '✅ Боты пройдены'),
    ('gender_selected', '⚧ Пол выбран'),
    ('main_menu_shown', '🏠 Меню показано'),
    ('search_started', '🔍 Поиск начат'),
    ('match_found', '🎯 Пара найдена'),
    ('chat_started', '💬 Чат начат'),
    ('chat_finished', '🚪 Чат завершён'),
    ('partner_rated', '⭐ Оценка'),
    ('next_search_started', '🔄 Следующий поиск'),
    ('report_sent', '🚨 Жалоба'),
]


@admin.register(FunnelSummary)
class FunnelSummaryAdmin(admin.ModelAdmin):
    change_list_template = 'admin/analytics_funnel.html'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        now = timezone.now()
        periods = {
            'today': now - timedelta(days=1),
            'week': now - timedelta(days=7),
            'month': now - timedelta(days=30),
        }

        funnel_data = []
        for event_type, label in FUNNEL_STEPS:
            row = {'label': label, 'event_type': event_type}
            for period_name, since in periods.items():
                cnt = UserEvent.objects.filter(
                    event_type=event_type,
                    created_at__gte=since,
                ).count()
                row[period_name] = cnt
            funnel_data.append(row)

        # Conversions
        conversions = []
        pairs = [
            ('start_opened', 'required_channels_passed', 'Start → Каналы пройдены'),
            ('required_channels_passed', 'required_bots_passed', 'Каналы → Боты пройдены'),
            ('required_bots_passed', 'search_started', 'Боты → Поиск начат'),
            ('search_started', 'match_found', 'Поиск → Пара найдена'),
            ('match_found', 'chat_finished', 'Пара → Чат завершён'),
            ('chat_finished', 'next_search_started', 'Чат завершён → Следующий'),
        ]
        for from_evt, to_evt, label in pairs:
            week_from = UserEvent.objects.filter(event_type=from_evt, created_at__gte=periods['week']).count()
            week_to = UserEvent.objects.filter(event_type=to_evt, created_at__gte=periods['week']).count()
            rate = f'{(week_to / week_from * 100):.0f}%' if week_from > 0 else '—'
            conversions.append({
                'label': label,
                'from_count': week_from,
                'to_count': week_to,
                'rate': rate,
            })

        extra_context = extra_context or {}
        extra_context['funnel_data'] = funnel_data
        extra_context['conversions'] = conversions
        extra_context['title'] = '📊 Воронка — сводка за 24ч / 7д / 30д'

        return super().changelist_view(request, extra_context=extra_context)
