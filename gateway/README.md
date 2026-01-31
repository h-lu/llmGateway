# TeachProxy Gateway

A high-performance AI API gateway built with FastAPI, featuring rate limiting, quota management, multi-provider support, and rule-based content filtering.

## Features

- **Multi-Provider Support**: DeepSeek, OpenAI, and Mock providers with automatic failover
- **Load Balancing**: Round-robin, weighted, and health-first strategies
- **Rate Limiting**: Token bucket algorithm with Redis-backed distributed limiting
- **Quota Management**: Weekly token quotas per student with Redis caching
- **Content Filtering**: Regex-based rules engine for blocking and guiding content
- **Health Checking**: Automatic provider health monitoring with recovery
- **Observability**: Structured logging, metrics, and OpenTelemetry tracing
- **High Performance**: Connection pooling, async operations, and warm startup

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Client    │───▶│   Gateway    │───▶│  Providers  │
└─────────────┘    └──────────────┘    └─────────────┘
                         │
                         ▼
                   ┌──────────────┐
                   │  PostgreSQL  │
                   │     Redis    │
                   └──────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| `app/api/` | API endpoints (chat, metrics, weekly prompts) |
| `app/core/` | Configuration, HTTP client, logging, security |
| `app/db/` | Database models, sessions, CRUD operations |
| `app/middleware/` | Auth, rate limiting, request ID, size limits |
| `app/providers/` | Provider implementations and load balancing |
| `app/services/` | Business logic (quota, rules, conversation) |

## Requirements

- Python 3.12+
- PostgreSQL 14+
- Redis 6+ (optional, for distributed rate limiting)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd gateway

# Install dependencies
pip install -e .

# Or using uv
uv pip install -e .
```

## Configuration

Create a `.env` file in the project root:

```bash
# Database
db_host=localhost
db_port=5432
db_user=teachproxy
db_password=teachproxy123
db_name=teachproxy

# Connection Pool (optimized for high concurrency)
db_pool_size=50
db_max_overflow=-1        # -1 = unlimited overflow
db_pool_timeout=5
db_pool_recycle=1800

# DeepSeek API
deepseek_api_key=your-api-key
deepseek_base_url=https://api.deepseek.com/v1

# OpenAI API (optional)
openai_api_key=your-api-key
openai_base_url=https://api.openai.com/v1

# Rate Limiting
rate_limit_requests_per_minute=60
rate_limit_burst_size=10

# Redis (optional)
redis_enabled=false
redis_url=redis://localhost:6379/0

# Academic Calendar
semester_start_date=2026-02-17
semester_weeks=16
```

## Running

```bash
# Development
uvicorn gateway.app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Chat Completions

```bash
POST /v1/chat/completions
Authorization: Bearer <student-api-key>
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "model": "deepseek",
  "stream": false
}
```

### List Models

```bash
GET /v1/models
Authorization: Bearer <student-api-key>
```

### Health Check

```bash
GET /health
```

### Metrics

```bash
GET /metrics
```

## Middleware Chain

Requests flow through middleware in this order:

1. **CORSMiddleware** - CORS handling
2. **MetricsMiddleware** - Request timing and tracking
3. **RequestIdMiddleware** - Unique request ID generation
4. **RateLimitMiddleware** - Token bucket rate limiting
5. **AuthMiddleware** - Student authentication
6. **RequestSizeMiddleware** - Content size validation

## Database Models

| Model | Fields |
|-------|--------|
| **Student** | id, name, weekly_token_limit, api_key |
| **Conversation** | id, student_id, messages, created_at |
| **Rule** | id, name, pattern, rule_type (BLOCK/GUIDE) |
| **WeeklySystemPrompt** | id, week_number, content, start_date, end_date |
| **QuotaLog** | id, student_id, week_number, tokens_used |

## Load Balancing Strategies

| Strategy | Description |
|----------|-------------|
| `ROUND_ROBIN` | Distribute requests evenly across providers |
| `WEIGHTED` | Distribute based on configured weights |
| `HEALTH_FIRST` | Prioritize healthy providers |

## Error Responses

| Code | Error | Description |
|------|-------|-------------|
| 401 | `authentication_error` | Invalid or missing API key |
| 403 | `quota_exceeded` | Weekly quota limit reached |
| 403 | `rule_violation` | Content blocked by rules |
| 429 | `rate_limit_exceeded` | Too many requests |
| 500 | `internal_error` | Server error |

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=gateway --cov-report=html

# Linting
ruff check gateway/
ruff format gateway/
```

## Environment Variables

See `app/core/config.py` for all available configuration options.

## License

MIT
