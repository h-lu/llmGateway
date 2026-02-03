"""Distributed quota management using Redis for multi-instance deployments.

Provides atomic quota operations using Redis INCR/DECR commands, with fallback
to database when Redis is unavailable. Supports periodic sync from Redis to database.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from gateway.app.core.config import settings
from gateway.app.core.utils import get_current_week_number

# Import DB functions - these are re-exported from __init__.py for backward compatibility
# Tests mock these at the package level: gateway.app.services.distributed_quota.xxx
from . import check_and_consume_quota, get_student_by_id, update_student_quota

from .models import DistributedQuotaState
from .redis_lua import CHECK_AND_CONSUME_SCRIPT

logger = logging.getLogger(__name__)


class DistributedQuotaService:
    """Service for distributed quota management using Redis.
    
    Provides:
    - Atomic quota operations using Redis Lua scripts
    - Multi-instance quota sharing
    - Periodic sync from Redis to database (every 60 seconds)
    - Fallback to database when Redis is unavailable
    - Backward compatibility with single-instance mode
    
    Redis key format:
    - quota:used:{student_id}:{week_number} - Current used quota counter
    - quota:meta:{student_id}:{week_number} - Metadata (quota limit, last_sync)
    """
    
    REDIS_KEY_PREFIX_USED = "quota:used"
    REDIS_KEY_PREFIX_META = "quota:meta"
    SYNC_INTERVAL_SECONDS = 60  # Sync to DB every minute
    REDIS_TTL_SECONDS = 86400 * 7  # 7 days TTL for weekly quota data
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        redis_url: Optional[str] = None,
        enable_sync: bool = True,
    ) -> None:
        """Initialize the distributed quota service."""
        self._redis = redis_client
        self._redis_url = redis_url or settings.redis_url
        self._sync_task: Optional[asyncio.Task] = None
        self._enable_sync = enable_sync
        self._sync_interval = self.SYNC_INTERVAL_SECONDS
        self._shutdown_event = asyncio.Event()
        self._pending_syncs: Dict[str, int] = {}
        self._sync_lock = asyncio.Lock()
    
    def _get_redis(self) -> Optional[Any]:
        """Get or create Redis client."""
        if self._redis is not None:
            return self._redis
        if not settings.redis_enabled:
            return None
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url)
            return self._redis
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using database fallback.")
            return None
    
    def _make_used_key(self, student_id: str, week_number: Optional[int] = None) -> str:
        """Create Redis key for used quota counter."""
        if week_number is None:
            week_number = get_current_week_number()
        return f"{self.REDIS_KEY_PREFIX_USED}:{student_id}:{week_number}"
    
    def _make_meta_key(self, student_id: str, week_number: Optional[int] = None) -> str:
        """Create Redis key for quota metadata."""
        if week_number is None:
            week_number = get_current_week_number()
        return f"{self.REDIS_KEY_PREFIX_META}:{student_id}:{week_number}"
    
    async def _get_initial_quota_from_db(
        self, student_id: str, week_number: Optional[int] = None
    ) -> Optional[DistributedQuotaState]:
        """Get initial quota state from database."""
        from gateway.app.db import async_session
        async with async_session.get_async_session() as session:
            student = await get_student_by_id(session, student_id)
            if student is None:
                return None
            if week_number is None:
                week_number = get_current_week_number()
            return DistributedQuotaState(
                student_id=student_id,
                current_week_quota=student.current_week_quota,
                used_quota=student.used_quota,
                week_number=week_number,
                source="db",
            )
    
    async def _init_redis_quota(
        self,
        student_id: str,
        current_week_quota: int,
        initial_used: int,
        week_number: Optional[int] = None,
    ) -> bool:
        """Initialize quota counters in Redis from database values."""
        redis = self._get_redis()
        if redis is None:
            return False
        if week_number is None:
            week_number = get_current_week_number()
        try:
            used_key = self._make_used_key(student_id, week_number)
            meta_key = self._make_meta_key(student_id, week_number)
            existing = await redis.get(used_key)
            if existing is None:
                await redis.setex(used_key, self.REDIS_TTL_SECONDS, str(initial_used))
                meta = {
                    "quota": current_week_quota,
                    "initialized_at": datetime.now().isoformat(),
                    "initial_used": initial_used,
                }
                await redis.setex(meta_key, self.REDIS_TTL_SECONDS, json.dumps(meta))
                logger.debug(f"Initialized Redis quota for {student_id}: {initial_used}/{current_week_quota}")
            return True
        except Exception as e:
            logger.warning(f"Failed to init Redis quota for {student_id}: {e}")
            return False
    
    async def get_quota_state(
        self, student_id: str, week_number: Optional[int] = None
    ) -> Optional[DistributedQuotaState]:
        """Get quota state from Redis or database."""
        if week_number is None:
            week_number = get_current_week_number()
        redis = self._get_redis()
        if redis is not None:
            try:
                used_key = self._make_used_key(student_id, week_number)
                meta_key = self._make_meta_key(student_id, week_number)
                used_val, meta_val = await asyncio.gather(
                    redis.get(used_key),
                    redis.get(meta_key),
                    return_exceptions=True,
                )
                if isinstance(used_val, Exception):
                    raise used_val
                if isinstance(meta_val, Exception):
                    raise meta_val
                if used_val is not None and meta_val is not None:
                    used_quota = int(used_val)
                    meta = json.loads(meta_val)
                    return DistributedQuotaState(
                        student_id=student_id,
                        current_week_quota=meta.get("quota", 0),
                        used_quota=used_quota,
                        week_number=week_number,
                        source="redis",
                    )
            except Exception as e:
                logger.warning(f"Redis get failed for {student_id}: {e}. Falling back to DB.")
        return await self._get_initial_quota_from_db(student_id, week_number)
    
    async def check_and_consume_quota(
        self,
        student_id: str,
        current_week_quota: int,
        tokens_needed: int,
        week_number: Optional[int] = None,
    ) -> tuple[bool, int, int]:
        """Atomically check and consume quota using Redis or database."""
        if week_number is None:
            week_number = get_current_week_number()
        redis = self._get_redis()
        if redis is not None:
            try:
                return await self._check_and_consume_with_redis(
                    student_id, current_week_quota, tokens_needed, week_number
                )
            except Exception as e:
                logger.warning(f"Redis quota check failed for {student_id}: {e}. Falling back to DB.")
        from gateway.app.db import async_session
        async with async_session.get_async_session() as session:
            return await check_and_consume_quota(session, student_id, tokens_needed)
    
    async def _check_and_consume_with_redis(
        self,
        student_id: str,
        current_week_quota: int,
        tokens_needed: int,
        week_number: int,
    ) -> tuple[bool, int, int]:
        """Check and consume quota using Redis Lua script for atomicity."""
        redis = self._get_redis()
        if redis is None:
            raise RuntimeError("Redis not available")
        used_key = self._make_used_key(student_id, week_number)
        meta_key = self._make_meta_key(student_id, week_number)
        try:
            result = await redis.eval(
                CHECK_AND_CONSUME_SCRIPT,
                2,  # Number of keys
                used_key,  # KEYS[1]
                meta_key,  # KEYS[2]
                current_week_quota,  # ARGV[1]
                tokens_needed,  # ARGV[2]
                self.REDIS_TTL_SECONDS,  # ARGV[3]
                str(student_id),  # ARGV[4]
                str(week_number),  # ARGV[5]
                datetime.now().isoformat(),  # ARGV[6]
            )
        except Exception as e:
            logger.error(f"Lua script execution failed: {e}")
            return await self._check_and_consume_fallback(
                student_id, tokens_needed, current_week_quota, week_number
            )
        success = bool(result[0])
        remaining = int(result[1])
        new_used = int(result[2])
        if success:
            async with self._sync_lock:
                self._pending_syncs[student_id] = new_used
        return success, remaining, new_used
    
    async def _check_and_consume_fallback(
        self,
        student_id: str,
        tokens_needed: int,
        current_week_quota: int,
        week_number: int,
    ) -> tuple[bool, int, int]:
        """Fallback method for quota check-and-consume (non-atomic)."""
        redis = self._get_redis()
        if redis is None:
            raise RuntimeError("Redis not available")
        used_key = self._make_used_key(student_id, week_number)
        current_val = await redis.get(used_key)
        if current_val is None:
            current_val = b"0"
        current_used = int(current_val)
        remaining = current_week_quota - current_used
        if remaining < tokens_needed:
            return False, remaining, current_used
        new_val = await redis.incrby(used_key, tokens_needed)
        new_used = int(new_val)
        new_remaining = current_week_quota - new_used
        async with self._sync_lock:
            self._pending_syncs[student_id] = new_used
        return True, new_remaining, new_used
    
    async def release_quota(
        self,
        student_id: str,
        tokens_to_release: int,
        week_number: Optional[int] = None,
    ) -> bool:
        """Release previously reserved quota."""
        if week_number is None:
            week_number = get_current_week_number()
        redis = self._get_redis()
        if redis is not None:
            try:
                used_key = self._make_used_key(student_id, week_number)
                current = await redis.get(used_key)
                if current is None:
                    return False
                current_val = int(current)
                new_val = max(0, current_val - tokens_to_release)
                actual_release = current_val - new_val
                if actual_release > 0:
                    await redis.decrby(used_key, actual_release)
                    async with self._sync_lock:
                        self._pending_syncs[student_id] = new_val
                return True
            except Exception as e:
                logger.warning(f"Failed to release Redis quota for {student_id}: {e}")
        try:
            from gateway.app.db import async_session
            async with async_session.get_async_session() as session:
                student = await get_student_by_id(session, student_id)
                if student:
                    new_used = max(0, student.used_quota - tokens_to_release)
                    adjustment = new_used - student.used_quota
                    if adjustment != 0:
                        await update_student_quota(session, student_id, adjustment)
                    return True
        except Exception as e:
            logger.error(f"Failed to release DB quota for {student_id}: {e}")
        return False
    
    async def start_sync_task(self) -> None:
        """Start the periodic sync task to synchronize Redis state to database."""
        if not self._enable_sync or self._sync_task is not None:
            return
        self._shutdown_event.clear()
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("Started distributed quota sync task")
    
    async def stop_sync_task(self) -> None:
        """Stop the periodic sync task."""
        if self._sync_task is None:
            return
        self._shutdown_event.set()
        try:
            await asyncio.wait_for(self._sync_task, timeout=5.0)
        except asyncio.TimeoutError:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        self._sync_task = None
        logger.info("Stopped distributed quota sync task")
    
    async def _sync_loop(self) -> None:
        """Background loop for periodic sync to database."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._sync_interval,
                )
            except asyncio.TimeoutError:
                pass
            if self._shutdown_event.is_set():
                break
            try:
                await self.sync_to_database()
            except Exception as e:
                logger.error(f"Error during quota sync: {e}")
    
    async def sync_to_database(self) -> int:
        """Synchronize pending quota updates from Redis to database."""
        redis = self._get_redis()
        if redis is None:
            return 0
        async with self._sync_lock:
            pending = dict(self._pending_syncs)
            self._pending_syncs.clear()
        if not pending:
            return 0
        synced_count = 0
        from gateway.app.db import async_session
        async with async_session.get_async_session() as session:
            for student_id, redis_used in pending.items():
                try:
                    student = await get_student_by_id(session, student_id)
                    if student is None:
                        continue
                    db_used = student.used_quota
                    adjustment = redis_used - db_used
                    if adjustment != 0:
                        await update_student_quota(session, student_id, adjustment)
                        synced_count += 1
                        logger.debug(
                            f"Synced quota for {student_id}: DB {db_used} -> {redis_used} "
                            f"(adjustment: {adjustment:+d})"
                        )
                except Exception as e:
                    logger.error(f"Failed to sync quota for {student_id}: {e}")
                    async with self._sync_lock:
                        if student_id not in self._pending_syncs:
                            self._pending_syncs[student_id] = redis_used
        if synced_count > 0:
            logger.info(f"Synced quota for {synced_count} students to database")
        return synced_count
    
    async def get_multi_instance_quota(
        self, student_id: str, week_number: Optional[int] = None
    ) -> Optional[DistributedQuotaState]:
        """Get quota state optimized for multi-instance deployments."""
        state = await self.get_quota_state(student_id, week_number)
        if state is not None and state.source == "redis":
            return state
        if state is not None and state.source == "db":
            redis = self._get_redis()
            if redis is not None:
                await self._init_redis_quota(
                    student_id,
                    state.current_week_quota,
                    state.used_quota,
                    week_number,
                )
        return state
    
    async def close(self) -> None:
        """Close the service and cleanup resources."""
        await self.stop_sync_task()
        if self._redis is not None:
            try:
                await self._redis.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            self._redis = None


_distributed_quota_service: Optional[DistributedQuotaService] = None


def get_distributed_quota_service(
    redis_client: Optional[Any] = None,
    redis_url: Optional[str] = None,
    enable_sync: bool = True,
) -> DistributedQuotaService:
    """Get the global distributed quota service instance."""
    global _distributed_quota_service
    if _distributed_quota_service is None:
        _distributed_quota_service = DistributedQuotaService(
            redis_client=redis_client,
            redis_url=redis_url,
            enable_sync=enable_sync,
        )
    return _distributed_quota_service


def reset_distributed_quota_service() -> None:
    """Reset the global distributed quota service instance."""
    global _distributed_quota_service
    _distributed_quota_service = None
