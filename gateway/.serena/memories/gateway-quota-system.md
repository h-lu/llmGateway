# Gateway Quota Management System

## Overview
Two-tier quota system: in-memory cache for performance, database for persistence, optional Redis for multi-instance deployments.

## Components

### QuotaCacheService (`app/services/quota_cache.py`)
Primary quota checking service with cache-first strategy:
- `check_and_reserve_quota(student_id, week_number, quota, tokens_needed, session)`
- Uses in-memory LRU cache for fast lookups
- Falls back to database on cache miss
- Optimistic locking to prevent race conditions
- Async cache refresh from database

### DistributedQuotaService (`app/services/distributed_quota.py`)
Redis-backed distributed quota for multi-instance deployments:
- Atomic quota operations using Redis INCR/DECR
- Key format: `quota:used:{student_id}:{week_number}`
- Periodic sync from Redis to database (every 60 seconds)
- Fallback to database when Redis unavailable
- TTL: 7 days for weekly quota keys

Key methods:
- `get_quota_state(student_id, week_number)` - Get from Redis or DB
- `check_and_consume_quota(...)` - Atomic check and consume
- `release_quota(student_id, tokens)` - Refund on request failure
- `start_sync_task()` - Start background sync to DB
- `sync_to_database()` - Manually trigger sync

## Database Models

### Student (`app/db/models.py`)
```python
class Student(Base):
    id: str  # Student ID
    current_week_quota: int  # Weekly token limit
    used_quota: int  # Tokens used this week
```

### QuotaLog (`app/db/models.py`)
Audit trail for quota changes:
```python
class QuotaLog(Base):
    student_id: str
    week_number: int
    tokens_granted: int
    tokens_used: int
    reset_at: datetime
```

## Week Number Calculation
- Based on `semester_start_date` from settings
- Example: `2026-02-17` for Spring 2026
- `get_current_week_number()` in `app/core/utils.py`

## Quota Check Flow
1. Cache service checks in-memory cache first
2. On cache miss, load from database
3. If Redis enabled, use `DistributedQuotaService` for atomic operations
4. Reserve tokens using optimistic locking
5. Return remaining quota or raise `QuotaExceededError`

## Quota Adjustment
Actual token usage may differ from reserved:
- `async_logger` tracks `max_tokens` (reserved) vs `tokens_used` (actual)
- Batch quota adjustments after conversation logging
- Positive adjustment = over-reserved, Negative = under-reserved

## Configuration
```python
# From app/core/config.py
redis_enabled = False  # Enable distributed quota
redis_url = "redis://localhost:6379/0"
quota_sync_interval_seconds = 60
quota_redis_ttl_days = 7

# Student quota (database field)
current_week_quota = 50000  # Per-week token limit
```

## Error Handling
`QuotaExceededError` raised with:
- `remaining`: Remaining quota (0 or negative)
- `reset_week`: Week number when quota resets
- `detail`: Human-readable message

Returns HTTP 429 to client with remaining quota info.
