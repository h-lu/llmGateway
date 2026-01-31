"""Tests for DistributedQuotaService.

Tests cover:
- Basic quota state operations
- Redis INCR atomic operations  
- Fallback to database when Redis is unavailable
- Periodic sync functionality
- Multi-process concurrency testing
"""

import asyncio
import json
import multiprocessing
import os
import sys
import time
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from unittest.mock import patch

# Import the service under test
from gateway.app.services.distributed_quota import (
    DistributedQuotaService,
    DistributedQuotaState,
    get_distributed_quota_service,
    reset_distributed_quota_service,
)
from gateway.app.core.cache import InMemoryCache, reset_cache


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state before each test."""
    reset_distributed_quota_service()
    reset_cache()
    yield
    reset_distributed_quota_service()
    reset_cache()


@pytest.fixture
def mock_get_async_session():
    """Mock the get_async_session to avoid database dependency."""
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock
    
    mock_session = AsyncMock()
    
    @asynccontextmanager
    async def _mock_session():
        yield mock_session
    
    # Patch at the module level where it's imported
    with patch("gateway.app.db.async_session.get_async_session", _mock_session):
        yield mock_session


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing."""
    redis = MagicMock()
    redis.data = {}
    redis.ttls = {}
    
    async def mock_get(key):
        # Check if expired
        if key in redis.ttls and redis.ttls[key] < time.time():
            redis.data.pop(key, None)
            redis.ttls.pop(key, None)
            return None
        value = redis.data.get(key)
        return value.encode() if isinstance(value, str) else value
    
    async def mock_setex(key, ttl, value):
        redis.data[key] = value.decode() if isinstance(value, bytes) else str(value)
        redis.ttls[key] = time.time() + ttl
    
    async def mock_incrby(key, amount):
        current = redis.data.get(key, "0")
        new_val = int(current) + amount
        redis.data[key] = str(new_val)
        return new_val
    
    async def mock_decrby(key, amount):
        current = redis.data.get(key, "0")
        new_val = max(0, int(current) - amount)
        redis.data[key] = str(new_val)
        return new_val
    
    async def mock_exists(key):
        if key in redis.ttls and redis.ttls[key] < time.time():
            return 0
        return 1 if key in redis.data else 0
    
    async def mock_delete(key):
        redis.data.pop(key, None)
        redis.ttls.pop(key, None)
        return 1

    async def mock_eval(script, num_keys, *args):
        """Mock Redis Lua script execution for CHECK_AND_CONSUME_SCRIPT.

        Simulates the atomic check-and-consume operation:
        - ARGV[1]: current_week_quota
        - ARGV[2]: tokens_needed
        - ARGV[3]: ttl
        - ARGV[4]: student_id
        - ARGV[5]: week_number
        - ARGV[6]: timestamp
        - KEYS[1]: used_key (format: quota:used:{student_id}:{week_number})
        - KEYS[2]: meta_key
        """
        # Parse arguments
        if len(args) < 6:
            return [0, 0, 0]

        current_week_quota = int(args[0])
        tokens_needed = int(args[1])
        ttl = int(args[2])
        student_id = str(args[3])
        week_number = str(args[4])
        now = args[5]

        # Extract keys from args (after num_keys)
        used_key = args[6] if len(args) > 6 else f"quota:used:{student_id}:{week_number}"
        meta_key = args[7] if len(args) > 7 else f"quota:meta:{student_id}:{week_number}"

        # Get current used value
        current = redis.data.get(used_key)
        current_used = int(current) if current else 0

        # Check if quota is available
        remaining = current_week_quota - current_used
        if remaining < tokens_needed:
            # Not enough quota
            return [0, remaining, current_used]

        # Atomically increment
        new_used = current_used + tokens_needed
        redis.data[used_key] = str(new_used)

        # Set TTL if this is a new key
        if current is None:
            redis.ttls[used_key] = time.time() + ttl

        # Update metadata
        meta = redis.data.get(meta_key)
        meta_table = json.loads(meta) if meta else {}
        meta_table['quota'] = current_week_quota
        meta_table['last_used'] = now
        meta_table['student_id'] = student_id
        meta_table['week_number'] = week_number
        redis.data[meta_key] = json.dumps(meta_table)
        redis.ttls[meta_key] = time.time() + ttl

        # Return success
        new_remaining = current_week_quota - new_used
        return [1, new_remaining, new_used]

    redis.get = mock_get
    redis.setex = mock_setex
    redis.incrby = mock_incrby
    redis.decrby = mock_decrby
    redis.exists = mock_exists
    redis.delete = mock_delete
    redis.eval = mock_eval
    redis.close = AsyncMock()

    return redis


