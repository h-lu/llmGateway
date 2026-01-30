"""Async conversation logging service with batch writing.

This module provides asynchronous conversation logging with batch writing
to improve database performance by buffering logs and writing in bulk.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks

from gateway.app.core.logging import get_logger
from gateway.app.db.async_session import get_async_session
from gateway.app.db.crud import save_conversation_bulk, update_student_quota_bulk
from gateway.app.db.models import Conversation

logger = get_logger(__name__)

# Dead letter queue file path for failed logs
DEAD_LETTER_QUEUE_PATH = Path(
    os.getenv("DEAD_LETTER_QUEUE_PATH", "/tmp/gateway_failed_logs.jsonl")
)


@dataclass
class ConversationLogData:
    """Data required to log a conversation."""
    student_id: str
    prompt: str
    response: str
    tokens_used: int
    action: str
    rule_triggered: Optional[str]
    week_number: int
    max_tokens: int  # Original reserved tokens
    request_id: str


@dataclass
class LogBufferEntry:
    """An entry in the log buffer with retry tracking."""
    log_data: ConversationLogData
    attempt_count: int = 0
    last_error: Optional[Exception] = field(default=None)


class AsyncConversationLogger:
    """Async conversation logger with batch writing.
    
    This class handles conversation logging with buffering and batch insertion
