"""Rate limiting data models.

This module contains dataclasses for rate limit state and results.
"""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None


@dataclass
class RateLimitEntry:
    """Entry for tracking rate limit state (sliding window)."""
    requests: int = 0
    window_start: float = field(default_factory=time.time)


@dataclass
class TokenBucket:
    """Token bucket state for token bucket algorithm."""
    tokens: float = field(default_factory=float)
    last_update: float = field(default_factory=time.time)