@pytest.fixture
def mock_db_student():
    """Create a mock student for database operations."""
    student = MagicMock()
    student.id = "test_student"
    student.current_week_quota = 1000
    student.used_quota = 100
    return student


# ============================================================================
# Test DistributedQuotaState
# ============================================================================

class TestDistributedQuotaState:
    """Test DistributedQuotaState dataclass."""
    
    def test_remaining_calculation(self):
        """Test remaining property calculates correctly."""
        state = DistributedQuotaState(
            student_id="test_student",
            current_week_quota=1000,
            used_quota=300,
            week_number=5,
            source="redis",
        )
        assert state.remaining == 700
    
    def test_remaining_zero(self):
        """Test remaining when quota is exhausted."""
        state = DistributedQuotaState(
            student_id="test_student",
            current_week_quota=1000,
            used_quota=1000,
            week_number=5,
            source="db",
        )
        assert state.remaining == 0
    
    def test_remaining_negative(self):
        """Test remaining when over quota."""
        state = DistributedQuotaState(
            student_id="test_student",
            current_week_quota=1000,
            used_quota=1500,
            week_number=5,
            source="redis",
        )
        assert state.remaining == -500
    
    def test_to_dict(self):
        """Test serialization to dict."""
        state = DistributedQuotaState(
            student_id="test_student",
            current_week_quota=1000,
            used_quota=300,
            week_number=5,
            source="redis",
        )
        data = state.to_dict()
        assert data["student_id"] == "test_student"
        assert data["current_week_quota"] == 1000
        assert data["used_quota"] == 300
        assert data["week_number"] == 5
        assert data["source"] == "redis"
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "student_id": "test_student",
            "current_week_quota": 1000,
            "used_quota": 300,
            "week_number": 5,
            "source": "db",
        }
        state = DistributedQuotaState.from_dict(data)
        assert state.student_id == "test_student"
        assert state.current_week_quota == 1000
        assert state.used_quota == 300
        assert state.week_number == 5
        assert state.source == "db"
    
    def test_from_dict_defaults(self):
        """Test deserialization with default values."""
        data = {
            "student_id": "test_student",
            "current_week_quota": 1000,
            "used_quota": 300,
        }
        state = DistributedQuotaState.from_dict(data)
        assert state.week_number == 0
        assert state.source == "db"


# ============================================================================
# Test DistributedQuotaService Basic Operations
# ============================================================================

class TestDistributedQuotaServiceBasic:
    """Test basic DistributedQuotaService operations."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup fresh service for each test."""
        self.service = DistributedQuotaService(enable_sync=False)
        yield
    
    @pytest.mark.asyncio
    async def test_redis_key_format(self):
        """Test Redis key format is correct."""
        used_key = self.service._make_used_key("student123", week_number=5)
        meta_key = self.service._make_meta_key("student123", week_number=5)
        
        assert used_key == "quota:used:student123:5"
        assert meta_key == "quota:meta:student123:5"
    
    @pytest.mark.asyncio
    async def test_init_redis_quota(self, mock_redis):
        """Test initializing quota in Redis."""
        self.service._redis = mock_redis
        
        result = await self.service._init_redis_quota(
            "test_student",
            current_week_quota=1000,
            initial_used=100,
            week_number=5,
        )
        
        assert result is True
        assert mock_redis.data.get("quota:used:test_student:5") == "100"
        assert "quota:meta:test_student:5" in mock_redis.data
        
        # Verify metadata
        meta = json.loads(mock_redis.data["quota:meta:test_student:5"])
        assert meta["quota"] == 1000
        assert meta["initial_used"] == 100
    
    @pytest.mark.asyncio
    async def test_init_redis_quota_already_exists(self, mock_redis):
        """Test initializing quota when already exists."""
        self.service._redis = mock_redis
        
        # Pre-populate
        mock_redis.data["quota:used:test_student:5"] = "200"
        
        result = await self.service._init_redis_quota(
            "test_student",
            current_week_quota=1000,
            initial_used=100,
            week_number=5,
        )
        
        assert result is True
        # Should not overwrite existing value
        assert mock_redis.data.get("quota:used:test_student:5") == "200"


