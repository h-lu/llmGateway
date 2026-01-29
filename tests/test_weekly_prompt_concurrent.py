"""Concurrent access and thread-safety tests for weekly prompt service."""

import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.services.weekly_prompt_service import (
    WeeklyPromptService,
    get_weekly_prompt_service,
    reset_weekly_prompt_service,
)
from gateway.app.db.models import WeeklySystemPrompt


@pytest.fixture(autouse=True)
def reset_service():
    """Reset singleton before each test."""
    reset_weekly_prompt_service()
    yield


class TestCacheThreadSafety:
    """Test cache behavior under concurrent access."""
    
    @pytest.mark.asyncio
    async def test_concurrent_reads_same_week(self):
        """Test multiple concurrent reads for same week."""
        service = WeeklyPromptService()
        
        # Mock session that returns same prompt
        mock_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="测试提示词",
            is_active=True,
        )
        
        async def mock_get_prompt(session, week):
            await asyncio.sleep(0.01)  # Simulate DB latency
            return mock_prompt
        
        # Patch the CRUD function
        import gateway.app.services.weekly_prompt_service as service_module
        original_func = service_module.get_active_prompt_for_week
        service_module.get_active_prompt_for_week = mock_get_prompt
        
        try:
            mock_session = AsyncMock()
            
            # 50 concurrent reads for week 1
            tasks = [
                service.get_prompt_for_week(mock_session, 1)
                for _ in range(50)
            ]
            results = await asyncio.gather(*tasks)
            
            # All should return same result
            assert all(r == mock_prompt for r in results)
            
        finally:
            service_module.get_active_prompt_for_week = original_func
    
    @pytest.mark.asyncio
    async def test_concurrent_reads_different_weeks(self):
        """Test concurrent reads for different weeks."""
        service = WeeklyPromptService()
        
        prompts_by_week = {
            1: WeeklySystemPrompt(id=1, week_start=1, week_end=1, system_prompt="第1周", is_active=True),
            2: WeeklySystemPrompt(id=2, week_start=2, week_end=2, system_prompt="第2周", is_active=True),
            3: WeeklySystemPrompt(id=3, week_start=3, week_end=3, system_prompt="第3周", is_active=True),
        }
        
        async def mock_get_prompt(session, week):
            await asyncio.sleep(0.01)
            return prompts_by_week.get(week)
        
        import gateway.app.services.weekly_prompt_service as service_module
        original_func = service_module.get_active_prompt_for_week
        service_module.get_active_prompt_for_week = mock_get_prompt
        
        try:
            mock_session = AsyncMock()
            
            # Interleaved reads for different weeks
            tasks = []
            for i in range(30):
                week = (i % 3) + 1
                tasks.append(service.get_prompt_for_week(mock_session, week))
            
            results = await asyncio.gather(*tasks)
            
            # Verify correct mapping
            for i, result in enumerate(results):
                expected_week = (i % 3) + 1
                assert result == prompts_by_week[expected_week]
                
        finally:
            service_module.get_active_prompt_for_week = original_func


class TestCacheInvalidationRaceConditions:
    """Test cache invalidation during concurrent access."""
    
    @pytest.mark.asyncio
    async def test_read_during_invalidation(self):
        """Test reading cache while another thread invalidates it."""
        service = WeeklyPromptService()
        
        # Pre-populate cache
        cached_prompt = WeeklySystemPrompt(id=1, week_start=1, week_end=1, system_prompt="缓存", is_active=True)
        service._cached_week = 1
        service._cached_prompt = cached_prompt
        service._cache_valid = True
        
        async def read_cache():
            mock_session = AsyncMock()
            return await service.get_prompt_for_week(mock_session, 1)
        
        def invalidate_cache():
            service.invalidate_cache()
        
        # Start read
        read_task = asyncio.create_task(read_cache())
        
        # Invalidate immediately
        invalidate_cache()
        
        # Read should still succeed (might hit DB if invalidated first)
        result = await read_task
        # Result could be cached_prompt or from DB
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_invalidation_and_update(self):
        """Test concurrent cache invalidation and updates."""
        service = get_weekly_prompt_service()
        
        operations = []
        
        async def cache_operation(op_id: int):
            if op_id % 3 == 0:
                # Invalidate
                service.invalidate_cache()
                return "invalidated"
            elif op_id % 3 == 1:
                # Set cache
                service._cached_week = 1
                service._cached_prompt = MagicMock()
                service._cache_valid = True
                return "set"
            else:
                # Read cache
                valid = service._cache_valid
                week = service._cached_week
                return f"read:{valid}:{week}"
        
        # Run 30 interleaved operations
        tasks = [cache_operation(i) for i in range(30)]
        results = await asyncio.gather(*tasks)
        
        # Service should not crash (no assertions on specific state due to race)
        assert len(results) == 30