to improve database performance. Logs are collected in a buffer and written
to the database either when the buffer reaches a certain size or after a
timeout period.
    
    Features:
    - Batch buffering: collects up to `buffer_size` logs (default 100)
    - Timer-based flush: flushes every `flush_interval` seconds (default 5)
    - Graceful shutdown: flushes remaining logs on shutdown
    - Retry logic: retries failed logs with exponential backoff
    
    Example:
        logger = AsyncConversationLogger()
        logger.log_conversation(
            background_tasks=background_tasks,
            log_data=ConversationLogData(...)
        )
        
        # On application shutdown:
        await logger.shutdown()
    """
    
    def __init__(
        self,
        buffer_size: int = 100,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize the async batch logger.
        
        Args:
            buffer_size: Maximum number of logs to buffer before flushing
            flush_interval: Maximum time in seconds between flushes
            max_retries: Maximum number of retry attempts for failed logs
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Buffer for log entries
        self._buffer: List[LogBufferEntry] = []
        self._buffer_lock = asyncio.Lock()
        
        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Track initialization state
        self._started = False
    
    def start(self) -> None:
        """Start the background flush task.
        
        This should be called during application startup.
        """
        if not self._started:
            self._shutdown_event.clear()
            self._flush_task = asyncio.create_task(self._flush_loop())
            self._started = True
            logger.debug("AsyncConversationLogger started")
    
    async def shutdown(self) -> None:
        """Shutdown the logger gracefully.
        
        Flushes any remaining logs in the buffer before returning.
        This should be called during application shutdown.
        
        Note: Always flushes the buffer even if not explicitly started,
        to handle edge cases where logs were buffered but start() was never called.
        """
        logger.debug("AsyncConversationLogger shutting down...")
        self._shutdown_event.set()
        
        # Cancel the flush loop if it was started
        if self._started and self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush of remaining logs - always do this even if not started
        await self._flush_buffer()
        
        self._started = False
        logger.debug("AsyncConversationLogger shutdown complete")
    
    def log_conversation(
        self,
        background_tasks: BackgroundTasks,
        log_data: ConversationLogData,
    ) -> None:
        """Add a conversation log to the buffer.
        
        This method adds the log data to the buffer and triggers a flush
        if the buffer is full. The actual database write happens asynchronously.
        
        Args:
            background_tasks: FastAPI BackgroundTasks instance
            log_data: All data required to log the conversation
        """
        # Ensure the logger is started
        if not self._started:
            self.start()
        
        # Add to background tasks for processing
        background_tasks.add_task(self._add_to_buffer, log_data)
    
    async def _add_to_buffer(self, log_data: ConversationLogData) -> None:
        """Add a log entry to the buffer.
        
        Args:
            log_data: The conversation log data to buffer
        """
        entry = LogBufferEntry(log_data=log_data)
        
        async with self._buffer_lock:
            self._buffer.append(entry)
            buffer_count = len(self._buffer)
        
        logger.debug(
            "Conversation log added to buffer",
            extra={
                "student_id": log_data.student_id,
                "request_id": log_data.request_id,
                "buffer_size": buffer_count,
            }
        )
        
        # Trigger immediate flush if buffer is full
        if buffer_count >= self.buffer_size:
            asyncio.create_task(self._flush_buffer())
    
    async def _flush_loop(self) -> None:
        """Background task that periodically flushes the buffer."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for the flush interval or shutdown signal
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.flush_interval
                )
            except asyncio.TimeoutError:
                # Time to flush
                pass
            
            # Flush if not shutting down (shutdown does its own final flush)
            if not self._shutdown_event.is_set():
                await self._flush_buffer()
    
    async def _flush_buffer(self) -> None:
        """Flush the buffer by writing all logs to the database.
        
        This method takes all logs from the buffer and writes them to the
database in a batch operation. Failed logs are retried.
        """
        # Extract logs from buffer
        async with self._buffer_lock:
            if not self._buffer:
                return
            entries = self._buffer[:]
            self._buffer = []
        
        if not entries:
            return
        
        logger.debug(f"Flushing {len(entries)} conversation logs to database")
        
        # Execute batch logging with retry
        await self._batch_log_with_retry(entries)
    
    async def _batch_log_with_retry(self, entries: List[LogBufferEntry]) -> None:
        """Execute batch logging with retry logic.
        
        Attempts to save all conversations in the batch. Failed entries
        are retried individually with exponential backoff.
        
        Args:
            entries: List of log buffer entries to save
        """
        # Separate entries that need quota adjustment
        quota_adjustments: dict[str, int] = {}  # student_id -> adjustment
        
        for entry in entries:
            log_data = entry.log_data
            if log_data.tokens_used != log_data.max_tokens:
                adjustment = log_data.tokens_used - log_data.max_tokens
                if log_data.student_id in quota_adjustments:
                    quota_adjustments[log_data.student_id] += adjustment
                else:
                    quota_adjustments[log_data.student_id] = adjustment
        
        # Attempt batch save
        last_error: Optional[Exception] = None
        delay = self.retry_delay
        
        for attempt in range(1, self.max_retries + 1):
            try:
                async with get_async_session() as session:
                    # Prepare conversation records
                    conversations = []
                    for entry in entries:
                        log_data = entry.log_data
                        conversation = Conversation(
                            student_id=log_data.student_id,
                            timestamp=datetime.now(),
                            prompt_text=log_data.prompt,
                            response_text=log_data.response,
                            tokens_used=log_data.tokens_used,
                            rule_triggered=log_data.rule_triggered,
                            action_taken=log_data.action,
                            week_number=log_data.week_number,
                        )
                        conversations.append(conversation)
                    
                    # Batch insert conversations
                    if conversations:
                        await save_conversation_bulk(session, conversations)
                    
                    # Batch update quotas
                    if quota_adjustments:
                        await update_student_quota_bulk(session, quota_adjustments)
                
                logger.info(
                    f"Successfully saved {len(conversations)} conversations",
                    extra={"attempt": attempt}
                )
                return
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Batch save failed (attempt {attempt}/{self.max_retries}): {e}",
                    extra={"attempt": attempt, "error": str(e)}
                )
                
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2
        
        # All retries exhausted - write to dead letter queue for later recovery
        logger.error(
            f"Batch save failed after {self.max_retries} attempts: {last_error}. "
            f"Writing {len(entries)} conversation logs to dead letter queue."
        )
        
        await self._write_to_dead_letter_queue(entries)
    
    async def _write_to_dead_letter_queue(self, entries: List[LogBufferEntry]) -> None:
        """Write failed log entries to a dead letter queue file for later recovery.
        
        This ensures audit trail data is not lost even during database outages.
        Failed logs can be replayed later using the recovery script.
        
        Args:
            entries: List of log entries that failed to save
        """
        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            
            def _write_sync():
                # Ensure directory exists
                DEAD_LETTER_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
                
                with open(DEAD_LETTER_QUEUE_PATH, "a", encoding="utf-8") as f:
                    for entry in entries:
                        log_record = {
                            "timestamp": datetime.now().isoformat(),
                            "student_id": entry.log_data.student_id,
                            "prompt": entry.log_data.prompt,
                            "response": entry.log_data.response,
                            "tokens_used": entry.log_data.tokens_used,
                            "action": entry.log_data.action,
                            "rule_triggered": entry.log_data.rule_triggered,
                            "week_number": entry.log_data.week_number,
                            "max_tokens": entry.log_data.max_tokens,
                            "request_id": entry.log_data.request_id,
                        }
                        f.write(json.dumps(log_record, ensure_ascii=False) + "\n")
            
            await loop.run_in_executor(None, _write_sync)
            
            logger.info(
                f"Successfully wrote {len(entries)} failed logs to dead letter queue",
                extra={"dead_letter_queue": str(DEAD_LETTER_QUEUE_PATH)}
            )
            
        except Exception as dlq_error:
            # Last resort: log the error with full details
            logger.critical(
                f"Failed to write to dead letter queue: {dlq_error}. "
                f"{len(entries)} conversation logs are permanently lost!",
                extra={
                    "dlq_error": str(dlq_error),
                    "entry_count": len(entries),
                }
            )
            
            # Log each entry individually for debugging
            for entry in entries:
                logger.error(
                    "Permanently lost conversation log",
                    extra={
                        "student_id": entry.log_data.student_id,
                        "request_id": entry.log_data.request_id,
                        "action": entry.log_data.action,
                        "tokens_used": entry.log_data.tokens_used,
                    }
                )


# Global instance for convenience
async_logger = AsyncConversationLogger()


def get_async_logger() -> AsyncConversationLogger:
    """Get the global async conversation logger instance.
    
    Returns:
        The global AsyncConversationLogger instance
    """
    return async_logger