# ============================================================================
# Test Redis Quota Operations
# ============================================================================

class TestDistributedQuotaServiceRedis:
    """Test Redis-based quota operations."""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_redis, mock_db_student):
        """Setup service with mock Redis."""
        self.service = DistributedQuotaService(enable_sync=False)
        self.service._redis = mock_redis
        self.mock_student = mock_db_student
        yield
    
    @pytest.mark.asyncio
    async def test_get_quota_state_from_redis(self, mock_redis):
        """Test getting quota state from Redis."""
        # Pre-populate Redis
        mock_redis.data["quota:used:test_student:5"] = "300"
        mock_redis.data["quota:meta:test_student:5"] = json.dumps({
            "quota": 1000,
            "initialized_at": datetime.now().isoformat(),
        })
        
        state = await self.service.get_quota_state("test_student", week_number=5)
        
        assert state is not None
        assert state.student_id == "test_student"
        assert state.current_week_quota == 1000
        assert state.used_quota == 300
        assert state.week_number == 5
        assert state.source == "redis"
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    async def test_get_quota_state_fallback_to_db(self, mock_get_student, mock_db_student):
        """Test fallback to database when Redis is empty."""
        mock_get_student.return_value = mock_db_student
        
        # Clear Redis
        self.service._redis = None
        
        state = await self.service.get_quota_state("test_student", week_number=5)
        
        assert state is not None
        assert state.source == "db"
        assert state.used_quota == 100
        # Verify the mock was called with session as first argument
        mock_get_student.assert_called_once()
        call_args = mock_get_student.call_args
        assert call_args[0][1] == "test_student"  # First arg is session, second is student_id
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    async def test_check_and_consume_with_redis_sufficient_quota(self, mock_get_student, mock_db_student, mock_redis):
        """Test consuming quota when sufficient.

        With lazy initialization, Redis starts from 0 (not from DB value).
        This ensures atomic operations without race conditions.
        """
        mock_get_student.return_value = mock_db_student

        success, remaining, used = await self.service._check_and_consume_with_redis(
            "test_student",
            current_week_quota=1000,
            tokens_needed=100,
            week_number=5,
        )

        assert success is True
        # With lazy initialization: starts from 0, consumes 100
        assert used == 100
        assert remaining == 900

    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    async def test_check_and_consume_with_redis_insufficient_quota(self, mock_get_student, mock_db_student, mock_redis):
        """Test consuming quota when insufficient.

        Pre-populate Redis with 950 used to test insufficient quota scenario.
        """
        # Pre-populate Redis to test insufficient quota
        mock_redis.data["quota:used:test_student:5"] = "950"
        mock_redis.data["quota:meta:test_student:5"] = json.dumps({"quota": 1000})
        mock_get_student.return_value = mock_db_student

        success, remaining, used = await self.service._check_and_consume_with_redis(
            "test_student",
            current_week_quota=1000,
            tokens_needed=100,  # Need 100, only 50 remaining
            week_number=5,
        )

        assert success is False
        assert remaining == 50
        assert used == 950
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    async def test_release_quota(self, mock_get_student, mock_redis, mock_db_student):
        """Test releasing previously consumed quota."""
        mock_get_student.return_value = mock_db_student
        
        # Setup initial state in Redis
        mock_redis.data["quota:used:test_student:5"] = "500"
        mock_redis.data["quota:meta:test_student:5"] = json.dumps({"quota": 1000})
        
        result = await self.service.release_quota("test_student", tokens_to_release=200, week_number=5)
        
        assert result is True
        assert mock_redis.data["quota:used:test_student:5"] == "300"


