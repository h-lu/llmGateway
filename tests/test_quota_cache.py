"""Tests for QuotaCacheService."""

import pytest
import asyncio
from unittest.mock import patch

from gateway.app.core.cache import InMemoryCache, reset_cache
from gateway.app.services.quota_cache import (
    QuotaCacheService,
    QuotaCacheState,
    get_quota_cache_service,
    reset_quota_cache_service,
)


class TestQuotaCacheState:
    """Test QuotaCacheState dataclass."""
    
    def test_remaining_calculation(self):
        """Test remaining property calculates correctly."""
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=300,
            version=1,
        )
        assert state.remaining == 700
    
    def test_remaining_zero(self):
        """Test remaining when quota is exhausted."""
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=1000,
            version=1,
        )
        assert state.remaining == 0
    
    def test_remaining_negative(self):
        """Test remaining when over quota."""
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=1500,
            version=1,
        )
        assert state.remaining == -500
    
    def test_to_dict(self):
        """Test serialization to dict."""
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=300,
            version=2,
        )
        data = state.to_dict()
        assert data["student_id"] == "test_student"
        assert data["week_number"] == 5
        assert data["current_week_quota"] == 1000
        assert data["used_quota"] == 300
        assert data["version"] == 2
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "student_id": "test_student",
            "week_number": 5,
            "current_week_quota": 1000,
            "used_quota": 300,
            "version": 2,
        }
        state = QuotaCacheState.from_dict(data)
        assert state.student_id == "test_student"
        assert state.week_number == 5
        assert state.current_week_quota == 1000
        assert state.used_quota == 300
        assert state.version == 2
    
    def test_from_dict_default_version(self):
        """Test deserialization with default version."""
        data = {
            "student_id": "test_student",
            "week_number": 5,
            "current_week_quota": 1000,
            "used_quota": 300,
        }
        state = QuotaCacheState.from_dict(data)
        assert state.version == 1


class TestQuotaCacheService:
    """Test QuotaCacheService."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup fresh cache and service for each test."""
        reset_cache()
        reset_quota_cache_service()
        self.cache = InMemoryCache()
        self.service = QuotaCacheService(cache=self.cache)
        yield
        reset_cache()
        reset_quota_cache_service()
    
    @pytest.mark.asyncio
    async def test_get_quota_state_cache_miss(self):
        """Test get returns None on cache miss."""
        result = await self.service.get_quota_state("nonexistent", week_number=5)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_and_get_quota_state(self):
        """Test set and get quota state."""
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=300,
            version=1,
        )
        await self.service.set_quota_state(state)
        
        result = await self.service.get_quota_state("test_student", week_number=5)
        assert result is not None
        assert result.student_id == "test_student"
        assert result.week_number == 5
        assert result.current_week_quota == 1000
        assert result.used_quota == 300
        assert result.version == 1
    
    @pytest.mark.asyncio
    async def test_delete_quota_state(self):
        """Test delete removes quota state."""
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=300,
            version=1,
        )
        await self.service.set_quota_state(state)
        await self.service.delete_quota_state("test_student", week_number=5)
        
        result = await self.service.get_quota_state("test_student", week_number=5)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_key_format(self):
        """Test cache key uses correct format."""
        key = self.service._make_key("student123", week_number=5)
        assert key == "quota:student123:5"
    
    @pytest.mark.asyncio
    async def test_get_quota_state_invalid_data(self):
        """Test get handles invalid cache data gracefully."""
        # Store invalid data
        await self.cache.set("quota:bad_student:5", b"invalid json", ttl=30)
        
        result = await self.service.get_quota_state("bad_student", week_number=5)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_quota_state_corrupted_data(self):
        """Test get handles corrupted JSON gracefully."""
        await self.cache.set("quota:corrupt:5", b'{"invalid": json}', ttl=30)
        
        result = await self.service.get_quota_state("corrupt", week_number=5)
        assert result is None


