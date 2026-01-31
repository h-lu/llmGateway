# Gateway Chat API Flow

## API Endpoint (`app/api/chat.py`)

### Main Endpoint: `POST /v1/chat/completions`

**Request Models:**
- `ChatRequest`: Incoming chat request with validation
  - `messages`: List of chat messages
  - `model`: Model identifier
  - `stream`: Enable streaming response
  - `validate_messages()`: Custom validator

**Response Models:**
- `ChatMessage`: Standard chat message format

### Flow Diagram

```
Request
    │
    ▼
┌─────────────────────────────┐
│ 1. Validate Request         │
│    - Parse messages         │
│    - Check model validity   │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 2. Check Student Quota      │ ← get_load_balancer_dependency()
│    - Get student from DB    │
│    - Check weekly quota     │
│    - Reserve tokens         │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 3. Check & Reserve Quota    │ ← check_and_reserve_quota()
│    - Apply usage count      │
│    - Log to QuotaLog        │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 4. Evaluate Content Rules   │
│    - Check block patterns   │
│    - Check guide patterns   │
└─────────────────────────────┘
    │
    ├─ BLOCKED ─► create_blocked_response()
    │
    ▼ ALLOWED
┌─────────────────────────────┐
│ 5. Route to Provider        │
│    - Get from load balancer │
│    - Handle streaming/non-   │
│      streaming              │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 6. Handle Response          │
│  - Streaming: generator     │
│  - Non-streaming: full resp │
└─────────────────────────────┘
    │
    ▼
Response
```

### Key Functions

**`check_student_quota(student_id: int)`**
- Retrieves student from database
- Checks `weekly_token_limit` vs used tokens
- Raises `QuotaExceededError` if over limit

**`check_and_reserve_quota(student_id: int, input_tokens: int)`**
- Applies usage via `apply_usage()` from `app/services/quota.py`
- Creates `QuotaLog` entry

**`handle_streaming_response()`**
- Generator function for SSE streaming
- Handles failover on provider errors
- Max failover attempts: `MAX_FAILOVER_ATTEMPTS`

**`handle_non_streaming_response()`**
- Waits for complete response
- Similar failover logic

**`create_blocked_response(rule_violation: str)`**
- Returns formatted block response
- Includes rule violation message

### Error Handlers

- `quota_exceeded_handler`: Catches `QuotaExceededError`
- `auth_error_handler`: Catches `AuthenticationError`
- `rule_violation_handler`: Catches `RuleViolationError`
- `global_exception_handler`: Catches all other exceptions

### Dependencies

- `get_load_balancer_dependency()`: FastAPI dependency for load balancer
- Database session for student/quota queries
- Rule service for content evaluation
