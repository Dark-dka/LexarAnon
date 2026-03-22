from django.contrib import admin
from django.utils.html import format_html

from .models import TelegramUser, Rating, RequiredChannel, RequiredBot, ChannelSubscriptionEvent, ReferralCampaign, BotClickEvent


class CampaignFilter(admin.SimpleListFilter):
    title = 'рекламная кампания'
    parameter_name = 'has_campaign'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'Пришёл по рекламе'),
            ('no', 'Органически'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(campaign__isnull=False)
        if self.value() == 'no':
            return queryset.filter(campaign__isnull=True)
        return queryset


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = [
        'telegram_id',
        'username',
        'first_name',
        'last_name',
        'photo_preview',
        'likes_count',
        'dislikes_count',
        'campaign',
        'is_active',
        'is_blocked',
        'last_activity_at',
        'created_at',
    ]
    list_filter = ['is_active', 'is_blocked', 'created_at', 'campaign', CampaignFilter]
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    readonly_fields = ['telegram_id', 'created_at', 'updated_at', 'last_activity_at', 'photo_large', 'likes_count', 'dislikes_count']
    list_editable = ['is_blocked']
    list_per_page = 50
    actions = ['block_users', 'unblock_users']

    fieldsets = (
        ('Telegram данные', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name', 'language_code'),
        }),
        ('Фото профиля', {
            'fields': ('profile_photo', 'photo_large'),
        }),
        ('Статистика', {
            'fields': ('likes_count', 'dislikes_count'),
        }),
        ('Реклама', {
            'fields': ('campaign',),
        }),
        ('Статус', {
            'fields': ('is_active', 'is_blocked'),
        }),
        ('Legacy — пол (не используется)', {
            'fields': ('gender', 'search_gender'),
            'classes': ('collapse',),
            'description': 'Гендерные поля сохранены для совместимости с БД, '
                           'но больше не используются в интерфейсе бота.',
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'last_activity_at'),
        }),
    )

    @admin.display(description='Фото')
    def photo_preview(self, obj):
        if obj.profile_photo:
            return format_html(
                '<img src="{}" style="width:40px;height:40px;border-radius:50%;object-fit:cover;" />',
                obj.profile_photo.url,
            )
        return '—'

    @admin.display(description='Фото профиля (большое)')
    def photo_large(self, obj):
        if obj.profile_photo:
            return format_html(
                '<img src="{}" style="max-width:200px;max-height:200px;border-radius:8px;" />',
                obj.profile_photo.url,
            )
        return 'Нет фото'

    @admin.display(description='👍 Лайки')
    def likes_count(self, obj):
        return obj.ratings_received.filter(is_like=True).count()

    @admin.display(description='👎 Дизлайки')
    def dislikes_count(self, obj):
        return obj.ratings_received.filter(is_like=False).count()

    @admin.action(description='🔒 Заблокировать выбранных')
    def block_users(self, request, queryset):
        count = queryset.update(is_blocked=True)
        self.message_user(request, f'Заблокировано пользователей: {count}')

    @admin.action(description='🔓 Разблокировать выбранных')
    def unblock_users(self, request, queryset):
        count = queryset.update(is_blocked=False)
        self.message_user(request, f'Разблокировано пользователей: {count}')


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['id', 'from_user', 'to_user', 'rating_display', 'chat_session', 'created_at']
    list_filter = ['is_like', 'created_at']
    search_fields = ['from_user__username', 'to_user__username']
    readonly_fields = ['from_user', 'to_user', 'is_like', 'chat_session', 'created_at']

    @admin.display(description='Оценка')
    def rating_display(self, obj):
        return '👍 Лайк' if obj.is_like else '👎 Дизлайк'


