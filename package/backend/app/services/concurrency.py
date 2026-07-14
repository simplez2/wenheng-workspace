import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.config import settings


ACQUIRE_TIMEOUT = 3600


@dataclass
class ActiveSession:
    started_at: datetime
    user_id: Optional[int]


@dataclass
class QueuedSession:
    session_id: str
    user_id: Optional[int]
    user_limit: Optional[int]
    queued_at: datetime


class ConcurrencyManager:
    """Coordinate global task slots and per-user task slots."""

    def __init__(self, max_concurrent: Optional[int] = None):
        self.max_concurrent = max(1, max_concurrent or settings.MAX_CONCURRENT_USERS)
        self.active_sessions: Dict[str, ActiveSession] = {}
        self.queue: List[QueuedSession] = []
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)

    async def acquire(
        self,
        session_id: str,
        user_id: Optional[int] = None,
        user_limit: Optional[int] = None,
        timeout: float = ACQUIRE_TIMEOUT,
    ) -> bool:
        """Wait until both the global and user task limits allow execution."""
        normalized_limit = max(1, user_limit) if user_id is not None and user_limit else None

        async with self._condition:
            if session_id in self.active_sessions:
                return True

            queued = self._find_queued_locked(session_id)
            if queued is None:
                queued = QueuedSession(
                    session_id=session_id,
                    user_id=user_id,
                    user_limit=normalized_limit,
                    queued_at=datetime.now(timezone.utc),
                )
                self.queue.append(queued)
            else:
                queued.user_id = user_id
                queued.user_limit = normalized_limit

            self._activate_waiting_locked()
            if session_id in self.active_sessions:
                return True

            start_time = datetime.now(timezone.utc)
            while self._find_queued_locked(session_id) is not None:
                remaining = timeout - (datetime.now(timezone.utc) - start_time).total_seconds()
                if remaining <= 0:
                    self._remove_queued_locked(session_id)
                    self._condition.notify_all()
                    return False
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=min(remaining, 60))
                except asyncio.TimeoutError:
                    continue

                if session_id in self.active_sessions:
                    return True

            return session_id in self.active_sessions

    async def release(self, session_id: str):
        async with self._condition:
            self.active_sessions.pop(session_id, None)
            self._remove_queued_locked(session_id)
            self._activate_waiting_locked()
            self._condition.notify_all()

    async def cancel_queued(self, session_id: str) -> bool:
        """Remove a waiting task without releasing an already-running slot."""
        async with self._condition:
            removed = self._remove_queued_locked(session_id)
            if removed:
                self._activate_waiting_locked()
                self._condition.notify_all()
            return removed

    async def get_status(self, session_id: Optional[str] = None) -> Dict:
        async with self._lock:
            queue_ids = [item.session_id for item in self.queue]
            status = {
                "current_users": len(self.active_sessions),
                "max_users": self.max_concurrent,
                "queue_length": len(queue_ids),
                "your_position": None,
                "estimated_wait_time": None,
            }
            if session_id and session_id in queue_ids:
                position = queue_ids.index(session_id) + 1
                status["your_position"] = position
                waves = (position + self.max_concurrent - 1) // self.max_concurrent
                status["estimated_wait_time"] = waves * 300
            return status

    def is_active(self, session_id: str) -> bool:
        return session_id in self.active_sessions

    def get_active_count(self) -> int:
        return len(self.active_sessions)

    async def update_limit(self, new_limit: int):
        async with self._condition:
            self.max_concurrent = max(1, new_limit)
            self._activate_waiting_locked()
            self._condition.notify_all()

    async def update_user_limit(self, user_id: int, new_limit: int):
        async with self._condition:
            normalized = max(1, new_limit)
            for item in self.queue:
                if item.user_id == user_id:
                    item.user_limit = normalized
            self._activate_waiting_locked()
            self._condition.notify_all()

    def _find_queued_locked(self, session_id: str) -> Optional[QueuedSession]:
        return next((item for item in self.queue if item.session_id == session_id), None)

    def _remove_queued_locked(self, session_id: str) -> bool:
        for index, item in enumerate(self.queue):
            if item.session_id == session_id:
                self.queue.pop(index)
                return True
        return False

    def _active_for_user_locked(self, user_id: Optional[int]) -> int:
        if user_id is None:
            return 0
        return sum(1 for item in self.active_sessions.values() if item.user_id == user_id)

    def _can_activate_locked(self, item: QueuedSession) -> bool:
        if len(self.active_sessions) >= self.max_concurrent:
            return False
        if item.user_id is None or item.user_limit is None:
            return True
        return self._active_for_user_locked(item.user_id) < item.user_limit

    def _activate_waiting_locked(self):
        while self.queue and len(self.active_sessions) < self.max_concurrent:
            eligible_index = next(
                (index for index, item in enumerate(self.queue) if self._can_activate_locked(item)),
                None,
            )
            if eligible_index is None:
                break
            item = self.queue.pop(eligible_index)
            self.active_sessions[item.session_id] = ActiveSession(
                started_at=datetime.now(timezone.utc),
                user_id=item.user_id,
            )


concurrency_manager = ConcurrencyManager()


class DynamicConcurrencyLimiter:
    """Hot-reloadable limiter for outbound AI requests."""

    def __init__(self, limit: int):
        self.limit = max(1, limit)
        self.active = 0
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def slot(self):
        async with self._condition:
            while self.active >= self.limit:
                await self._condition.wait()
            self.active += 1
        try:
            yield
        finally:
            async with self._condition:
                self.active -= 1
                self._condition.notify_all()

    async def update_limit(self, new_limit: int):
        async with self._condition:
            self.limit = max(1, new_limit)
            self._condition.notify_all()


ai_request_limiter = DynamicConcurrencyLimiter(settings.MAX_CONCURRENT_AI_REQUESTS)