# ============================================================================
# Test Database Fallback
# ============================================================================

class TestDistributedQuotaServiceFallback:
    """Test fallback to database when Redis is unavailable."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup service without Redis."""
        self.service = DistributedQuotaService(enable_sync=False)
        self.service._redis = None
        yield
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.check_and_consume_quota")
    async def test_fallback_to_database(self, mock_check_consume):
        """Test fallback to database when Redis unavailable."""
        mock_check_consume.return_value = (True, 800, 200)
        
        success, remaining, used = await self.service.check_and_consume_quota(
            "test_student",
            current_week_quota=1000,
            tokens_needed=200,
            week_number=5,
        )
        
        assert success is True
        assert remaining == 800
        assert used == 200
        # Verify mock was called with session as first argument
        mock_check_consume.assert_called_once()
        call_args = mock_check_consume.call_args
        assert call_args[0][1] == "test_student"  # First arg is session, second is student_id
        assert call_args[0][2] == 200  # Third arg is tokens_needed


# ============================================================================
# Test Sync to Database
# ============================================================================

class TestDistributedQuotaServiceSync:
    """Test periodic sync to database."""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_redis, mock_db_student):
        """Setup service with mock Redis and DB."""
        self.service = DistributedQuotaService(enable_sync=False)
        self.service._redis = mock_redis
        self.mock_student = mock_db_student
        yield
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    @patch("gateway.app.services.distributed_quota.update_student_quota")
    async def test_sync_to_database(self, mock_update_quota, mock_get_student):
        """Test syncing Redis state to database."""
        # Setup: DB has 100, Redis has 500
        self.mock_student.used_quota = 100
        mock_get_student.return_value = self.mock_student
        mock_update_quota.return_value = True
        
        # Add pending sync
        self.service._pending_syncs["test_student"] = 500
        
        synced = await self.service.sync_to_database()
        
        assert synced == 1
        # Should update DB with adjustment of +400
        # Verify mock was called with session as first argument
        mock_update_quota.assert_called_once()
        call_args = mock_update_quota.call_args
        assert call_args[0][1] == "test_student"  # First arg is session, second is student_id
        assert call_args[0][2] == 400  # Third arg is adjustment
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    @patch("gateway.app.services.distributed_quota.update_student_quota")
    async def test_sync_no_pending(self, mock_update_quota, mock_get_student):
        """Test sync when no pending updates."""
        synced = await self.service.sync_to_database()
        
        assert synced == 0
        mock_update_quota.assert_not_called()
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    @patch("gateway.app.services.distributed_quota.update_student_quota")
    async def test_sync_multiple_students(self, mock_update_quota, mock_get_student):
        """Test syncing multiple students."""
        # Setup mocks for multiple students
        students = {
            "student1": MagicMock(id="student1", used_quota=100, current_week_quota=1000),
            "student2": MagicMock(id="student2", used_quota=200, current_week_quota=1000),
        }
        mock_get_student.side_effect = lambda session, sid: students.get(sid)
        
        # Add pending syncs
        self.service._pending_syncs["student1"] = 500  # +400 adjustment
        self.service._pending_syncs["student2"] = 300  # +100 adjustment
        
        synced = await self.service.sync_to_database()
        
        assert synced == 2
        assert mock_update_quota.call_count == 2


# ============================================================================
# Test Multi-Instance Quota
# ============================================================================

