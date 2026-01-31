"""Distributed quota management using Redis for multi-instance deployments.

Provides atomic quota operations using Redis INCR/DECR commands, with fallback
to database when Redis is unavailable. Supports periodic sync from Redis to database.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from gateway.app.core.config import settings
from gateway.app.core.utils import get_current_week_number
from gateway.app.db.crud import check_and_consume_quota, update_student_quota, get_student_by_id

logger = logging.getLogger(__name__)


@dataclass
class DistributedQuotaState:
    """Quota state for distributed quota management.
    
    Attributes:
        student_id: The student ID
        current_week_quota: Maximum tokens allowed for the week
        used_quota: Tokens already used (from Redis or DB)
        week_number: The academic week number
        source: Where the data came from ('redis', 'db', or 'cache')
    """
    student_id: str
    current_week_quota: int
    used_quota: int
    week_number: int = field(default=0)
    source: str = field(default="db")
    
    @property
    def remaining(self) -> int:
        """Calculate remaining quota."""
        return self.current_week_quota - self.used_quota
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "student_id": self.student_id,
            "current_week_quota": self.current_week_quota,
            "used_quota": self.used_quota,
            "week_number": self.week_number,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DistributedQuotaState":
        """Create from dictionary."""
        return cls(
            student_id=data["student_id"],
            current_week_quota=data["current_week_quota"],
            used_quota=data["used_quota"],
            week_number=data.get("week_number", 0),
            source=data.get("source", "db"),
        )


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
    
    # Lua script for atomic check-and-consume operation
    # This prevents TOCTOU race conditions by checking and incrementing in one atomic operation
    CHECK_AND_CONSUME_SCRIPT = """
        local used_key = KEYS[1]
        local meta_key = KEYS[2]
        local current_week_quota = tonumber(ARGV[1])
        local tokens_needed = tonumber(ARGV[2])
        local ttl = tonumber(ARGV[3])
        local student_id = ARGV[4]
        local week_number = ARGV[5]
        local now = ARGV[6]
        
        -- Get current used value
        local current = redis.call('GET', used_key)
        local current_used = tonumber(current) or 0
        
        -- Check if quota is available
        local remaining = current_week_quota - current_used
        if remaining < tokens_needed then
            -- Not enough quota, return failure
            return {0, remaining, current_used}
        end
        
        -- Atomically increment
        local new_used = redis.call('INCRBY', used_key, tokens_needed)
        
        -- Set TTL if this is a new key
        if current == nil then
            redis.call('EXPIRE', used_key, ttl)
        end
        
        -- Update metadata
        local meta = redis.call('GET', meta_key)
        local meta_table = {}
        if meta then
            meta_table = cjson.decode(meta)
        end
        meta_table['quota'] = current_week_quota
        meta_table['last_used'] = now
        meta_table['student_id'] = student_id
        meta_table['week_number'] = week_number
        redis.call('SETEX', meta_key, ttl, cjson.encode(meta_table))
        
        -- Return success
        local new_remaining = current_week_quota - new_used
        return {1, new_remaining, new_used}
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        redis_url: Optional[str] = None,
        enable_sync: bool = True,
    ) -> None:
        """Initialize the distributed quota service.
        
        Args:
            redis_client: Optional Redis client instance
            redis_url: Redis connection URL (uses settings if not provided)
            enable_sync: Whether to enable periodic DB sync
        """
        self._redis = redis_client
        self._redis_url = redis_url or settings.redis_url
        self._sync_task: Optional[asyncio.Task] = None
        self._enable_sync = enable_sync
        self._sync_interval = self.SYNC_INTERVAL_SECONDS
        self._shutdown_event = asyncio.Event()
        
        # Track pending syncs (student_id -> used_quota)
        self._pending_syncs: Dict[str, int] = {}
        self._sync_lock = asyncio.Lock()
    
    def _get_redis(self) -> Optional[Any]:
        """Get or create Redis client.
        
        Returns:
            Redis client if available, None otherwise
        """
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
        """Create Redis key for used quota counter.
        
        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.
            
        Returns:
            Redis key string
        """
        if week_number is None:
            week_number = get_current_week_number()
        return f"{self.REDIS_KEY_PREFIX_USED}:{student_id}:{week_number}"
    
    def _make_meta_key(self, student_id: str, week_number: Optional[int] = None) -> str:
        """Create Redis key for quota metadata.
        
        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.
            
        Returns:
            Redis key string
        """
        if week_number is None:
            week_number = get_current_week_number()
        return f"{self.REDIS_KEY_PREFIX_META}:{student_id}:{week_number}"
    
    async def _get_initial_quota_from_db(
        self, student_id: str, week_number: Optional[int] = None
    ) -> Optional[DistributedQuotaState]:
        """Get initial quota state from database.
        
        Args:
            student_id: The student ID
            week_number: The week number
            
        Returns:
            DistributedQuotaState if found, None otherwise
        """
        from gateway.app.db.async_session import get_async_session
        async with get_async_session() as session:
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
        """Initialize quota counters in Redis from database values.
        
        Uses Redis SET NX (set if not exists) to avoid overwriting existing values.
        
        Args:
            student_id: The student ID
            current_week_quota: Maximum quota for the week
            initial_used: Initial used quota from DB
            week_number: The week number
            
        Returns:
            True if initialized successfully
        """
        redis = self._get_redis()
        if redis is None:
            return False
        
        if week_number is None:
            week_number = get_current_week_number()
        
        try:
            used_key = self._make_used_key(student_id, week_number)
            meta_key = self._make_meta_key(student_id, week_number)
            
            # Check if already exists (use SET NX pattern with SET + GET)
            existing = await redis.get(used_key)
            if existing is None:
                # Initialize with current DB value
                await redis.setex(used_key, self.REDIS_TTL_SECONDS, str(initial_used))
                
                # Store metadata
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
        """Get quota state from Redis or database.
        
        Tries Redis first for distributed state, falls back to database.
        
        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.
            
        Returns:
            DistributedQuotaState if found, None otherwise
        """
        if week_number is None:
            week_number = get_current_week_number()
        
        redis = self._get_redis()
        
        # Try Redis first
        if redis is not None:
            try:
                used_key = self._make_used_key(student_id, week_number)
                meta_key = self._make_meta_key(student_id, week_number)
                
                # Get both values concurrently
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
        
        # Fall back to database
        return await self._get_initial_quota_from_db(student_id, week_number)
    
    async def check_and_consume_quota(
        self,
        student_id: str,
        current_week_quota: int,
        tokens_needed: int,
        week_number: Optional[int] = None,
    ) -> tuple[bool, int, int]:
        """Atomically check and consume quota using Redis or database.
        
        Uses Redis INCR for atomic distributed operations when available.
        Falls back to database check_and_consume_quota when Redis is unavailable.
        
        Args:
            student_id: The student ID
            current_week_quota: Maximum tokens allowed for the week
            tokens_needed: Number of tokens to consume
            week_number: The academic week number. If None, uses current week.
            
        Returns:
            Tuple of (success, remaining_quota, current_used)
            - success: True if quota was sufficient and consumed
            - remaining_quota: Remaining quota after operation
            - current_used: Current used quota
        """
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
        
        # Fallback to database
        from gateway.app.db.async_session import get_async_session
        async with get_async_session() as session:
            return await check_and_consume_quota(session, student_id, tokens_needed)
    
    async def _check_and_consume_with_redis(
        self,
        student_id: str,
        current_week_quota: int,
        tokens_needed: int,
        week_number: int,
    ) -> tuple[bool, int, int]:
        """Check and consume quota using Redis Lua script for atomicity.
        
        Uses Lua script for atomic check-and-consume to prevent TOCTOU race conditions.
        The entire operation (check + increment) happens atomically on the Redis server.
        
        Args:
            student_id: The student ID
            current_week_quota: Maximum tokens allowed for the week
            tokens_needed: Number of tokens to consume
            week_number: The academic week number
            
        Returns:
            Tuple of (success, remaining_quota, current_used)
        """
        redis = self._get_redis()
        if redis is None:
            raise RuntimeError("Redis not available")
        
        used_key = self._make_used_key(student_id, week_number)
        meta_key = self._make_meta_key(student_id, week_number)
        
        # First, ensure Redis has this student's quota initialized
        exists = await redis.exists(used_key)
        
        if not exists:
            # Initialize from database (outside the atomic operation)
            db_state = await self._get_initial_quota_from_db(student_id, week_number)
            if db_state is None:
                return False, 0, 0
            
            await self._init_redis_quota(
                student_id,
                current_week_quota,
                db_state.used_quota,
                week_number,
            )
        
        # Execute Lua script for atomic check-and-consume
        # This prevents TOCTOU race conditions by checking and incrementing atomically
        try:
            result = await redis.eval(
                self.CHECK_AND_CONSUME_SCRIPT,
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
            # Fallback to non-atomic method (less safe but better than hard failure)
            return await self._check_and_consume_fallback(
                student_id, tokens_needed, current_week_quota, week_number
            )
        
        # Parse result: [success (0/1), remaining, new_used]
        success = bool(result[0])
        remaining = int(result[1])
        new_used = int(result[2])
        
        # Track for sync to DB
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
        """Fallback method for quota check-and-consume (non-atomic).
        
        This is used only when Lua script execution fails.
        Not recommended for high-concurrency scenarios due to TOCTOU race conditions.
        
        Args:
            student_id: The student ID
            tokens_needed: Number of tokens to consume
            current_week_quota: Maximum tokens allowed
            week_number: The academic week number
            
        Returns:
            Tuple of (success, remaining_quota, current_used)
        """
        redis = self._get_redis()
        if redis is None:
            raise RuntimeError("Redis not available")
        
        used_key = self._make_used_key(student_id, week_number)
        meta_key = self._make_meta_key(student_id, week_number)
        
        # Check current value
        current_val = await redis.get(used_key)
        if current_val is None:
            current_val = b"0"
        
        current_used = int(current_val)
        remaining = current_week_quota - current_used
        
        if remaining < tokens_needed:
            return False, remaining, current_used
        
        # Increment (non-atomic with check above)
        new_val = await redis.incrby(used_key, tokens_needed)
        new_used = int(new_val)
        new_remaining = current_week_quota - new_used
        
        # Track for sync to DB
        async with self._sync_lock:
            self._pending_syncs[student_id] = new_used
        
        return True, new_remaining, new_used
    
    async def release_quota(
        self,
        student_id: str,
        tokens_to_release: int,
        week_number: Optional[int] = None,
    ) -> bool:
        """Release previously reserved quota.
        
        Used when a request fails or is cancelled after quota was reserved.
        
        Args:
            student_id: The student ID
            tokens_to_release: Number of tokens to release
            week_number: The academic week number. If None, uses current week.
            
        Returns:
            True if released successfully
        """
        if week_number is None:
            week_number = get_current_week_number()
        
        redis = self._get_redis()
        
        if redis is not None:
            try:
                used_key = self._make_used_key(student_id, week_number)
                
                # Use DECRBY to atomically decrease (but not below 0)
                # DECRBY returns the new value
                current = await redis.get(used_key)
                if current is None:
                    return False
                
                current_val = int(current)
                new_val = max(0, current_val - tokens_to_release)
                
                # Calculate actual release amount
                actual_release = current_val - new_val
                
                if actual_release > 0:
                    await redis.decrby(used_key, actual_release)
                    
                    # Track for sync
                    async with self._sync_lock:
                        self._pending_syncs[student_id] = new_val
                
                return True
            except Exception as e:
                logger.warning(f"Failed to release Redis quota for {student_id}: {e}")
        
        # Fallback: update database directly (negative adjustment)
        from gateway.app.db.async_session import get_async_session
        try:
            async with get_async_session() as session:
                # Get current state
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
        if not self._enable_sync:
            return
        
        if self._sync_task is not None:
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
            # Wait for sync loop to finish with timeout
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
                # Wait for sync interval or shutdown
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._sync_interval,
                )
            except asyncio.TimeoutError:
                # Time to sync
                pass
            
            if self._shutdown_event.is_set():
                break
            
            try:
                await self.sync_to_database()
            except Exception as e:
                logger.error(f"Error during quota sync: {e}")
    
    async def sync_to_database(self) -> int:
        """Synchronize pending quota updates from Redis to database.
        
        Returns:
            Number of students synced
        """
        redis = self._get_redis()
        if redis is None:
            return 0
        
        # Get pending syncs
        async with self._sync_lock:
            pending = dict(self._pending_syncs)
            self._pending_syncs.clear()
        
        if not pending:
            return 0
        
        synced_count = 0
        
        from gateway.app.db.async_session import get_async_session
        async with get_async_session() as session:
            for student_id, redis_used in pending.items():
                try:
                    # Get current DB state
                    student = await get_student_by_id(session, student_id)
                    if student is None:
                        continue
                    
                    # Calculate adjustment needed
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
                    # Re-add to pending for next sync
                    async with self._sync_lock:
                        if student_id not in self._pending_syncs:
                            self._pending_syncs[student_id] = redis_used
        
        if synced_count > 0:
            logger.info(f"Synced quota for {synced_count} students to database")
        
        return synced_count
    
    async def get_multi_instance_quota(
        self, student_id: str, week_number: Optional[int] = None
    ) -> Optional[DistributedQuotaState]:
        """Get quota state optimized for multi-instance deployments.
        
        This method prioritizes Redis state for distributed consistency.
        
        Args:
            student_id: The student ID
            week_number: The week number. If None, uses current week.
            
        Returns:
            DistributedQuotaState if found, None otherwise
        """
        state = await self.get_quota_state(student_id, week_number)
        
        if state is not None and state.source == "redis":
            return state
        
        # If only DB state available, try to initialize Redis
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


# Global service instance
_distributed_quota_service: Optional[DistributedQuotaService] = None


def get_distributed_quota_service(
    redis_client: Optional[Any] = None,
    redis_url: Optional[str] = None,
    enable_sync: bool = True,
) -> DistributedQuotaService:
    """Get the global distributed quota service instance.
    
    Args:
        redis_client: Optional Redis client to use
        redis_url: Optional Redis URL
        enable_sync: Whether to enable periodic DB sync
        
    Returns:
        DistributedQuotaService instance
    """
    global _distributed_quota_service
    if _distributed_quota_service is None:
        _distributed_quota_service = DistributedQuotaService(
            redis_client=redis_client,
            redis_url=redis_url,
            enable_sync=enable_sync,
        )
    return _distributed_quota_service


def reset_distributed_quota_service() -> None:
    """Reset the global distributed quota service instance.
    
    Useful for testing.
    """
    global _distributed_quota_service
    _distributed_quota_service = None
