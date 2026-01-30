# Gateway Middleware Chain

## Middleware Order (Outer → Inner)
FastAPI middleware is executed in reverse order of registration.

```
Request →
  [RequestSizeLimitMiddleware]     # Outermost - executes first
    [MetricsMiddleware]             # Collects metrics
      [RateLimitMiddleware]         # Rate limiting
        [RequestIdMiddleware]       # Innermost - executes last
          → Route Handler ←
        [RequestIdMiddleware]       # Response path
      [RateLimitMiddleware]
    [MetricsMiddleware]
  [RequestSizeLimitMiddleware]
← Response
```

## Individual Middleware

### RequestSizeLimitMiddleware (`app/middleware/request_size.py`)
- **Purpose**: Prevent large payload attacks
- **Limit**: 10MB default (configurable)
- **Action**: Returns HTTP 413 if exceeded

### MetricsMiddleware (`app/api/metrics.py`)
- **Purpose**: Collect request/response metrics
- **Tracks**: Request count, error count, response times
- **Endpoint**: `GET /metrics` returns Prometheus-style metrics

### RateLimitMiddleware (`app/middleware/rate_limit.py`)
- **Purpose**: Prevent API abuse
- **Key**: Hashed API key or IP address (hashed for privacy)
- **Algorithms**:
  - `sliding_window` - Fixed window with sliding
  - `token_bucket` - Token bucket algorithm
- **Backends**:
  - `InMemoryRateLimiter` - Single instance
  - `RedisRateLimiter` - Distributed
- **Response Headers**:
  - `X-RateLimit-Limit`
  - `X-RateLimit-Remaining`
  - `X-RateLimit-Reset`
  - `Retry-After` (on 429)
- **HTTP 429** when limit exceeded

### RequestIdMiddleware (`app/middleware/request_id.py`)
- **Purpose**: Add request tracing ID
- **Header**: `X-Request-ID`
- **Traceparent**: W3C traceparent format for distributed tracing
- **Used in**: All logging for request correlation

### SessionMiddleware (Starlette)
- Added for admin panel support
- Not used in API routes

## Authentication Middleware

### require_api_key (`app/middleware/auth.py`)
FastAPI dependency (not middleware):
- Extracts Bearer token from Authorization header
- Hashes token and looks up in database
- Returns Student object
- Raises HTTP 401 if invalid

### require_admin (`app/middleware/auth.py`)
- Validates ADMIN_TOKEN environment variable
- Uses constant-time comparison (hmac.compare_digest)
- Returns HTTP 401 if invalid

## Error Handling Middleware
Defined in `app/main.py` as exception handlers:
- `QuotaExceededError` → HTTP 429
- `AuthenticationError` → HTTP 401
- `RuleViolationError` → HTTP 400
- Global handler → HTTP 500 (no stack trace in production)

## Configuration
```python
# From app/core/config.py
rate_limit_requests_per_minute = 60
rate_limit_burst_size = 10
rate_limit_window_seconds = 60
rate_limit_fail_closed = False  # Allow requests when Redis unavailable
redis_enabled = False  # Use Redis for distributed rate limiting
```
