"""
Bot configuration loaded from environment.
"""
import os
from decouple import config


# Telegram
BOT_TOKEN = config('TELEGRAM_BOT_TOKEN', default='')
BOT_USERNAME = config('BOT_USERNAME', default='')
WEBHOOK_URL = config('WEBHOOK_URL', default='')

# Rate limiting
RATE_LIMIT_MESSAGES = 30  # max messages
RATE_LIMIT_PERIOD = 60    # per N seconds

# Django settings module
DJANGO_SETTINGS_MODULE = config('DJANGO_SETTINGS_MODULE', default='config.settings.dev')