class TestMultiInstanceQuota:
    """Test multi-instance quota operations."""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_redis, mock_db_student):
        """Setup service."""
        self.service = DistributedQuotaService(enable_sync=False)
        self.service._redis = mock_redis
        self.mock_student = mock_db_student
        yield
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    async def test_get_multi_instance_quota_from_redis(self, mock_get_student, mock_redis):
        """Test getting multi-instance quota when Redis has data."""
        mock_get_student.return_value = self.mock_student
        
        # Pre-populate Redis
        mock_redis.data["quota:used:test_student:5"] = "400"
        mock_redis.data["quota:meta:test_student:5"] = json.dumps({"quota": 1000})
        
        state = await self.service.get_multi_instance_quota("test_student", week_number=5)
        
        assert state is not None
        assert state.source == "redis"
        assert state.used_quota == 400
    
    @pytest.mark.asyncio
    @patch("gateway.app.services.distributed_quota.get_student_by_id")
    async def test_get_multi_instance_quota_init_redis(self, mock_get_student, mock_redis):
        """Test that DB state initializes Redis when Redis is empty."""
        mock_get_student.return_value = self.mock_student
        
        # Redis is empty, DB has data
        state = await self.service.get_multi_instance_quota("test_student", week_number=5)
        
        assert state is not None
        # Should initialize Redis with DB values
        assert "quota:used:test_student:5" in mock_redis.data


# ============================================================================
# Test Atomic Operations
# ============================================================================

class TestAtomicOperations:
    """Test atomic quota operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_incrby_is_atomic(self):
        """Test that multiple concurrent INCRBY operations are atomic.
        
        This simulates multiple instances consuming quota simultaneously.
        """
        # Create a simple in-memory Redis-like store with proper locking
        class AtomicRedis:
            def __init__(self):
                self.data = {}
                self.lock = asyncio.Lock()
            
            async def get(self, key):
                async with self.lock:
                    return self.data.get(key, b"0")
            
            async def setex(self, key, ttl, value):
                async with self.lock:
                    self.data[key] = str(value).encode()
            
            async def incrby(self, key, amount):
                async with self.lock:
                    current = int(self.data.get(key, b"0"))
                    new_val = current + amount
                    self.data[key] = str(new_val).encode()
                    return new_val
            
            async def exists(self, key):
                async with self.lock:
                    return 1 if key in self.data else 0
        
        redis = AtomicRedis()
        service = DistributedQuotaService(enable_sync=False)
        service._redis = redis
        
        # Initialize with 0
        await redis.setex("quota:used:student1:5", 86400, "0")
        await redis.setex("quota:meta:student1:5", 86400, json.dumps({"quota": 10000}))
        
        # Simulate 10 concurrent consumers, each consuming 100 tokens
        async def consume():
            return await service._check_and_consume_with_redis(
                "student1", 10000, 100, 5
            )
        
        # Run 10 concurrent consumers
        results = await asyncio.gather(*[consume() for _ in range(10)])
        
        # All should succeed
        assert all(r[0] for r in results), "All consumers should succeed"
        
        # Final value should be exactly 1000 (10 * 100)
        final_val = await redis.get("quota:used:student1:5")
        assert int(final_val) == 1000, f"Expected 1000, got {final_val}"


# ============================================================================
# Test Global Service Instance
# ============================================================================

class TestGlobalServiceInstance:
    """Test global service instance functions."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset global state before each test."""
        reset_distributed_quota_service()
        yield
        reset_distributed_quota_service()
    
    def test_get_service_singleton(self):
        """Test service is a singleton."""
        service1 = get_distributed_quota_service(enable_sync=False)
        service2 = get_distributed_quota_service(enable_sync=False)
        
        assert service1 is service2
    
    def test_reset_service(self):
        """Test reset creates new instance."""
        service1 = get_distributed_quota_service(enable_sync=False)
        reset_distributed_quota_service()
        service2 = get_distributed_quota_service(enable_sync=False)
        
        assert service1 is not service2
    
    def test_get_service_with_redis_url(self):
        """Test service creation with explicit Redis URL."""
        service = get_distributed_quota_service(
            redis_url="redis://custom:6379/1",
            enable_sync=False,
        )
        
        assert service._redis_url == "redis://custom:6379/1"


