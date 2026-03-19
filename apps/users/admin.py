from django.contrib import admin
from django.utils.html import format_html

from .models import TelegramUser, Rating


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
        'is_active',
        'is_blocked',
        'created_at',
    ]
    list_filter = ['is_active', 'is_blocked', 'gender', 'search_gender', 'created_at']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    readonly_fields = ['telegram_id', 'created_at', 'updated_at', 'photo_large', 'likes_count', 'dislikes_count']
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
            'fields': ('likes_count', 'dislikes_count'),
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
