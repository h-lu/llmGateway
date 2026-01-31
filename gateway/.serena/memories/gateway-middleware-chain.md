# Gateway Middleware Chain

## Middleware Execution Order

The middleware is applied in the following order (from outer to inner):

```
Request
    │
    ▼
┌─────────────────────────────────┐
│ 1. SessionMiddleware            │ ← FastAPI built-in
│    - Session management         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 2. CORSMiddleware               │ ← FastAPI built-in
│    - CORS headers               │
│    - Origin validation          │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 3. MetricsMiddleware            │ ← app/api/metrics.py
│    - Request timing             │
│    - Status code tracking       │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 4. RequestIdMiddleware          │ ← app/middleware/request_id.py
│    - Generate unique request ID │
│    - Add to response headers    │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 5. RateLimitMiddleware          │ ← app/middleware/rate_limit.py
│    - Token bucket rate limiting │
│    - Redis-backed (optional)    │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 6. AuthMiddleware               │ ← app/middleware/auth.py
│    - Student authentication     │
│    - API key validation         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 7. RequestSizeMiddleware        │ ← app/middleware/request_size.py
│    - Content size validation    │
│    - Max size enforcement       │
└─────────────────────────────────┘
    │
    ▼
Route Handler
```

## Middleware Details

### RequestIdMiddleware (`app/middleware/request_id.py`)

**Purpose:** Assign unique identifiers to requests for tracing.

**Features:**
- Generates UUID for each request
- Adds `X-Request-ID` header to response
- Logs request ID for correlation

### RateLimitMiddleware (`app/middleware/rate_limit.py`)

**Purpose:** Token bucket rate limiting algorithm.

**Configuration:**
- `rate_limit_requests_per_minute`: Requests per minute
- `rate_limit_burst_size`: Burst capacity
- `rate_limit_fail_closed`: Deny when Redis unavailable

**Behavior:**
- Redis-backed for distributed rate limiting
- Falls back to in-memory if Redis disabled
- Returns 429 Too Many Requests when exceeded

### AuthMiddleware (`app/middleware/auth.py`)

**Purpose:** Authenticate and authorize students.

**Features:**
- Extracts student ID from headers/API key
- Validates student exists in database
- Attaches student to request state
- Raises `AuthenticationError` on failure

### RequestSizeMiddleware (`app/middleware/request_size.py`)

**Purpose:** Prevent oversized requests.

**Features:**
- Checks Content-Length header
- Validates against maximum size
- Returns 413 Payload Too Large when exceeded

### MetricsMiddleware (`app/api/metrics.py`)

**Purpose:** Track request metrics.

**Tracks:**
- Request count by endpoint
- Response time percentiles
- Status code distribution
- Active request count

## Configuration

Middleware is configured in `app/main.py` within `create_app()`:

```python
app.add_middleware(SessionMiddleware, secret_key=...)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestSizeMiddleware)
```

## Custom Exceptions

Middleware raises specific exceptions:
- `AuthenticationError`: Auth failures
- `QuotaExceededError`: Quota limit exceeded
- `RuleViolationError`: Content rule violation

These are caught by exception handlers in `app/main.py`.