# ============================================================================
# Test Sync Task Lifecycle
# ============================================================================

class TestSyncTaskLifecycle:
    """Test sync task start/stop lifecycle."""
    
    @pytest.mark.asyncio
    async def test_start_stop_sync_task(self):
        """Test starting and stopping the sync task."""
        service = DistributedQuotaService(enable_sync=True)
        
        # Start sync task
        await service.start_sync_task()
        assert service._sync_task is not None
        
        # Stop sync task
        await service.stop_sync_task()
        assert service._sync_task is None
    
    @pytest.mark.asyncio
    async def test_sync_task_not_started_when_disabled(self):
        """Test sync task is not started when disabled."""
        service = DistributedQuotaService(enable_sync=False)
        
        await service.start_sync_task()
        assert service._sync_task is None
    
    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self, mock_redis):
        """Test close method cleans up resources."""
        service = DistributedQuotaService(enable_sync=True)
        service._redis = mock_redis
        
        await service.start_sync_task()
        await service.close()
        
        assert service._sync_task is None
        assert service._redis is None


# ============================================================================
# Test Configuration Integration
# ============================================================================

class TestConfigIntegration:
    """Test integration with configuration."""
    
    def test_service_uses_config_redis_url(self):
        """Test service uses Redis URL from config."""
        with patch("gateway.app.services.distributed_quota.settings") as mock_settings:
            mock_settings.redis_url = "redis://config:6379/2"
            mock_settings.redis_enabled = False
            
            service = DistributedQuotaService(enable_sync=False)
            
            assert service._redis_url == "redis://config:6379/2"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.mark.asyncio
    async def test_get_quota_state_student_not_found(self):
        """Test getting quota for non-existent student."""
        service = DistributedQuotaService(enable_sync=False)
        service._redis = None
        
        with patch("gateway.app.services.distributed_quota.get_student_by_id") as mock:
            mock.return_value = None
            
            state = await service.get_quota_state("nonexistent", week_number=5)
            
            assert state is None
    
    @pytest.mark.asyncio
    async def test_release_quota_negative_result(self, mock_redis):
        """Test release quota doesn't go below zero."""
        service = DistributedQuotaService(enable_sync=False)
        service._redis = mock_redis
        
        # Setup: used is 50
        mock_redis.data["quota:used:student1:5"] = "50"
        mock_redis.data["quota:meta:student1:5"] = json.dumps({"quota": 1000})
        
        # Try to release 100 (more than used)
        result = await service.release_quota("student1", tokens_to_release=100, week_number=5)
        
        assert result is True
        # Should clamp to 0, not negative
        assert mock_redis.data["quota:used:student1:5"] == "0"
    
    @pytest.mark.asyncio
    async def test_check_and_consume_exactly_at_limit(self, mock_redis):
        """Test consuming exactly the remaining quota."""
        service = DistributedQuotaService(enable_sync=False)
        service._redis = mock_redis

        mock_student = MagicMock()
        mock_student.used_quota = 900
        mock_student.current_week_quota = 1000

        with patch("gateway.app.services.distributed_quota.get_student_by_id") as mock:
            mock.return_value = mock_student

            # Pre-populate Redis with 900 used
            mock_redis.data["quota:used:student1:5"] = "900"
            mock_redis.data["quota:meta:student1:5"] = json.dumps({"quota": 1000})

            # Try to consume exactly 100 (remaining quota)
            success, remaining, used = await service._check_and_consume_with_redis(
                "student1", 1000, 100, 5
            )

            assert success is True
            assert remaining == 0
            assert used == 1000  # 900 (initial) + 100 (consumed)


# ============================================================================
# Multi-Process Concurrency Test
# ============================================================================

