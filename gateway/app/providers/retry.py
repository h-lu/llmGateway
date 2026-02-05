"""Retry mechanism with exponential backoff for AI providers.

This module provides a configurable retry policy and decorator that implements
exponential backoff for transient failures in HTTP requests.
"""

import asyncio
import functools
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

import httpx

from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class RetryPolicy:
    """Configuration for retry behavior with exponential backoff.

    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 0.5)
        max_delay: Maximum delay between retries in seconds (default: 10.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        retryable_exceptions: Tuple of exception types that trigger a retry

    Example:
        >>> policy = RetryPolicy(max_retries=5, base_delay=1.0)
        >>> delay = policy.calculate_delay(attempt=2)  # Returns 4.0
    """

    max_retries: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    exponential_base: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        httpx.HTTPStatusError,
        httpx.NetworkError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )

    def calculate_delay(self, attempt: int) -> float:
        """Calculate the delay for a given retry attempt.

        Uses exponential backoff: delay = min(base_delay * (exponential_base ^ attempt), max_delay)

        Args:
            attempt: The current retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base**attempt)
        return min(delay, self.max_delay)

    def is_retryable(self, exception: Exception) -> bool:
        """Check if an exception should trigger a retry.

        For HTTPStatusError, only 5xx status codes are considered retryable.

        Args:
            exception: The exception to check

        Returns:
            True if the exception should trigger a retry
        """
        # Special handling for HTTPStatusError - only retry 5xx errors
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code >= 500

        return isinstance(exception, self.retryable_exceptions)


def with_retry(policy: Optional[RetryPolicy] = None) -> Callable[[F], F]:
    """Decorator that adds retry logic with exponential backoff.

    This decorator wraps async functions and retries them on specified
    exceptions using exponential backoff.

    Args:
        policy: RetryPolicy configuration. Uses defaults if not provided.

    Returns:
        Decorated function with retry logic

    Example:
        >>> @with_retry(policy=RetryPolicy(max_retries=3))
        ... async def chat_completion(self, payload):
        ...     return await self._make_request(payload)
    """
    retry_policy = policy or RetryPolicy()

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None

            for attempt in range(retry_policy.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Check if we should retry this exception
                    if not retry_policy.is_retryable(e):
                        logger.debug(
                            f"Non-retryable exception in {func.__name__}: {type(e).__name__}: {e}"
                        )
                        raise

                    # Check if we've exhausted retries
                    if attempt >= retry_policy.max_retries:
                        logger.warning(
                            f"Max retries ({retry_policy.max_retries}) exceeded for {func.__name__}: "
                            f"{type(e).__name__}: {e}"
                        )
                        raise

                    # Calculate delay and log
                    delay = retry_policy.calculate_delay(attempt)
                    logger.warning(
                        f"Retry {attempt + 1}/{retry_policy.max_retries} for {func.__name__} "
                        f"after {type(e).__name__}: {e}. Waiting {delay:.2f}s..."
                    )

                    # Wait before retry
                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper  # type: ignore

    return decorator