class TestQuotaCacheServiceCheckAndReserve:
    """Test check_and_reserve_quota with mocked DB."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup fresh cache and service for each test."""
        reset_cache()
        reset_quota_cache_service()
        self.cache = InMemoryCache()
        self.service = QuotaCacheService(cache=self.cache)
        yield
        reset_cache()
        reset_quota_cache_service()
    
    @pytest.fixture
    def mock_get_async_session(self):
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
    
    @pytest.mark.asyncio
    async def test_cache_hit_sufficient_quota(self, monkeypatch, mock_get_async_session):
        """Test successful reservation updates cache from DB result."""
        # Setup cache with sufficient quota
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=300,
            version=1,
        )
        await self.service.set_quota_state(state)
        
        # Mock DB to return successful reservation (session is first arg now)
        async def mock_db(session, student_id, tokens, auto_commit=True):
            return True, 600, 400  # success, remaining, used
        
        from gateway.app.services import quota_cache
        monkeypatch.setattr(quota_cache, "check_and_consume_quota", mock_db)
        
        success, remaining, used = await self.service.check_and_reserve_quota(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            tokens_needed=100,
        )
        
        assert success is True
        assert remaining == 600  # From DB
        assert used == 400  # From DB
        
        # Verify cache was updated with DB result
        cached = await self.service.get_quota_state("test_student", week_number=5)
        assert cached.used_quota == 400
        assert cached.remaining == 600
    
    @pytest.mark.asyncio
    async def test_cache_hit_insufficient_quota(self, monkeypatch, mock_get_async_session):
        """Test failure when cache shows insufficient quota."""
        # Setup cache with insufficient quota
        state = QuotaCacheState(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            used_quota=950,
            version=1,
        )
        await self.service.set_quota_state(state)
        
        # Mock DB to simulate exhausted quota (session is first arg now)
        async def mock_db(session, student_id, tokens, auto_commit=True):
            return False, 50, 950
        
        from gateway.app.services import quota_cache
        monkeypatch.setattr(quota_cache, "check_and_consume_quota", mock_db)
        
        success, remaining, used = await self.service.check_and_reserve_quota(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            tokens_needed=100,  # Need 100, only 50 remaining
        )
        
        assert success is False
        assert remaining == 50
        assert used == 950
    
    @pytest.mark.asyncio
    async def test_cache_miss_calls_db(self, monkeypatch, mock_get_async_session):
        """Test DB is called on cache miss."""
        db_called = False
        async def mock_db(session, student_id, tokens, auto_commit=True):
            nonlocal db_called
            db_called = True
            return True, 700, 300
        
        from gateway.app.services import quota_cache
        monkeypatch.setattr(quota_cache, "check_and_consume_quota", mock_db)
        
        success, remaining, used = await self.service.check_and_reserve_quota(
            student_id="test_student",
            week_number=5,
            current_week_quota=1000,
            tokens_needed=100,
        )
        
        assert db_called is True
        assert success is True
        
        # Verify cache was updated from DB result
        cached = await self.service.get_quota_state("test_student", week_number=5)
        assert cached is not None
        assert cached.used_quota == 300
    
    @pytest.mark.asyncio
    async def test_cache_ttl(self):
        """Test cache entries have TTL."""
        # Verify the service uses correct TTL
        assert self.service.CACHE_TTL_SECONDS == 30


class TestGlobalQuotaCacheService:
    """Test global service instance functions."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset global state before each test."""
        reset_quota_cache_service()
        yield
        reset_quota_cache_service()
    
    def test_get_quota_cache_service_singleton(self):
        """Test service is a singleton."""
        service1 = get_quota_cache_service()
        service2 = get_quota_cache_service()
        assert service1 is service2
    
    def test_get_quota_cache_service_with_cache(self):
        """Test service creation with explicit cache."""
        cache = InMemoryCache()
        service = get_quota_cache_service(cache=cache)
        assert service._cache is cache
    
    def test_reset_quota_cache_service(self):
        """Test reset creates new instance on next get."""
        service1 = get_quota_cache_service()
        reset_quota_cache_service()
        service2 = get_quota_cache_service()
        assert service1 is not service2