def _worker_consume_quota(
    redis_url: str,
    student_id: str,
    week_number: int,
    tokens_per_request: int,
    num_requests: int,
    results_queue: multiprocessing.Queue,
):
    """Worker process for concurrent quota consumption test.
    
    This function is run in separate processes to simulate multiple
    gateway instances consuming quota simultaneously.
    """
    import asyncio
    
    async def run():
        # Create service with explicit Redis client
        service = DistributedQuotaService(
            redis_url=redis_url,
            enable_sync=False,
        )
        
        # Initialize Redis connection
        redis = service._get_redis()
        if redis is None:
            results_queue.put(("error", "Redis not available"))
            return
        
        success_count = 0
        failure_count = 0
        
        for _ in range(num_requests):
            try:
                success, remaining, used = await service.check_and_consume_quota(
                    student_id=student_id,
                    current_week_quota=10000,
                    tokens_needed=tokens_per_request,
                    week_number=week_number,
                )
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
        
        results_queue.put(("success", success_count, failure_count))
        await service.close()
    
    asyncio.run(run())


@pytest.mark.skip(reason="Requires running Redis server - run manually with: redis-server")
class TestMultiProcessConcurrency:
    """Test multi-process concurrent quota consumption.
    
    These tests require a running Redis server and are skipped by default.
    To run: start redis-server, then run pytest with --run-redis flag.
    """
    
    @pytest.fixture(scope="class")
    def redis_available(self):
        """Check if Redis is available."""
        try:
            import redis
            r = redis.Redis(host="localhost", port=6379, socket_connect_timeout=1)
            r.ping()
            return True
        except Exception:
            return False
    
    def test_multi_process_concurrent_consumption(self, redis_available):
        """Test that multiple processes can safely consume quota concurrently.
        
        This test simulates multiple gateway instances consuming from the same
        quota pool, verifying that the total consumed never exceeds the limit.
        """
        if not redis_available:
            pytest.skip("Redis not available")
        
        import redis as redis_lib
        
        # Setup: Clear any existing quota data
        r = redis_lib.Redis(host="localhost", port=6379)
        student_id = "test_concurrent_student"
        week_number = 99  # Use unique week number for this test
        
        # Clean up any existing keys
        for key in r.scan_iter(match=f"quota:*:{student_id}:{week_number}"):
            r.delete(key)
        
        # Initialize quota in Redis
        total_quota = 1000
        r.setex(f"quota:used:{student_id}:{week_number}", 3600, "0")
        r.setex(
            f"quota:meta:{student_id}:{week_number}",
            3600,
            json.dumps({"quota": total_quota}),
        )
        
        # Launch multiple processes
        num_processes = 4
        requests_per_process = 10
        tokens_per_request = 20
        # 4 * 10 * 20 = 800 tokens should succeed (under 1000 limit)
        
        processes = []
        results_queue = multiprocessing.Queue()
        
        for _ in range(num_processes):
            p = multiprocessing.Process(
                target=_worker_consume_quota,
                args=(
                    "redis://localhost:6379/0",
                    student_id,
                    week_number,
                    tokens_per_request,
                    requests_per_process,
                    results_queue,
                ),
            )
            processes.append(p)
            p.start()
        
        # Wait for all processes to complete
        for p in processes:
            p.join(timeout=30)
        
        # Collect results
        total_success = 0
        total_failure = 0
        for _ in range(num_processes):
            result = results_queue.get(timeout=5)
            if result[0] == "success":
                total_success += result[1]
                total_failure += result[2]
        
        # Verify results
        final_used = int(r.get(f"quota:used:{student_id}:{week_number}") or 0)
        
        # Cleanup
        for key in r.scan_iter(match=f"quota:*:{student_id}:{week_number}"):
            r.delete(key)
        
        # Assertions
        expected_consumed = total_success * tokens_per_request
        assert final_used == expected_consumed, (
            f"Final used ({final_used}) should match successful consumptions "
            f"({expected_consumed})"
        )
        assert final_used <= total_quota, (
            f"Total consumed ({final_used}) should not exceed quota ({total_quota})"
        )
        print(f"\nMulti-process test results:")
        print(f"  Total successful: {total_success}")
        print(f"  Total failed: {total_failure}")
        print(f"  Final quota used: {final_used}")
        print(f"  Expected consumed: {expected_consumed}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
