"""
Matchmaking service: manages the queue of users looking for a chat partner.
Matching is fully random — first available user in queue is paired.
Includes cooldown: same pair won't match within 10 min or last 5 chats.
"""
import asyncio
import logging
import time
from typing import Optional
from asgiref.sync import sync_to_async

from apps.users.models import TelegramUser
from apps.chat.models import ChatSession

logger = logging.getLogger(__name__)

# Cooldown settings
COOLDOWN_SECONDS = 600      # 10 minutes
COOLDOWN_CHAT_COUNT = 5     # must have 5 other chats before re-matching


class MatchmakingService:
    """Thread-safe matchmaking queue — random pairing with cooldown."""

    def __init__(self):
        self._queue: list[int] = []          # telegram_ids waiting
        self._lock = asyncio.Lock()
        self._active_chats: dict[int, int] = {}  # telegram_id -> chat_session_id
        # Recent partners: {user_tid: [(partner_tid, timestamp), ...]}
        self._recent_pairs: dict[int, list[tuple[int, float]]] = {}

    def _is_on_cooldown(self, user_tid: int, partner_tid: int) -> bool:
        """Check if this pair is on cooldown."""
        history = self._recent_pairs.get(user_tid, [])
        now = time.time()
        for i, (ptid, ts) in enumerate(history):
            if ptid == partner_tid:
                # Check time cooldown (10 min)
                if now - ts < COOLDOWN_SECONDS:
                    return True
                # Check chat count cooldown (must have 5 others in between)
                if i < COOLDOWN_CHAT_COUNT:
                    return True
                return False
        return False

    def _record_pair(self, user_tid: int, partner_tid: int):
        """Record a new pairing in history for both users."""
        now = time.time()
        for tid, ptid in [(user_tid, partner_tid), (partner_tid, user_tid)]:
            history = self._recent_pairs.setdefault(tid, [])
            # Insert at beginning (most recent first)
            history.insert(0, (ptid, now))
            # Keep only last 20 entries to avoid memory bloat
            if len(history) > 20:
                self._recent_pairs[tid] = history[:20]

    async def _get_user(self, telegram_id: int) -> TelegramUser:
        return await sync_to_async(TelegramUser.objects.get)(telegram_id=telegram_id)

    async def add_to_queue(self, telegram_id: int) -> Optional[tuple[TelegramUser, ChatSession]]:
        """
        Add user to queue. If anyone is waiting, pair them immediately.
        Returns (partner_user, chat_session) if matched, None if queued.
        Skips partners on cooldown.
        """
        partner_tid: Optional[int] = None
        partner_index: int = -1

        async with self._lock:
            if telegram_id in self._queue or telegram_id in self._active_chats:
                return None

            if self._queue:
                # Find first partner NOT on cooldown
                for idx, candidate_tid in enumerate(self._queue):
                    if not self._is_on_cooldown(telegram_id, candidate_tid):
                        partner_tid = candidate_tid
                        partner_index = idx
                        break

                if partner_tid is None and self._queue:
                    # All in queue are on cooldown — pick the oldest pairing
                    # (least recently matched = best option)
                    best_idx = 0
                    best_age = 0
                    now = time.time()
                    for idx, candidate_tid in enumerate(self._queue):
                        history = self._recent_pairs.get(telegram_id, [])
                        age = COOLDOWN_SECONDS  # default if no history
                        for ptid, ts in history:
                            if ptid == candidate_tid:
                                age = now - ts
                                break
                        if age > best_age:
                            best_age = age
                            best_idx = idx
                    partner_tid = self._queue[best_idx]
                    partner_index = best_idx

                if partner_tid is not None:
                    self._queue.pop(partner_index)
                    self._record_pair(telegram_id, partner_tid)
                else:
                    self._queue.append(telegram_id)
                    logger.info(f'User {telegram_id} added to queue. Queue size: {len(self._queue)}')
                    return None
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

