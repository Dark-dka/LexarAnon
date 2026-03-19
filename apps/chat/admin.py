from django.contrib import admin
from django.utils.html import format_html

from .models import ChatSession, Message, MediaFile


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['sender', 'message_type', 'text', 'media_preview', 'telegram_file_id', 'created_at']
    fields = ['sender', 'message_type', 'text', 'media_preview', 'created_at']
    can_delete = False
    show_change_link = True

    @admin.display(description='Медиа')
    def media_preview(self, obj):
        if obj.file:
            if obj.message_type == Message.MessageType.PHOTO:
                return format_html(
                    '<img src="{}" style="max-width:120px;max-height:120px;border-radius:4px;" />',
                    obj.file.url,
                )
            return format_html(
                '<a href="{}" target="_blank">📎 {}</a>',
                obj.file.url,
                obj.get_message_type_display(),
            )
        return '—'


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user1_display',
        'user2_display',
        'status',
        'message_count',
        'created_at',
        'ended_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = [
        'user1__username', 'user1__telegram_id',
        'user2__username', 'user2__telegram_id',
    ]
    readonly_fields = ['created_at', 'ended_at']
    list_per_page = 50
    inlines = [MessageInline]

    @admin.display(description='Пользователь 1', ordering='user1')
    def user1_display(self, obj):
        return obj.user1.display_name

    @admin.display(description='Пользователь 2', ordering='user2')
    def user2_display(self, obj):
        return obj.user2.display_name

    @admin.display(description='Сообщений')
    def message_count(self, obj):
        return obj.messages.count()


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'chat_session',
        'sender',
        'message_type',
        'text_preview',
        'has_media',
        'created_at',
    ]
    list_filter = ['message_type', 'created_at']
    search_fields = [
        'text',
        'sender__username',
        'sender__telegram_id',
    ]
    readonly_fields = ['chat_session', 'sender', 'message_type', 'text', 'file', 'telegram_file_id', 'created_at']
    list_per_page = 100
    date_hierarchy = 'created_at'

    @admin.display(description='Текст')
    def text_preview(self, obj):
        if obj.text:
            return obj.text[:80] + ('...' if len(obj.text) > 80 else '')
        return '—'

    @admin.display(description='Файл', boolean=True)
    def has_media(self, obj):
        return bool(obj.file)


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    """Dedicated admin page for all media files."""

    list_display = [
        'id',
        'media_thumbnail',
        'message_type',
        'sender',
        'chat_session',
        'file_size',
        'created_at',
    ]
    list_filter = ['message_type', 'created_at']
    search_fields = [
        'sender__username',
        'sender__telegram_id',
        'chat_session__id',
    ]
    readonly_fields = [
        'chat_session',
        'sender',
        'message_type',
        'text',
        'file',
        'media_preview_full',
        'telegram_file_id',
        'created_at',
    ]
    list_per_page = 50
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Информация', {
            'fields': ('chat_session', 'sender', 'message_type', 'created_at'),
        }),
        ('Медиа файл', {
            'fields': ('file', 'media_preview_full', 'telegram_file_id'),
        }),
        ('Подпись', {
            'fields': ('text',),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return MediaFile.objects.select_related('sender', 'chat_session')

    @admin.display(description='Превью')
    def media_thumbnail(self, obj):
        if obj.file:
            if obj.message_type == Message.MessageType.PHOTO:
                return format_html(
                    '<img src="{}" style="width:80px;height:80px;object-fit:cover;border-radius:6px;" />',
                    obj.file.url,
                )
            elif obj.message_type == Message.MessageType.VIDEO:
                return format_html('🎬 <a href="{}" target="_blank">Видео</a>', obj.file.url)
            elif obj.message_type == Message.MessageType.VIDEO_NOTE:
                return format_html('⚪ <a href="{}" target="_blank">Кружок</a>', obj.file.url)
            elif obj.message_type == Message.MessageType.VOICE:
                return format_html('🎤 <a href="{}" target="_blank">Голосовое</a>', obj.file.url)
            elif obj.message_type == Message.MessageType.DOCUMENT:
                return format_html('📄 <a href="{}" target="_blank">Документ</a>', obj.file.url)
        return '—'

    @admin.display(description='Размер')
    def file_size(self, obj):
        if obj.file:
            try:
                size = obj.file.size
                if size < 1024:
                    return f'{size} B'
                elif size < 1024 * 1024:
                    return f'{size / 1024:.1f} KB'
                else:
                    return f'{size / (1024 * 1024):.1f} MB'
            except Exception:
                return '—'
        return '—'

    @admin.display(description='Превью файла')
    def media_preview_full(self, obj):
        if obj.file:
            if obj.message_type == Message.MessageType.PHOTO:
                return format_html(
                    '<img src="{}" style="max-width:500px;max-height:500px;border-radius:8px;" />',
                    obj.file.url,
                )
            elif obj.message_type in (Message.MessageType.VIDEO, Message.MessageType.VIDEO_NOTE):
                return format_html(
                    '<video controls style="max-width:500px;border-radius:8px;">'
                    '<source src="{}"></video>',
                    obj.file.url,
                )
            elif obj.message_type == Message.MessageType.VOICE:
                return format_html(
                    '<audio controls style="width:100%;max-width:500px;">'
                    '<source src="{}"></audio>',
                    obj.file.url,
                )
            return format_html(
                '<a href="{}" target="_blank" style="font-size:16px;">📎 Скачать файл</a>',
                obj.file.url,
            )
        return 'Нет файла'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
