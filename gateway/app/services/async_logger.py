"""Async conversation logging service using FastAPI BackgroundTasks.

This module provides asynchronous conversation logging to avoid blocking
response delivery to the client.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from fastapi import BackgroundTasks

from gateway.app.core.logging import get_logger
from gateway.app.db.crud import save_conversation, update_student_quota

logger = get_logger(__name__)


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


class AsyncConversationLogger:
    """Async conversation logger using FastAPI BackgroundTasks.
    
    This class handles conversation saving and quota adjustment
    asynchronously using FastAPI's BackgroundTasks, ensuring that
    response delivery is not blocked by database operations.
    
    Example:
        logger = AsyncConversationLogger()
        logger.log_conversation(
            background_tasks=background_tasks,
            log_data=ConversationLogData(...)
        )
    """
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        """Initialize the async logger.
        
        Args:
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def log_conversation(
        self,
        background_tasks: BackgroundTasks,
        log_data: ConversationLogData,
    ) -> None:
        """Add conversation logging as a background task.
        
        This method adds the logging task to FastAPI's BackgroundTasks,
        which will execute after the response is sent to the client.
        
        Args:
            background_tasks: FastAPI BackgroundTasks instance
            log_data: All data required to log the conversation
        """
        background_tasks.add_task(
            self._log_with_retry,
            log_data,
        )
    
    async def _log_with_retry(self, log_data: ConversationLogData) -> None:
        """Execute logging with retry logic.
        
        Attempts to save the conversation and adjust quota with
        exponential backoff on failures. Errors are logged but do
        not raise exceptions to avoid affecting the client response.
        
        Args:
            log_data: All data required to log the conversation
        """
        last_error: Optional[Exception] = None
        delay = self.retry_delay
        
        for attempt in range(1, self.max_retries + 1):
            try:
                await self._execute_logging(log_data)
                logger.debug(
                    "Conversation logged successfully",
                    extra={
                        "student_id": log_data.student_id,
                        "request_id": log_data.request_id,
                        "attempt": attempt,
                    }
                )
                return
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Failed to save conversation (attempt {attempt}/{self.max_retries}): {e}",
                    extra={
                        "student_id": log_data.student_id,
                        "request_id": log_data.request_id,
                        "attempt": attempt,
                        "error": str(e),
                    }
                )
                
                if attempt < self.max_retries:
                    # Exponential backoff: 1s, 2s, 4s...
                    await asyncio.sleep(delay)
                    delay *= 2
        
        # All retries exhausted
        logger.error(
            f"Failed to save conversation after {self.max_retries} attempts: {last_error}",
            extra={
                "student_id": log_data.student_id,
                "request_id": log_data.request_id,
            }
        )
    
    async def _execute_logging(self, log_data: ConversationLogData) -> None:
        """Execute the actual logging operations.
        
        Saves the conversation record and adjusts quota if needed.
        
        Args:
            log_data: All data required to log the conversation
            
        Raises:
            Exception: If database operations fail
        """
        # Save conversation
        await save_conversation(
            student_id=log_data.student_id,
            prompt=log_data.prompt,
            response=log_data.response,
            tokens_used=log_data.tokens_used,
            action=log_data.action,
            rule_triggered=log_data.rule_triggered,
            week_number=log_data.week_number,
        )
        
        # Adjust quota if actual usage differs from reserved
        if log_data.tokens_used != log_data.max_tokens:
            adjustment = log_data.tokens_used - log_data.max_tokens
            await update_student_quota(log_data.student_id, adjustment)


# Global instance for convenience
async_logger = AsyncConversationLogger()


def get_async_logger() -> AsyncConversationLogger:
    """Get the global async conversation logger instance.
    
    Returns:
        The global AsyncConversationLogger instance
    """
    return async_logger
