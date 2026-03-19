from django.db import models
from apps.users.models import TelegramUser
from apps.chat.models import ChatSession


class Report(models.Model):
    """User report / complaint."""

    from_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='reports_sent',
        verbose_name='Кто пожаловался',
    )
    against_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='reports_received',
        verbose_name='На кого жалоба',
    )
    chat_session = models.ForeignKey(
        ChatSession,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reports',
        verbose_name='Чат-сессия',
    )
    reason = models.TextField(
        verbose_name='Причина',
        help_text='Описание жалобы',
    )
    is_reviewed = models.BooleanField(
        default=False,
        verbose_name='Рассмотрена',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата жалобы',
    )

    class Meta:
        verbose_name = 'Жалоба'
        verbose_name_plural = 'Жалобы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Жалоба от {self.from_user} на {self.against_user}'
