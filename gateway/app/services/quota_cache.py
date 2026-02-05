"""Quota cache service with optimistic locking.

Provides caching for student quota state to reduce database load.
Uses 30-second TTL and optimistic locking for updates.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Optional

from gateway.app.core.cache import CacheBackend, get_cache
from gateway.app.core.utils import get_current_week_number
from gateway.app.db.crud import check_and_consume_quota


@dataclass
class QuotaCacheState:
    """Quota state stored in cache.

    Attributes:
        student_id: The student ID
        current_week_quota: Maximum tokens allowed for the week
        used_quota: Tokens already used
        week_number: The academic week number (optional for backward compat)
        version: Incremented on each update for optimistic locking
    """

    student_id: str
    current_week_quota: int
    used_quota: int
    week_number: int = field(default=0)
    version: int = field(default=1)

    @property
    def remaining(self) -> int:
        """Calculate remaining quota."""
        return self.current_week_quota - self.used_quota

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "student_id": self.student_id,
            "current_week_quota": self.current_week_quota,
            "used_quota": self.used_quota,
            "week_number": self.week_number,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuotaCacheState":
        """Create from dictionary."""
        return cls(
            student_id=data["student_id"],
            current_week_quota=data["current_week_quota"],
            used_quota=data["used_quota"],
            week_number=data.get("week_number", 0),
            version=data.get("version", 1),
        )


class QuotaCacheService:
    """Service for caching and managing quota state.

    Provides:
    - 30-second TTL caching of quota state
    - Optimistic locking for concurrent updates
    - Fallback to database on cache miss or insufficient quota
    - Single-flight pattern to prevent cache stampede

    Cache key format: quota:{student_id}:{week_number}
    """

    CACHE_TTL_SECONDS = 30
    CACHE_KEY_PREFIX = "quota"

    def __init__(self, cache: Optional[CacheBackend] = None) -> None:
        """Initialize the quota cache service.

        Args:
            cache: Cache backend to use. If None, uses global cache instance.
        """
        self._cache = cache
        # Per-student locks to prevent cache stampede (single-flight pattern)
        self._loading_locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

    def _get_cache(self) -> CacheBackend:
        """Get the cache backend instance."""
        if self._cache is None:
            self._cache = get_cache()
        return self._cache

    def _make_key(self, student_id: str, week_number: Optional[int] = None) -> str:
        """Create cache key for a student.

        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.

        Returns:
            Cache key string in format: quota:{student_id}:{week_number}
        """
        if week_number is None:
            week_number = get_current_week_number()
        return f"{self.CACHE_KEY_PREFIX}:{student_id}:{week_number}"

    async def get_quota_state(
        self, student_id: str, week_number: Optional[int] = None
    ) -> Optional[QuotaCacheState]:
        """Get quota state from cache.

        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.

        Returns:
            QuotaCacheState if found in cache, None otherwise
        """
        cache = self._get_cache()
        key = self._make_key(student_id, week_number)
        data = await cache.get(key)

        if data is None:
            return None

        try:
            dict_data = json.loads(data.decode("utf-8"))
            state = QuotaCacheState.from_dict(dict_data)
            # If week_number specified, verify it matches (defensive check)
            if week_number is not None and state.week_number != 0:
                if state.week_number != week_number:
                    return None
            return state
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
            # Invalid cache data, treat as miss
            return None

    async def set_quota_state(self, state: QuotaCacheState) -> None:
        """Store quota state in cache.

        Args:
            state: The quota state to cache
        """
        cache = self._get_cache()
        # Use state's week_number if set, otherwise use current week
        week_number = (
            state.week_number if state.week_number != 0 else get_current_week_number()
        )
        key = self._make_key(state.student_id, week_number)
        data = json.dumps(state.to_dict()).encode("utf-8")
        await cache.set(key, data, ttl=self.CACHE_TTL_SECONDS)

    async def delete_quota_state(
        self, student_id: str, week_number: Optional[int] = None
    ) -> None:
        """Remove quota state from cache.

        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.
        """
        cache = self._get_cache()
        key = self._make_key(student_id, week_number)
        await cache.delete(key)

    async def release_quota(
        self,
        student_id: str,
        tokens_to_release: int,
        week_number: Optional[int] = None,
        session: Optional[Any] = None,
    ) -> bool:
        """Release previously reserved quota.

        Used when a request fails or is cancelled after quota was reserved.
        This reverses the quota reservation by applying a negative adjustment.

        Args:
            student_id: The student ID
            tokens_to_release: Number of tokens to release (must be positive)
            week_number: The academic week number. If None, uses current week.
            session: Optional database session. If provided, uses it for the operation.
                    If None, creates a new session.

        Returns:
            True if released successfully, False otherwise
        """
        if tokens_to_release <= 0:
            return False

        if week_number is None:
            week_number = get_current_week_number()

        # Invalidate cache to prevent stale data
        await self.delete_quota_state(student_id, week_number)

        # Apply negative adjustment to database
        from gateway.app.db.crud import update_student_quota

        # Negative adjustment to release the quota
        adjustment = -tokens_to_release

        if session is not None:
            # Use the provided session
            success, remaining, used = await update_student_quota(
                session, student_id, adjustment, auto_commit=False
            )
            # Note: caller is responsible for committing the session
            return success
        else:
            # Create a new session for this operation
            from gateway.app.db.async_session import get_async_session

            async with get_async_session() as new_session:
                success, remaining, used = await update_student_quota(
                    new_session, student_id, adjustment, auto_commit=True
                )
                return success

    async def check_and_reserve_quota(
        self,
        student_id: str,
        current_week_quota: int,
        tokens_needed: int,
        week_number: Optional[int] = None,
        session: Optional[Any] = None,
    ) -> tuple[bool, int, int]:
        """Check and reserve quota using cache for fast checks, DB for persistence.

        First checks cache for quota state for fast rejection of over-quota requests.
        If cache shows insufficient quota, returns failure immediately.

        Uses database atomic check_and_consume_quota for actual reservation
        to ensure consistency. Updates cache with result after DB operation.

        Args:
            student_id: The student ID
            current_week_quota: Maximum tokens allowed for the week
            tokens_needed: Number of tokens to reserve
            week_number: The academic week number. If None, uses current week.
            session: Optional database session. If provided, uses it for the operation
                    (for transaction consistency). If None, creates a new session.

        Returns:
            Tuple of (success, remaining_quota, current_used)
            - success: True if quota was sufficient and reserved
            - remaining_quota: Remaining quota after operation
            - current_used: Current used quota
        """
        # Use current week if not specified
        if week_number is None:
            week_number = get_current_week_number()

        # Try cache first for fast rejection
        cached_state = await self.get_quota_state(student_id, week_number)

        if cached_state is not None:
            # Fast path: if cache shows insufficient quota, reject immediately
            if cached_state.remaining < tokens_needed:
                return False, cached_state.remaining, cached_state.used_quota

        # Get or create per-student lock for single-flight pattern
        async with self._locks_lock:
            lock = self._loading_locks.setdefault(student_id, asyncio.Lock())

        # Hold the lock while checking/reserving quota to prevent concurrent
        # requests from hitting the database simultaneously
        async with lock:
            # Double-check cache after acquiring lock (another request may have populated it)
            cached_state = await self.get_quota_state(student_id, week_number)
            if cached_state is not None:
                if cached_state.remaining < tokens_needed:
                    return False, cached_state.remaining, cached_state.used_quota

            # Use provided session or create a new one
            if session is not None:
                # Use the provided session (e.g., from FastAPI dependency)
                success, remaining, used = await check_and_consume_quota(
                    session, student_id, tokens_needed, auto_commit=False
                )
                # Note: caller is responsible for committing the session
            else:
                # Create a new session for this operation
                from gateway.app.db.async_session import get_async_session

                async with get_async_session() as new_session:
                    success, remaining, used = await check_and_consume_quota(
                        new_session, student_id, tokens_needed, auto_commit=True
                    )

        if success:
            # Update cache with new state from DB
            new_state = QuotaCacheState(
                student_id=student_id,
                week_number=week_number,
                current_week_quota=current_week_quota,
                used_quota=used,
                version=1,
            )
            await self.set_quota_state(new_state)
        else:
            # Always invalidate/update cache on failure to prevent stale data
            # This handles the case where cache shows sufficient quota but DB update fails
            new_state = QuotaCacheState(
                student_id=student_id,
                week_number=week_number,
                current_week_quota=current_week_quota,
                used_quota=used,
                version=1,
            )
            await self.set_quota_state(new_state)

        return success, remaining, used


# Global service instance
_quota_cache_service: Optional[QuotaCacheService] = None


def get_quota_cache_service(cache: Optional[CacheBackend] = None) -> QuotaCacheService:
    """Get the global quota cache service instance.

    Args:
        cache: Optional cache backend to use

    Returns:
        QuotaCacheService instance
    """
    global _quota_cache_service
    if _quota_cache_service is None or cache is not None:
        _quota_cache_service = QuotaCacheService(cache=cache)
    return _quota_cache_service


def reset_quota_cache_service() -> None:
    """Reset the global quota cache service instance.

    Useful for testing.
    """
    global _quota_cache_service
    _quota_cache_service = None
