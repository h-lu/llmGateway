"""Tests for the async batch logger."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from gateway.app.services.async_logger import (
    AsyncConversationLogger,
    ConversationLogData,
    get_async_logger,
)


@pytest.fixture
def sample_log_data():
    """Create sample conversation log data."""
    return ConversationLogData(
        student_id="student-123",
        prompt="Hello, world!",
        response="Hi there!",
        tokens_used=10,
        action="passed",
        rule_triggered=None,
        week_number=1,
        max_tokens=10,
        request_id="req-123",
    )


@pytest.fixture
def background_tasks():
    """Create a mock BackgroundTasks."""
    tasks = MagicMock(spec=BackgroundTasks)
    tasks.add_task = MagicMock()
    return tasks


@pytest.mark.asyncio
async def test_logger_starts_automatically(sample_log_data, background_tasks):
    """Test that the logger starts automatically when logging."""
    logger = AsyncConversationLogger()
    
    assert not logger._started
    
    # Mock the start method to prevent actual task creation
    with patch.object(logger, 'start') as mock_start:
        logger.log_conversation(background_tasks, sample_log_data)
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_add_to_buffer(sample_log_data):
    """Test adding logs to the buffer."""
    logger = AsyncConversationLogger(buffer_size=10)
    logger.start()
    
    try:
        # Add log to buffer
        await logger._add_to_buffer(sample_log_data)
        
        # Check buffer state
        assert len(logger._buffer) == 1
        assert logger._buffer[0].log_data == sample_log_data
    finally:
        await logger.shutdown()


@pytest.mark.asyncio
async def test_buffer_flush_on_size():
    """Test that buffer flushes when it reaches buffer_size."""
    logger = AsyncConversationLogger(buffer_size=5)
    logger.start()
    
    try:
        # Mock flush_buffer to track calls
        with patch.object(logger, '_flush_buffer') as mock_flush:
            # Add 5 logs (should trigger flush)
            for i in range(5):
                log_data = ConversationLogData(
                    student_id=f"student-{i}",
                    prompt=f"Prompt {i}",
                    response=f"Response {i}",
                    tokens_used=10,
                    action="passed",
                    rule_triggered=None,
                    week_number=1,
                    max_tokens=10,
                    request_id=f"req-{i}",
                )
                await logger._add_to_buffer(log_data)
            
            # Give async task time to execute
            await asyncio.sleep(0.1)
            
            # Flush should have been triggered
            mock_flush.assert_called()
    finally:
        await logger.shutdown()


@pytest.mark.asyncio
async def test_batch_log_with_retry_success():
    """Test successful batch logging."""
    logger = AsyncConversationLogger()
    
    # Create sample entries (with different token usage to trigger quota adjustments)
    entries = []
    for i in range(3):
        log_data = ConversationLogData(
            student_id=f"student-{i}",
            prompt=f"Prompt {i}",
            response=f"Response {i}",
            tokens_used=8,  # Different from max_tokens to trigger quota adjustment
            action="passed",
            rule_triggered=None,
            week_number=1,
            max_tokens=10,
            request_id=f"req-{i}",
        )
        from gateway.app.services.async_logger import LogBufferEntry
        entries.append(LogBufferEntry(log_data=log_data))
    
    # Mock the bulk save functions
    with patch("gateway.app.services.async_logger.save_conversation_bulk", new_callable=AsyncMock) as mock_save:
        with patch("gateway.app.services.async_logger.update_student_quota_bulk", new_callable=AsyncMock) as mock_quota:
            await logger._batch_log_with_retry(entries)
            
            # Verify bulk save was called
            mock_save.assert_called_once()
            assert len(mock_save.call_args[0][0]) == 3  # 3 conversations
            # Quota adjustment should be called since tokens_used != max_tokens
            mock_quota.assert_called_once()


@pytest.mark.asyncio
async def test_batch_log_with_quota_adjustments():
    """Test batch logging with quota adjustments."""
    logger = AsyncConversationLogger()
    
    # Create entries with different token usage (triggering quota adjustments)
    from gateway.app.services.async_logger import LogBufferEntry
    
    entries = [
        LogBufferEntry(log_data=ConversationLogData(
            student_id="student-1",
            prompt="Prompt",
            response="Response",
            tokens_used=5,  # Less than max_tokens
            action="passed",
            rule_triggered=None,
            week_number=1,
            max_tokens=10,
            request_id="req-1",
        )),
        LogBufferEntry(log_data=ConversationLogData(
            student_id="student-1",  # Same student
            prompt="Prompt 2",
            response="Response 2",
            tokens_used=15,  # More than max_tokens
            action="passed",
            rule_triggered=None,
            week_number=1,
            max_tokens=10,
            request_id="req-2",
        )),
    ]
    
    # Mock the bulk save functions
    with patch("gateway.app.services.async_logger.save_conversation_bulk", new_callable=AsyncMock) as mock_save:
        with patch("gateway.app.services.async_logger.update_student_quota_bulk", new_callable=AsyncMock) as mock_quota:
            await logger._batch_log_with_retry(entries)
            
            # Verify bulk save was called
            mock_save.assert_called_once()
            # Verify quota update was called with combined adjustments
            mock_quota.assert_called_once()
            # Check the adjustment dict (5-10=-5 + 15-10=+5 = 0 total for student-1)
            adjustments = mock_quota.call_args[0][0]
            assert "student-1" in adjustments
            assert adjustments["student-1"] == 0  # -5 + 5 = 0


@pytest.mark.asyncio
async def test_graceful_shutdown_flushes_buffer():
    """Test that shutdown flushes remaining logs."""
    logger = AsyncConversationLogger(buffer_size=100)  # Large buffer to prevent auto-flush
    logger.start()
    
    # Add some logs without triggering flush
    for i in range(5):
        log_data = ConversationLogData(
            student_id=f"student-{i}",
            prompt=f"Prompt {i}",
            response=f"Response {i}",
            tokens_used=10,
            action="passed",
            rule_triggered=None,
            week_number=1,
            max_tokens=10,
            request_id=f"req-{i}",
        )
        await logger._add_to_buffer(log_data)
    
    assert len(logger._buffer) == 5
    
    # Mock flush_buffer to verify it's called
    with patch.object(logger, '_flush_buffer') as mock_flush:
        # Call shutdown
        await logger.shutdown()
        
        # Verify final flush was called
        mock_flush.assert_called()


@pytest.mark.asyncio
async def test_flush_buffer_with_empty_buffer():
    """Test that flushing an empty buffer does nothing."""
    logger = AsyncConversationLogger()
    logger.start()
    
    try:
        # Mock batch_log_with_retry to verify it's not called
        with patch.object(logger, '_batch_log_with_retry') as mock_batch:
            await logger._flush_buffer()
            mock_batch.assert_not_called()
    finally:
        await logger.shutdown()


@pytest.mark.asyncio
async def test_global_logger_instance():
    """Test that the global logger instance works."""
    logger = get_async_logger()
    assert isinstance(logger, AsyncConversationLogger)
    
    # Should return the same instance
    logger2 = get_async_logger()
    assert logger is logger2


@pytest.mark.asyncio
async def test_batch_retry_failure():
    """Test that batch logging retries on failure."""
    logger = AsyncConversationLogger(max_retries=2, retry_delay=0.01)
    
    from gateway.app.services.async_logger import LogBufferEntry
    entries = [
        LogBufferEntry(log_data=ConversationLogData(
            student_id="student-1",
            prompt="Prompt",
            response="Response",
            tokens_used=10,
            action="passed",
            rule_triggered=None,
            week_number=1,
            max_tokens=10,
            request_id="req-1",
        )),
    ]
    
    # Mock save to always fail
    with patch("gateway.app.services.async_logger.save_conversation_bulk", new_callable=AsyncMock) as mock_save:
        mock_save.side_effect = Exception("DB Error")
        
        # Mock logger.error to avoid spamming output
        with patch("gateway.app.services.async_logger.logger.error"):
            await logger._batch_log_with_retry(entries)
        
        # Should have been called max_retries times
        assert mock_save.call_count == 2
