"""
Funnel analytics: every meaningful user action is recorded as a UserEvent.
"""
from django.db import models


class EventType(models.TextChoices):
    # ── Onboarding ───────────────────────────────────────────────────
    START_OPENED = 'start_opened', '/start открыт'
    GENDER_SELECTION_SHOWN = 'gender_selection_shown', 'Выбор пола показан'
    GENDER_SELECTED = 'gender_selected', 'Пол выбран'

    # ── Required channels ────────────────────────────────────────────
    REQUIRED_CHANNELS_SHOWN = 'required_channels_shown', 'Каналы показаны'
    SUBSCRIPTION_CHECK_CLICKED = 'subscription_check_clicked', 'Проверка подписки'
    REQUIRED_CHANNELS_PASSED = 'required_channels_passed', 'Каналы пройдены'

    # ── Required bots ────────────────────────────────────────────────
    REQUIRED_BOTS_SHOWN = 'required_bots_shown', 'Боты показаны'
    REQUIRED_BOT_CONFIRMED = 'required_bot_confirmed', 'Бот подтверждён'
    REQUIRED_BOTS_PASSED = 'required_bots_passed', 'Боты пройдены'

    # ── Core funnel ──────────────────────────────────────────────────
    MAIN_MENU_SHOWN = 'main_menu_shown', 'Главное меню показано'
    SEARCH_STARTED = 'search_started', 'Поиск начат'
    SEARCH_CANCELLED = 'search_cancelled', 'Поиск отменён'
    MATCH_FOUND = 'match_found', 'Пара найдена'
    CHAT_STARTED = 'chat_started', 'Чат начат'
    MESSAGE_SENT = 'message_sent', 'Сообщение отправлено'
    CHAT_FINISHED = 'chat_finished', 'Чат завершён'
    PARTNER_LEFT = 'partner_left', 'Собеседник ушёл'
    PARTNER_RATED = 'partner_rated', 'Собеседник оценён'
    NEXT_SEARCH_STARTED = 'next_search_started', 'Следующий поиск'
    REPORT_SENT = 'report_sent', 'Жалоба отправлена'

    # ── Engagement ───────────────────────────────────────────────────
    PROFILE_OPENED = 'profile_opened', 'Профиль открыт'
    SETTINGS_OPENED = 'settings_opened', 'Настройки открыты'
    HOW_IT_WORKS_OPENED = 'how_it_works_opened', 'Как это работает'


class UserEvent(models.Model):
    """Single analytics event tied to a user."""

    user = models.ForeignKey(
        'users.TelegramUser',
        on_delete=models.CASCADE,
        related_name='events',
        verbose_name='Пользователь',
    )
    event_type = models.CharField(
        max_length=64,
        choices=EventType.choices,
        db_index=True,
        verbose_name='Тип события',
    )
    meta = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Метаданные',
        help_text='Доп. данные: channel_id, session_id, gender и т.д.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Дата',
    )

    class Meta:
        verbose_name = 'Событие'
        verbose_name_plural = 'События'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.user} ({self.created_at:%d.%m %H:%M})'
