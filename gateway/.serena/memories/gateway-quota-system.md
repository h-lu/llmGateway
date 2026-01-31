# Gateway Quota System

## Overview
The quota system manages student token usage with weekly limits and distributed caching for high performance.

## Core Components

### Quota Service (`app/services/quota.py`)

**QuotaState Class**
Dataclass representing quota state:
- `student_id`: Student identifier
- `week_number`: Current academic week (1-16)
- `used_tokens`: Tokens used this week
- `limit`: Weekly token limit

**`apply_usage(student_id: int, input_tokens: int, session)`**
Applies token usage to student quota:
1. Calculates current week from semester start date
2. Gets or creates quota state for week
3. Updates used_tokens count
4. Creates `QuotaLog` entry
5. Returns updated quota state

### Quota Cache (`app/services/quota_cache.py`)

**Purpose:** Cache quota state in Redis for high performance.

**Key Features:**
- TTL-based expiration (7 days default)
- Atomic operations for concurrency safety
- Fallback to database when cache unavailable

**Cache Key Pattern:**
```
quota:{student_id}:{week_number}
```

### Distributed Quota (`app/services/distributed_quota.py`)

**Purpose:** Manage quota synchronization between cache and database.

**Key Functions:**
- `sync_to_database()`: Batch sync Redis quota to PostgreSQL
- `get_quota_from_cache()`: Read quota from Redis
- `set_quota_in_cache()`: Write quota to Redis
- `invalidate_quota()`: Clear cached quota

**Sync Interval:** `quota_sync_interval_seconds` (default: 60s)

## Database Schema

### Student Model
```python
- id: Integer (PK)
- name: String
- weekly_token_limit: Integer  # Maximum tokens per week
- api_key: String (unique)
- created_at: DateTime
- updated_at: DateTime
```

### QuotaLog Model
```python
- id: Integer (PK)
- student_id: Integer (FK)
- week_number: Integer
- tokens_used: Integer
- created_at: DateTime
```

## Week Calculation

The system calculates academic weeks based on:
- `semester_start_date`: Configured in settings
- `semester_weeks`: Total weeks (default: 16)
- Current date automatically determines week number

## Quota Enforcement in Chat API

**Flow:**
1. Request arrives at `/v1/chat/completions`
2. `check_student_quota()` validates weekly limit
3. `check_and_reserve_quota()` applies usage
4. If exceeded, raises `QuotaExceededError`
5. Exception handler returns 403 with error message

## Error Handling

**QuotaExceededError**
```python
{
    "error": "quota_exceeded",
    "message": "Weekly quota exceeded. Used: X, Limit: Y"
}
```

## Configuration

Settings in `app/core/config.py`:
- `quota_sync_interval_seconds`: 60 (sync frequency)
- `quota_redis_ttl_days`: 7 (cache TTL)

## Academic Calendar Integration

Weekly prompts are associated with specific weeks via `WeeklySystemPrompt` model:
- `week_number`: Week of semester (1-16)
- `content`: System prompt for that week
- `start_date`/`end_date`: Date range for validity

This allows quota and prompts to be aligned with the academic schedule.
