# Gateway Architecture Overview

## Project Purpose
TeachProxy Gateway is an AI API gateway service built with FastAPI that provides:
- Rate limiting and quota management
- Multi-provider support (DeepSeek, OpenAI, Mock)
- Rule-based content filtering
- Health checking and failover
- Metrics and observability

## Technology Stack
- **Framework**: FastAPI with async/await
- **Database**: PostgreSQL with asyncpg driver
- **HTTP Client**: httpx with connection pooling
- **Caching**: Redis (optional)
- **Logging**: Structured logging with OpenTelemetry tracing

## Directory Structure

```
app/
├── api/           # API endpoints (chat, metrics, weekly_prompts)
├── core/          # Core utilities (config, http_client, logging, security, cache, tracing)
├── db/            # Database models, sessions, CRUD operations
├── middleware/    # Custom middleware (auth, rate_limit, request_id, request_size)
├── providers/     # Provider implementations and load balancing
└── services/      # Business logic (conversation, quota, rules, distributed_quota)
```

## Application Lifecycle (`app/main.py`)

### Startup Sequence (`lifespan`)
1. Initialize shared HTTP client with connection pooling
2. Verify database connection
3. Initialize database (create tables if needed)
4. Warm up connection pool (20 pre-created connections)
5. Warm rules cache
6. Start provider health checker

### Shutdown Sequence
1. Stop health checker
2. Flush conversation logs
3. Close cache connections (Redis)
4. Close database engine

## Key Configuration (`app/core/config.py`)

### Database Settings
- `db_pool_size`: 50 (base pool size)
- `db_max_overflow`: -1 (unlimited for burst load)
- `db_pool_timeout`: 5 seconds (fail fast)
- `db_pool_recycle`: 1800 seconds (30 minutes)

### HTTP Client Settings
- `httpx_max_connections`: 100
- `httpx_max_keepalive_connections`: 20
- `httpx_timeout`: 60 seconds default

### Rate Limiting
- `rate_limit_requests_per_minute`: 60
- `rate_limit_burst_size`: 10

## Database Models (`app/db/models.py`)

- **Student**: User account with weekly token quota
- **Conversation**: Chat conversation history
- **Rule**: Content filtering rules (regex patterns)
- **WeeklySystemPrompt**: Weekly prompts with date ranges
- **QuotaLog**: Quota usage tracking
