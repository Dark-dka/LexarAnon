from django.db import models


class TelegramUser(models.Model):
    """Telegram user who interacts with the bot."""

    class Gender(models.TextChoices):
        MALE = 'male', '👦 Парень'
        FEMALE = 'female', '👧 Девушка'

    telegram_id = models.BigIntegerField(
        unique=True,
        verbose_name='Telegram ID',
        db_index=True,
    )
    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Username',
    )
    first_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Имя',
    )
    last_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Фамилия',
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
        verbose_name='Пол',
    )
    search_gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
        verbose_name='Ищу пол',
        help_text='Какой пол ищет пользователь (null = любой)',
    )
    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True,
        verbose_name='Фото профиля',
    )
    language_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name='Язык',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
    )
    is_blocked = models.BooleanField(
        default=False,
        verbose_name='Заблокирован',
        help_text='Заблокированные пользователи не могут использовать бота',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Последнее обновление',
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']

    def __str__(self):
        if self.username:
            return f'@{self.username} ({self.telegram_id})'
        name = self.first_name or ''
        if self.last_name:
            name += f' {self.last_name}'
        return f'{name.strip() or "Unknown"} ({self.telegram_id})'

    @property
    def display_name(self):
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        if parts:
            return ' '.join(parts)
        if self.username:
            return f'@{self.username}'
        return str(self.telegram_id)

    @property
    def gender_emoji(self):
        if self.gender == self.Gender.MALE:
            return '👦'
        elif self.gender == self.Gender.FEMALE:
            return '👧'
        return '❓'


class Rating(models.Model):
    """Like / Dislike after chat session."""

    from_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='ratings_given',
        verbose_name='От кого',
    )
    to_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='ratings_received',
        verbose_name='Кому',
    )
    is_like = models.BooleanField(
        verbose_name='Лайк',
        help_text='True = 👍, False = 👎',
    )
    chat_session = models.ForeignKey(
        'chat.ChatSession',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='ratings',
        verbose_name='Чат-сессия',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата',
    )

    class Meta:
        verbose_name = 'Оценка'
        verbose_name_plural = 'Оценки'
        ordering = ['-created_at']
        unique_together = ['from_user', 'to_user', 'chat_session']

    def __str__(self):
        emoji = '👍' if self.is_like else '👎'
        return f'{emoji} {self.from_user} → {self.to_user}'


class RequiredChannel(models.Model):
    """A Telegram channel that users must subscribe to in order to use the bot."""

    title = models.CharField(
        max_length=255,
        verbose_name='Название канала',
    )
    channel_username = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Username канала',
        help_text='Например: @mychannel (с @)',
    )
    invite_link = models.URLField(
        verbose_name='Ссылка на канал',
        help_text='https://t.me/mychannel или приватная ссылка',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Неактивные каналы не проверяются',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления',
    )

    class Meta:
        verbose_name = 'Обязательный канал'
        verbose_name_plural = 'Обязательные каналы'
        ordering = ['title']

    def __str__(self):
        return f'{self.title} ({self.channel_username})'


class ChannelSubscriptionEvent(models.Model):
    """
    Recorded every time a user successfully passes the subscription check
    for a required channel. Stores channel data as strings so the history
    is preserved even after the channel is removed from RequiredChannel.
    """

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='subscription_events',
        verbose_name='Пользователь',
    )
    channel_username = models.CharField(
        max_length=255,
        verbose_name='Username канала',
        db_index=True,
    )
    channel_title = models.CharField(
        max_length=255,
        verbose_name='Название канала',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата подписки',
        db_index=True,
    )

    class Meta:
        verbose_name = 'Событие подписки'
        verbose_name_plural = 'Статистика подписок'
        ordering = ['-created_at']
        # One entry per user per channel (upsert via get_or_create)
        unique_together = ['user', 'channel_username']

    def __str__(self):
        return f'{self.user} → {self.channel_title} ({self.channel_username})'