@admin.register(RequiredChannel)
class RequiredChannelAdmin(admin.ModelAdmin):
    list_display = ['title', 'channel_username', 'invite_link_display', 'subscribers_count', 'is_active', 'created_at']
    list_editable = ['is_active']
    search_fields = ['title', 'channel_username']
    list_filter = ['is_active']
    list_per_page = 50

    fieldsets = (
        ('📢 Канал', {
            'fields': ('title', 'channel_username', 'invite_link', 'is_active'),
            'description': (
                'Укажите username канала (например: @mychannel) и ссылку для кнопки подписки. '
                'Бот должен быть администратором канала!'
            ),
        }),
        ('Мета', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['created_at']

    @admin.display(description='Ссылка')
    def invite_link_display(self, obj):
        return format_html('<a href="{}" target="_blank">{}</a>', obj.invite_link, obj.invite_link)

    @admin.display(description='👥 Подписчиков')
    def subscribers_count(self, obj):
        return ChannelSubscriptionEvent.objects.filter(
            channel_username=obj.channel_username
        ).count()


@admin.register(RequiredBot)
class RequiredBotAdmin(admin.ModelAdmin):
    list_display = ['title', 'bot_username', 'invite_link_display', 'is_active', 'created_at']
    list_editable = ['is_active']
    search_fields = ['title', 'bot_username']
    list_filter = ['is_active']
    list_per_page = 50

    fieldsets = (
        ('🤖 Бот', {
            'fields': ('title', 'bot_username', 'invite_link', 'is_active'),
            'description': (
                'Укажите username бота (например: @mybot) и ссылку для кнопки. '
                'Пользователь должен запустить этого бота.'
            ),
        }),
        ('Мета', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ['created_at']

    @admin.display(description='Ссылка')
    def invite_link_display(self, obj):
        return format_html('<a href="{}" target="_blank">{}</a>', obj.invite_link, obj.invite_link)


@admin.register(ChannelSubscriptionEvent)
class ChannelSubscriptionEventAdmin(admin.ModelAdmin):
    list_display = ['channel_title', 'channel_username', 'user', 'created_at']
    list_filter = ['channel_username', 'created_at']
    search_fields = ['channel_username', 'channel_title', 'user__username', 'user__telegram_id']
    readonly_fields = ['user', 'channel_username', 'channel_title', 'created_at']
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BotClickEvent)
class BotClickEventAdmin(admin.ModelAdmin):
    list_display = ['user', 'bot_username', 'clicked_at', 'self_confirmed_at']
    list_filter = ['bot_username', 'clicked_at', 'self_confirmed_at']
    search_fields = ['bot_username', 'user__username', 'user__telegram_id']
    readonly_fields = ['user', 'bot_username', 'clicked_at', 'self_confirmed_at']
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

@admin.register(ReferralCampaign)
class ReferralCampaignAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'code', 'is_active',
        'users_count_display', 'active_users_display', 'dead_users_display',
        'first_chat_display', 'avg_chats_display', 'quality_display',
        'invite_link_display', 'created_at',
    ]
    list_editable = ['is_active']
    search_fields = ['name', 'code']
    list_filter = ['is_active', 'created_at']
    readonly_fields = [
        'code', 'created_at',
        'users_count_display', 'active_users_display', 'dead_users_display',
        'first_chat_display', 'avg_chats_display', 'reports_display',
        'quality_display', 'invite_link_display',
    ]
    list_per_page = 50

    fieldsets = (
        ('🔗 Реферальная ссылка', {
            'fields': ('name', 'code', 'description', 'is_active'),
            'description': (
                'Код генерируется автоматически. '
                'Ссылка: https://t.me/«BOTNAME»?start=ref_КОД'
            ),
        }),
        ('📊 Статистика', {
            'fields': (
                'users_count_display', 'active_users_display', 'dead_users_display',
                'first_chat_display', 'avg_chats_display', 'reports_display',
                'quality_display', 'invite_link_display',
            ),
        }),
        ('Мета', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='👥 Всего')
    def users_count_display(self, obj):
        return obj.users.count()

    @admin.display(description='🟢 Живые 7д')
    def active_users_display(self, obj):
        from django.utils import timezone as tz
        from datetime import timedelta
        d7 = tz.now() - timedelta(days=7)
        return obj.users.filter(last_activity_at__gte=d7).count()

    @admin.display(description='💀 Мёртвые 3д+')
    def dead_users_display(self, obj):
        from django.utils import timezone as tz
        from datetime import timedelta
        from django.db.models import Q
        d3 = tz.now() - timedelta(days=3)
        return obj.users.filter(Q(last_activity_at__lt=d3) | Q(last_activity_at__isnull=True)).count()

    @admin.display(description='💬 Первый чат')
    def first_chat_display(self, obj):
        from apps.analytics.models import UserEvent
        user_ids = list(obj.users.values_list('telegram_id', flat=True))
        if not user_ids:
            return 0
        return UserEvent.objects.filter(
            user__telegram_id__in=user_ids,
            event_type='chat_started',
        ).values('user').distinct().count()

    @admin.display(description='💬 Ср. чатов')
    def avg_chats_display(self, obj):
        from apps.chat.models import ChatSession
        from django.db.models import Q
        total = obj.users.count()
        if total == 0:
            return '0'
        closed = ChatSession.objects.filter(
            Q(user1__campaign=obj) | Q(user2__campaign=obj),
            status='closed',
        ).count()
        return round(closed / total, 1)

    @admin.display(description='🚨 Жалоб')
    def reports_display(self, obj):
        from apps.reports.models import Report
        sent = Report.objects.filter(from_user__campaign=obj).count()
        received = Report.objects.filter(against_user__campaign=obj).count()
        return f'{sent} / {received}'

    @admin.display(description='⚡ Качество')
    def quality_display(self, obj):
        from django.utils import timezone as tz
        from datetime import timedelta
        from django.db.models import Q
        from apps.analytics.models import UserEvent
        from apps.reports.models import Report

        total = obj.users.count()
        if total == 0:
            return '—'

        d7 = tz.now() - timedelta(days=7)
        alive = obj.users.filter(last_activity_at__gte=d7).count()
        user_ids = list(obj.users.values_list('telegram_id', flat=True))
        chats = UserEvent.objects.filter(
            user__telegram_id__in=user_ids,
            event_type='chat_started',
        ).values('user').distinct().count()
        returns = UserEvent.objects.filter(
            user__telegram_id__in=user_ids,
            event_type='next_search_started',
        ).values('user').distinct().count()
        reports = Report.objects.filter(against_user__campaign=obj).count()

        alive_pct = alive / total
        chat_pct = chats / total
        return_pct = returns / max(chats, 1)
        report_penalty = min(reports / max(total, 1), 0.5)
        score = alive_pct * 30 + chat_pct * 30 + return_pct * 25 + (1 - report_penalty) * 15
        score = min(100, max(0, round(score * 100 / 100)))

        emoji = '🟢' if score >= 60 else '🟡' if score >= 30 else '🔴'
        return f'{emoji} {score}/100'

    @admin.display(description='🔗 Ссылка')
    def invite_link_display(self, obj):
        from bot.config import BOT_USERNAME
        bot = BOT_USERNAME or 'BOTNAME'
        link = f'https://t.me/{bot}?start=ref_{obj.code}'
        return format_html(
            '<a href="{}" target="_blank"><code>{}</code></a>',
            link, link,
        )

