# Chat API Request Flow

## Endpoint: `POST /v1/chat/completions`

## Detailed Flow

### 1. Authentication & Authorization
- `require_api_key` dependency extracts Bearer token from Authorization header
- Token is hashed (SHA-256) and looked up in database
- Returns `Student` object with quota information

### 2. Request Parsing
```python
messages = body.get("messages", [])
model = body.get("model", "deepseek")
max_tokens = body.get("max_tokens", 2048)
stream = body.get("stream", False)
```

### 3. Rule Evaluation
- `evaluate_prompt()` checks prompt against database rules
- Rules have week ranges (e.g., "1-2", "3-6")
- Actions: "blocked", "guided" (deprecated), or "allow"
- Blocked requests return immediate response with custom message

### 4. Weekly Prompt Injection
- `get_weekly_prompt_service()` fetches prompt for current week
- System prompt is prepended to messages
- Supports progressive learning guidance

### 5. Quota Check & Reservation
- `check_and_reserve_quota()` uses distributed quota cache
- First checks Redis (if enabled), falls back to database
- Uses optimistic locking to prevent race conditions
- Raises `QuotaExceededError` if insufficient quota

### 6. Provider Selection (with Failover)
- Load balancer selects provider based on strategy
- Up to `MAX_FAILOVER_ATTEMPTS` (default 3) retries on failure
- Failed providers are marked unhealthy immediately

### 7. Request Processing

#### Non-Streaming (`stream=False`)
- `handle_non_streaming_response()` calls provider
- Token counting on response
- Logs conversation asynchronously via background task

#### Streaming (`stream=True`)
- `handle_streaming_response()` uses `provider.stream_chat()`
- Token counting with `TokenCounter` for incremental counting
- SSE buffering (4KB) for efficient transmission
- Error handling: JSON decode errors logged but non-fatal
- Upstream errors return safe error messages (no sensitive data)

### 8. Response
- Includes `X-Request-ID` header for tracing
- Rate limit headers added by middleware
- `traceparent` header for distributed tracing

## Error Handling
- `QuotaExceededError` → HTTP 429 with remaining quota info
- `AuthenticationError` → HTTP 401
- `RuleViolationError` → HTTP 400 with rule details
- Upstream errors → HTTP 502/504/503
- Unhandled exceptions → HTTP 500 (no stack trace in production)

## Async Logging
- `AsyncConversationLogger` buffers logs (default 100 entries)
- Flushes every 5 seconds or when buffer is full
- Dead letter queue at `/tmp/gateway_failed_logs.jsonl` for failures
- Batch inserts with quota adjustments
