"""
Anti-spam throttle middleware.
Limits messages per user per time window.
"""
import time
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot import config, texts

logger = logging.getLogger(__name__)


class ThrottleMiddleware(BaseMiddleware):
    """Rate limiter: max N messages per user per time window."""

    def __init__(
        self,
        max_messages: int = config.RATE_LIMIT_MESSAGES,
        period: int = config.RATE_LIMIT_PERIOD,
    ):
        self.max_messages = max_messages
        self.period = period
        self._user_messages: Dict[int, list[float]] = defaultdict(list)
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        user_id = event.from_user.id
        now = time.time()

        # Clean old timestamps
        self._user_messages[user_id] = [
            ts for ts in self._user_messages[user_id]
            if now - ts < self.period
        ]

        if len(self._user_messages[user_id]) >= self.max_messages:
            logger.warning(f'Rate limit exceeded for user {user_id}')
            await event.answer(texts.RATE_LIMITED)
            return None

        self._user_messages[user_id].append(now)
        return await handler(event, data)
