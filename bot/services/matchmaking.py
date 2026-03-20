"""
Matchmaking service: manages the queue of users looking for a chat partner.
Matching is fully random — first available user in queue is paired.
"""
import asyncio
import logging
from typing import Optional
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from apps.chat.models import ChatSession

logger = logging.getLogger(__name__)


class MatchmakingService:
    """Thread-safe matchmaking queue — random pairing, no gender filtering."""

    def __init__(self):
        self._queue: list[int] = []          # telegram_ids waiting
        self._lock = asyncio.Lock()
        self._active_chats: dict[int, int] = {}  # telegram_id -> chat_session_id

    async def _get_user(self, telegram_id: int) -> TelegramUser:
        return await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)

    async def add_to_queue(self, telegram_id: int) -> Optional[tuple[TelegramUser, ChatSession]]:
        """
        Add user to queue. If anyone is waiting, pair them immediately.
        Returns (partner_user, chat_session) if matched, None if queued.

        DB operations are done OUTSIDE the lock to avoid blocking remove_from_queue.
        """
        partner_tid: Optional[int] = None
        async with self._lock:
            if telegram_id in self._queue or telegram_id in self._active_chats:
                return None

            if self._queue:
                # Take the first user waiting — fully random
                partner_tid = self._queue.pop(0)
            else:
                self._queue.append(telegram_id)
                logger.info(f'User {telegram_id} added to queue. Queue size: {len(self._queue)}')
                return None

        # --- Outside lock: DB-heavy operations ---
        assert partner_tid is not None
        user1 = await self._get_user(partner_tid)
        user2 = await self._get_user(telegram_id)

        session = await sync_to_async(ChatSession.objects.create)(
            user1=user1,
            user2=user2,
            status=ChatSession.Status.ACTIVE,
        )

        async with self._lock:
            self._active_chats[partner_tid] = session.id
            self._active_chats[telegram_id] = session.id

        logger.info(
            f'Matched {partner_tid} and {telegram_id} in session {session.id}'
        )
        return (user1, session)

    async def remove_from_queue(self, telegram_id: int) -> bool:
        """Remove user from the waiting queue."""
        async with self._lock:
            if telegram_id in self._queue:
                self._queue.remove(telegram_id)
                logger.info(f'User {telegram_id} removed from queue.')
                return True
            return False

    async def get_active_session(self, telegram_id: int) -> Optional[ChatSession]:
        """Get the active chat session for a user."""
        session_id = self._active_chats.get(telegram_id)
        if session_id:
            try:
                session = await sync_to_async(
                    ChatSession.objects.select_related('user1', 'user2').get
                )(id=session_id, status=ChatSession.Status.ACTIVE)
                return session
            except ChatSession.DoesNotExist:
                self._active_chats.pop(telegram_id, None)
                return None
        return None

    async def get_partner_telegram_id(self, telegram_id: int) -> Optional[int]:
        """Get the partner's telegram_id from the active session."""
        session = await self.get_active_session(telegram_id)
        if session:
            user1_tid = await sync_to_async(lambda: session.user1.telegram_id)()
            user2_tid = await sync_to_async(lambda: session.user2.telegram_id)()
            if user1_tid == telegram_id:
                return user2_tid
            return user1_tid
        return None

    async def end_session(self, telegram_id: int) -> Optional[tuple[int, ChatSession]]:
        """
        End the active session for a user.
        Returns (partner_telegram_id, session) or None.
        """
        async with self._lock:
            session_id = self._active_chats.get(telegram_id)
            if not session_id:
                return None

            try:
                session = await sync_to_async(
                    ChatSession.objects.select_related('user1', 'user2').get
                )(id=session_id)
            except ChatSession.DoesNotExist:
                self._active_chats.pop(telegram_id, None)
                return None

            from django.utils import timezone
            session.status = ChatSession.Status.CLOSED
            session.ended_at = timezone.now()
            await sync_to_async(session.save)()

            user1_tid = await sync_to_async(lambda: session.user1.telegram_id)()
            user2_tid = await sync_to_async(lambda: session.user2.telegram_id)()
            partner_tid = user2_tid if user1_tid == telegram_id else user1_tid

            self._active_chats.pop(telegram_id, None)
            self._active_chats.pop(partner_tid, None)

            logger.info(f'Session {session_id} ended by {telegram_id}')
            return (partner_tid, session)

    def is_in_queue(self, telegram_id: int) -> bool:
        return telegram_id in self._queue

    def is_in_chat(self, telegram_id: int) -> bool:
        return telegram_id in self._active_chats

    @property
    def queue_size(self) -> int:
        return len(self._queue)


# Singleton instance
matchmaking = MatchmakingService()

