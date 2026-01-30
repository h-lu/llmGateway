# Gateway Architecture Overview

## Project Purpose
TeachProxy Gateway - AI gateway service with rate limiting, quota management, and rule-based content filtering for educational use.

## Technology Stack
- **Framework**: FastAPI with async/await
- **Database**: SQLAlchemy with async session support (SQLite, extensible to PostgreSQL)
- **Cache**: Optional Redis support for distributed rate limiting and quota management
- **HTTP Client**: httpx with connection pooling
- **Token Counting**: tiktoken for accurate token counting

## Directory Structure
```
gateway/app/
├── main.py              # FastAPI app factory, middleware setup, exception handlers
├── core/                # Core utilities (config, logging, tokenizer, cache, http_client)
├── providers/           # AI provider abstraction (base, factory, loadbalancer, health, retry)
├── db/                  # Database models, async session, CRUD operations
├── services/            # Business logic (quota, rules, conversation, distributed_quota)
├── middleware/          # FastAPI middleware (auth, rate_limit, request_id, request_size)
└── api/                 # Route handlers (chat, metrics, weekly_prompts)
```

## Key Design Patterns
1. **Factory Pattern**: ProviderFactory for creating AI provider instances
2. **Singleton Pattern**: Global instances for factory, load balancer, health checker
3. **Repository Pattern**: CRUD layer abstracting database operations
4. **Middleware Pipeline**: Nested middleware for cross-cutting concerns
5. **Async/Batch Processing**: Async conversation logger with batch writes
6. **Health Checking**: Background health checks for provider failover

## Request Flow
1. RequestSizeLimitMiddleware (10MB limit)
2. MetricsMiddleware (collects metrics)
3. RateLimitMiddleware (per API key or IP)
4. RequestIdMiddleware (adds tracing ID)
5. Route handler (chat_completions)
6. Auth validation → Quota check → Rule evaluation → Provider selection → Response

## Configuration
All settings via environment variables (see `app/core/config.py`):
- Database URL, pool settings
- Provider API keys and URLs
- Rate limiting parameters
- Cache/Redis settings
- Academic calendar (for week-based quotas)

## Database Models
- `Student`: API keys, quota tracking
- `Conversation`: Audit log of all conversations
- `Rule`: Content filtering rules with week ranges
- `WeeklySystemPrompt`: Progressive learning prompts per week
- `QuotaLog`: Quota change history

## Provider Architecture
- Base abstract class defines interface
- Concrete implementations: DeepSeekProvider, OpenAIProvider, MockProvider
- Load balancer with strategies: round_robin, weighted, health_first
- Health checker with background monitoring
- Retry policy with exponential backoff