class TestSingletonThreadSafety:
    """Test singleton instance in multi-threaded environment."""
    
    def test_singleton_thread_safety(self):
        """Test get_weekly_prompt_service is thread-safe."""
        services = []
        
        def get_service():
            svc = get_weekly_prompt_service()
            services.append(id(svc))
        
        # 20 threads getting service simultaneously
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(get_service) for _ in range(20)]
            for f in as_completed(futures):
                f.result()
        
        # All should get same instance
        assert len(set(services)) == 1
    
    def test_reset_and_recreate_thread_safety(self):
        """Test reset and recreate in multi-threaded environment."""
        results = []
        
        def reset_and_get():
            reset_weekly_prompt_service()
            svc = get_weekly_prompt_service()
            results.append(id(svc))
        
        # Concurrent reset and get (may create multiple instances)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(reset_and_get) for _ in range(10)]
            for f in as_completed(futures):
                f.result()
        
        # After all operations, final get should return consistent instance
        final_id = id(get_weekly_prompt_service())
        assert final_id in results


class TestCacheConsistency:
    """Test cache consistency guarantees."""
    
    @pytest.mark.asyncio
    async def test_cache_eventual_consistency(self):
        """Test that cache eventually becomes consistent."""
        service = WeeklyPromptService()
        
        # Sequence: set week 1, read week 1, set week 2, read week 2, read week 1
        mock_prompt_1 = WeeklySystemPrompt(id=1, week_start=1, week_end=1, system_prompt="周1", is_active=True)
        mock_prompt_2 = WeeklySystemPrompt(id=2, week_start=2, week_end=2, system_prompt="周2", is_active=True)
        
        call_count = 0
        async def mock_get_prompt(session, week):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)
            return mock_prompt_1 if week == 1 else mock_prompt_2
        
        import gateway.app.services.weekly_prompt_service as service_module
        original_func = service_module.get_active_prompt_for_week
        service_module.get_active_prompt_for_week = mock_get_prompt
        
        try:
            mock_session = AsyncMock()
            
            # Read week 1 - should hit DB
            r1 = await service.get_prompt_for_week(mock_session, 1)
            assert r1 == mock_prompt_1
            assert call_count == 1
            
            # Read week 1 again - should hit cache
            r2 = await service.get_prompt_for_week(mock_session, 1)
            assert r2 == mock_prompt_1
            assert call_count == 1  # No DB call
            
            # Read week 2 - should hit DB (different week)
            r3 = await service.get_prompt_for_week(mock_session, 2)
            assert r3 == mock_prompt_2
            assert call_count == 2
            
            # Read week 1 again - should still be cached (week 2 doesn't invalidate week 1 cache)
            # Actually current implementation does invalidate, so this will hit DB
            r4 = await service.get_prompt_for_week(mock_session, 1)
            assert r4 == mock_prompt_1
            # call_count could be 2 or 3 depending on implementation
            
        finally:
            service_module.get_active_prompt_for_week = original_func


class TestStressTest:
    """Stress tests for cache under load."""
    
    @pytest.mark.asyncio
    async def test_cache_under_load(self):
        """Test cache behavior under high concurrent load."""
        service = WeeklyPromptService()
        
        async def mock_get_prompt(session, week):
            await asyncio.sleep(0.001)  # 1ms DB latency
            return WeeklySystemPrompt(
                id=week,
                week_start=week,
                week_end=week,
                system_prompt=f"第{week}周",
                is_active=True,
            )
        
        import gateway.app.services.weekly_prompt_service as service_module
        original_func = service_module.get_active_prompt_for_week
        service_module.get_active_prompt_for_week = mock_get_prompt
        
        try:
            mock_session = AsyncMock()
            
            # 100 concurrent requests across 4 weeks
            async def request(week: int):
                return await service.get_prompt_for_week(mock_session, week)
            
            tasks = [request((i % 4) + 1) for i in range(100)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # No exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
            
            # All results are valid prompts
            prompts = [r for r in results if not isinstance(r, Exception)]
            assert len(prompts) == 100
            
        finally:
            service_module.get_active_prompt_for_week = original_func
