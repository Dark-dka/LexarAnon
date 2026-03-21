from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import TelegramUser, Rating, RequiredChannel, RequiredBot, ChannelSubscriptionEvent


class ReferredByFilter(admin.SimpleListFilter):
    title = 'приглашён по рефералке'
    parameter_name = 'has_referrer'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'Да — пришёл по ссылке'),
            ('no', 'Нет — сам нашёл'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(referred_by__isnull=False)
        if self.value() == 'no':
            return queryset.filter(referred_by__isnull=True)
        return queryset



@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = [
        'telegram_id',
        'username',
        'first_name',
        'last_name',
        'gender',
        'search_gender',
        'photo_preview',
        'likes_count',
        'dislikes_count',
        'referrals_count',
        'is_active',
        'is_blocked',
        'created_at',
    ]
    list_filter = ['is_active', 'is_blocked', 'gender', 'search_gender', 'created_at', ReferredByFilter]
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    readonly_fields = ['telegram_id', 'created_at', 'updated_at', 'photo_large', 'likes_count', 'dislikes_count', 'referrals_count']
    list_editable = ['is_blocked']
    list_per_page = 50
    actions = ['block_users', 'unblock_users']

    fieldsets = (
        ('Telegram данные', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name', 'language_code'),
        }),
        ('Пол и поиск', {
            'fields': ('gender', 'search_gender'),
        }),
        ('Фото профиля', {
            'fields': ('profile_photo', 'photo_large'),
        }),
        ('Статистика', {
            'fields': ('likes_count', 'dislikes_count', 'referrals_count'),
        }),
        ('Реферал', {
            'fields': ('referred_by',),
        }),
        ('Статус', {
            'fields': ('is_active', 'is_blocked'),
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
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

    @admin.display(description='👥 Рефералов')
    def referrals_count(self, obj):
        return obj.referrals.count()

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
        from django.utils.html import format_html
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
        from django.utils.html import format_html
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

