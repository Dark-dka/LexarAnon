from django.db import models
from apps.users.models import TelegramUser


class ChatSession(models.Model):
    """Anonymous chat session between two users."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активен'
        CLOSED = 'closed', 'Завершён'

    user1 = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='sessions_as_user1',
        verbose_name='Пользователь 1',
    )
    user2 = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='sessions_as_user2',
        verbose_name='Пользователь 2',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name='Статус',
        db_index=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Начало сессии',
    )
    ended_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Конец сессии',
    )

    class Meta:
        verbose_name = 'Чат-сессия'
        verbose_name_plural = 'Чат-сессии'
        ordering = ['-created_at']

    def __str__(self):
        return f'Чат #{self.pk}: {self.user1} ↔ {self.user2} [{self.get_status_display()}]'

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Message(models.Model):
    """A single message in a chat session."""

    class MessageType(models.TextChoices):
        TEXT = 'text', 'Текст'
        PHOTO = 'photo', 'Фото'
        VIDEO = 'video', 'Видео'
        VOICE = 'voice', 'Голосовое'
        DOCUMENT = 'document', 'Документ'
        STICKER = 'sticker', 'Стикер'
        VIDEO_NOTE = 'video_note', 'Видеосообщение'

    chat_session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Чат-сессия',
    )
    sender = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Отправитель',
    )
    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT,
        verbose_name='Тип сообщения',
    )
    text = models.TextField(
        blank=True,
        null=True,
        verbose_name='Текст',
    )
    file = models.FileField(
        upload_to='chat_media/%Y/%m/%d/',
        blank=True,
        null=True,
        verbose_name='Файл',
    )
    telegram_file_id = models.CharField(
        max_length=512,
        blank=True,
        null=True,
        verbose_name='Telegram File ID',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата отправки',
        db_index=True,
    )

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        preview = ''
        if self.text:
            preview = self.text[:50]
        else:
            preview = self.get_message_type_display()
        return f'[{self.get_message_type_display()}] {self.sender} → {preview}'


class MediaFileManager(models.Manager):
    """Manager that returns only messages with files."""
    def get_queryset(self):
        return super().get_queryset().exclude(
            message_type=Message.MessageType.TEXT,
        ).exclude(
            message_type=Message.MessageType.STICKER,
        ).filter(
            file__isnull=False,
        ).exclude(file='')


class MediaFile(Message):
    """Proxy model for media messages — separate admin page."""
    objects = MediaFileManager()

    class Meta:
        proxy = True
        verbose_name = 'Медиа файл'
        verbose_name_plural = '📁 Медиа файлы'
