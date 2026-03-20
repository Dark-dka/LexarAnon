"""
Bot entry point.
Initializes Django ORM, sets up aiogram Bot + Dispatcher, runs polling.
"""
import os
import sys
import logging
import asyncio

# ── Django setup ─────────────────────────────────────────────────────────
# Must happen before any Django model import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

import django
django.setup()

# ── Imports after Django setup ───────────────────────────────────────────
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.config import BOT_TOKEN
from bot.handlers import start, search, chat, report
from bot.middlewares.throttle import ThrottleMiddleware
from bot.middlewares.subscription import SubscriptionMiddleware

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        logger.error('TELEGRAM_BOT_TOKEN is not set! Check your .env file.')
        sys.exit(1)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Register throttle middleware
    dp.message.middleware(ThrottleMiddleware())

    # Register subscription middleware (runs after throttle)
    sub_mw = SubscriptionMiddleware()
    dp.message.middleware(sub_mw)
    dp.callback_query.middleware(sub_mw)

    # Register routers (order matters — buttons before text relay)
    dp.include_router(start.router)
    dp.include_router(search.router)
    dp.include_router(report.router)
    dp.include_router(chat.router)  # must be last (catches all text)

    logger.info('🚀 Bot is starting...')

    # Drop pending updates and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
