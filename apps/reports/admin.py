from django.contrib import admin

from .models import Report
from apps.users.models import TelegramUser


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'from_user',
        'against_user',
        'chat_session',
        'reason_preview',
        'is_reviewed',
        'created_at',
    ]
    list_filter = ['is_reviewed', 'created_at']
    search_fields = [
        'from_user__username',
        'from_user__telegram_id',
        'against_user__username',
        'against_user__telegram_id',
        'reason',
    ]
    readonly_fields = ['from_user', 'against_user', 'chat_session', 'reason', 'created_at']
    list_editable = ['is_reviewed']
    list_per_page = 50
    actions = ['mark_reviewed', 'block_reported_users']

    fieldsets = (
        ('Участники', {
            'fields': ('from_user', 'against_user', 'chat_session'),
        }),
        ('Жалоба', {
            'fields': ('reason', 'is_reviewed'),
        }),
        ('Дата', {
            'fields': ('created_at',),
        }),
    )

    @admin.display(description='Причина')
    def reason_preview(self, obj):
        if obj.reason:
            return obj.reason[:100] + ('...' if len(obj.reason) > 100 else '')
        return '—'

    @admin.action(description='✅ Отметить как рассмотренные')
    def mark_reviewed(self, request, queryset):
        count = queryset.update(is_reviewed=True)
        self.message_user(request, f'Рассмотрено жалоб: {count}')

    @admin.action(description='🔒 Заблокировать нарушителей')
    def block_reported_users(self, request, queryset):
        user_ids = queryset.values_list('against_user_id', flat=True).distinct()
        count = TelegramUser.objects.filter(id__in=user_ids).update(is_blocked=True)
        queryset.update(is_reviewed=True)
        self.message_user(request, f'Заблокировано пользователей: {count}')
