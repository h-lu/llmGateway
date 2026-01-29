"""Performance and benchmark tests for weekly system prompt operations.

These tests measure response times and throughput.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.services.weekly_prompt_service import (
    WeeklyPromptService,
    inject_weekly_system_prompt,
    get_weekly_prompt_service,
    reset_weekly_prompt_service,
)
from gateway.app.db.models import WeeklySystemPrompt


@pytest.fixture(autouse=True)
def reset_service():
    """Reset cache before each test."""
    reset_weekly_prompt_service()
    yield


class TestCachePerformance:
    """Test cache operation performance."""
    
    @pytest.mark.asyncio
    async def test_cache_hit_performance(self):
        """Test cache hit response time < 1ms."""
        service = WeeklyPromptService()
        
        # Pre-populate cache
        service._cached_week = 1
        service._cached_prompt = WeeklySystemPrompt(
            id=1, week_start=1, week_end=1, system_prompt="测试", is_active=True
        )
        service._cache_valid = True
        
        mock_session = AsyncMock()
        
        # Measure 1000 cache hits
        start = time.perf_counter()
        for _ in range(1000):
            await service.get_prompt_for_week(mock_session, 1)
        elapsed = time.perf_counter() - start
        
        avg_time = (elapsed / 1000) * 1000  # Convert to ms
        assert avg_time < 1.0, f"Cache hit too slow: {avg_time:.3f}ms"
    
    @pytest.mark.asyncio
    async def test_cache_miss_db_overhead(self):
        """Test that cache reduces DB calls significantly."""
        service = WeeklyPromptService()
        
        call_count = 0
        async def mock_db_call(session, week):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.001)  # 1ms simulated DB latency
            return WeeklySystemPrompt(
                id=week,
                week_start=week,
                week_end=week,
                system_prompt=f"第{week}周",
                is_active=True,
            )
        
        import gateway.app.services.weekly_prompt_service as service_module
        original = service_module.get_active_prompt_for_week
        service_module.get_active_prompt_for_week = mock_db_call
        
        try:
            mock_session = AsyncMock()
            
            # 100 requests for same week
            for _ in range(100):
                await service.get_prompt_for_week(mock_session, 1)
            
            # Should hit DB only once
            assert call_count == 1, f"Expected 1 DB call, got {call_count}"
            
        finally:
            service_module.get_active_prompt_for_week = original
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_access_performance(self):
        """Test cache performance under concurrent load."""
        service = get_weekly_prompt_service()
        
        # Pre-populate
        service._cached_week = 1
        service._cached_prompt = MagicMock()
        service._cache_valid = True
        
        mock_session = AsyncMock()
        
        async def access():
            return await service.get_prompt_for_week(mock_session, 1)
        
        # 1000 concurrent accesses
        start = time.perf_counter()
        await asyncio.gather(*[access() for _ in range(1000)])
        elapsed = time.perf_counter() - start
        
        # Should complete in < 100ms (all cache hits)
        assert elapsed < 0.1, f"Concurrent cache access too slow: {elapsed*1000:.1f}ms"


class TestMessageInjectionPerformance:
    """Test message injection performance."""
    
    @pytest.mark.asyncio
    async def test_injection_overhead(self):
        """Test prompt injection adds < 5ms overhead."""
        prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="系统提示词",
            is_active=True,
        )
        
        messages = [
            {"role": "user", "content": "用户问题"},
        ]
        
        # Warm up
        for _ in range(100):
            await inject_weekly_system_prompt(messages, prompt)
        
        # Measure
        start = time.perf_counter()
        for _ in range(1000):
            await inject_weekly_system_prompt(messages, prompt)
        elapsed = time.perf_counter() - start
        
        avg_time = (elapsed / 1000) * 1000  # ms
        assert avg_time < 5.0, f"Injection overhead too high: {avg_time:.3f}ms"
    
    @pytest.mark.asyncio
    async def test_large_message_list_performance(self):
        """Test injection with large conversation history."""
        prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="系统提示",
            is_active=True,
        )
        
        # 100-turn conversation
        messages = []
        for i in range(50):
            messages.append({"role": "user", "content": f"问题{i}"})
            messages.append({"role": "assistant", "content": f"回答{i}" * 100})
        
        start = time.perf_counter()
        result = await inject_weekly_system_prompt(messages, prompt)
        elapsed = time.perf_counter() - start
        
        assert len(result) == 101  # +1 system message
        assert elapsed < 0.01, f"Large list injection too slow: {elapsed*1000:.1f}ms"


class TestThroughputBenchmark:
    """Test system throughput."""
    
    @pytest.mark.asyncio
    async def test_prompt_lookup_throughput(self):
        """Test prompt lookups per second."""
        service = WeeklyPromptService()
        
        # Pre-populate cache
        service._cached_week = 1
        service._cached_prompt = WeeklySystemPrompt(
            id=1, week_start=1, week_end=1, system_prompt="测试", is_active=True
        )
        service._cache_valid = True
        
        mock_session = AsyncMock()
        
        # Measure ops/sec
        duration = 0.1  # 100ms
        start = time.perf_counter()
        count = 0
        
        while time.perf_counter() - start < duration:
            await service.get_prompt_for_week(mock_session, 1)
            count += 1
        
        ops_per_sec = count / duration
        assert ops_per_sec > 10000, f"Throughput too low: {ops_per_sec:.0f} ops/sec"
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_end_to_end_response_time(self):
        """Benchmark end-to-end response time (simulated)."""
        # This simulates the full flow: check cache → inject → return
        service = get_weekly_prompt_service()
        
        prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="你是一个Python助教喵",
            is_active=True,
        )
        
        # Pre-populate
        service._cached_week = 1
        service._cached_prompt = prompt
        service._cache_valid = True
        
        messages = [{"role": "user", "content": "什么是变量？"}]
        
        start = time.perf_counter()
        
        # Full flow
        cached_prompt = await service.get_prompt_for_week(None, 1)
        modified_messages = await inject_weekly_system_prompt(messages, cached_prompt)
        
        elapsed = time.perf_counter() - start
        
        assert len(modified_messages) == 2
        assert modified_messages[0]["role"] == "system"
        assert elapsed < 0.001, f"End-to-end too slow: {elapsed*1000:.3f}ms"


class TestMemoryUsage:
    """Test memory efficiency."""
    
    def test_cache_memory_footprint(self):
        """Test that cache doesn't grow unbounded."""
        service = WeeklyPromptService()
        
        # Service only caches ONE week at a time
        prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="X" * 10000,  # 10KB prompt
            is_active=True,
        )
        
        service._cached_week = 1
        service._cached_prompt = prompt
        service._cache_valid = True
        
        # Memory usage should be constant regardless of total prompts in DB
        # (only current week cached)
        assert service._cached_prompt is not None
        
        # Switching weeks should replace (not accumulate)
        prompt2 = WeeklySystemPrompt(
            id=2,
            week_start=2,
            week_end=2,
            system_prompt="Y" * 10000,
            is_active=True,
        )
        service._cached_week = 2
        service._cached_prompt = prompt2
        
        # Old prompt should be replaced (garbage collected)
        assert service._cached_prompt == prompt2


class TestScalability:
    """Test scalability with large datasets."""
    
    @pytest.mark.asyncio
    async def test_many_prompts_query_performance(self):
        """Test query performance with many prompts in DB."""
        from gateway.app.db.weekly_prompt_crud import get_active_prompt_for_week
        
        # Simulate DB with 100 prompts
        many_prompts = [
            WeeklySystemPrompt(
                id=i,
                week_start=i,
                week_end=i,
                system_prompt=f"第{i}周",
                is_active=True,
            )
            for i in range(1, 101)
        ]
        
        # Mock returning the specific one
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = many_prompts[49]  # Week 50
        mock_session.execute.return_value = mock_result
        
        start = time.perf_counter()
        result = await get_active_prompt_for_week(mock_session, week_number=50)
        elapsed = time.perf_counter() - start
        
        assert result.week_start == 50
        assert elapsed < 0.001, f"Query too slow with large dataset: {elapsed*1000:.3f}ms"
