"""Regex utilities with timeout support."""
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Pattern
from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Thread pool for executing regex with timeout
_regex_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="regex_")

# Default regex timeout in seconds
REGEX_TIMEOUT_SECONDS = 2.0


def _regex_search_sync(pattern: Pattern, text: str) -> Optional[re.Match]:
    """Execute regex search synchronously."""
    try:
        return pattern.search(text)
    except re.error as e:
        logger.error(f"Regex error: {e}")
        return None


async def _regex_search_with_timeout(
    pattern: Pattern,
    text: str,
    timeout: float = REGEX_TIMEOUT_SECONDS
) -> Optional[re.Match]:
    """Execute regex search asynchronously with timeout protection.
    
    Args:
        pattern: Compiled regex pattern
        text: Text to search
        timeout: Timeout in seconds
        
    Returns:
        Match result or None
    """
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_regex_executor, _regex_search_sync, pattern, text),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"Regex timeout after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"Regex execution error: {e}")
        return None


def cleanup_regex_executor() -> None:
    """Cleanup regex thread pool (for testing)."""
    _regex_executor.shutdown(wait=False)
