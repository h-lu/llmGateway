# Gateway Code Review Report

**Date:** 2026-01-31  
**Commit:** `709cdb87`  
**Repository:** gateway  
**Reviewers:** Claude (Code Review Agent)

---

## Executive Summary

Reviewed the gateway codebase against latest FastAPI, asyncpg, and httpx best practices. Found **12 issues** across 4 severity categories:
- **4 Critical** - Security vulnerabilities and data corruption risks
- **4 High** - Race conditions and DoS vulnerabilities
- **3 Medium** - Configuration inconsistencies
- **1 Low** - Minor improvements

---

## Critical Issues

### 1. Race Condition in Quota Check (CRITICAL)

**File:** `app/services/distributed_quota.py`  
**Lines:** 376-410  
**Severity:** CRITICAL

**Issue:** TOCTOU (Time-Of-Check-Time-Of-Use) race condition allows users to exceed quota by 2-3x through concurrent requests.

```python
# Current code has race window between check and increment
current_val = await redis.get(used_key)
current_used = int(current_val)
remaining = current_week_quota - current_used

if remaining < tokens_needed:
    return False, remaining, current_used

# Race window: another request can consume here
new_val = await redis.incrby(used_key, tokens_needed)
```

**Fix:** Use Redis Lua script for atomic check-and-consume:

```lua
-- Atomic check-and-consume Lua script
local current = redis.call('GET', KEYS[1])
local used = tonumber(current) or 0
local remaining = tonumber(ARGV[1]) - used
if remaining < tonumber(ARGV[2]) then
    return {0, remaining, used}
end
local new_val = redis.call('INCRBY', KEYS[1], ARGV[2])
return {1, remaining - tonumber(ARGV[2]), new_val}
```

**Reference:** [Redis Atomic Operations](https://redis.io/docs/manual/patterns/distributed-locks/)

---

### 2. Truncated Hash Collisions in Rate Limiting (CRITICAL)

**File:** `app/middleware/rate_limit.py`  
**Line:** 515  
**Severity:** CRITICAL

**Issue:** Using only 16 hex characters (64 bits) of SHA-256 hash creates high collision probability.

```python
key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
```

With 64 bits, birthday paradox gives ~50% collision probability after 2^32 entries. Attackers can bypass rate limits through hash collisions.

**Fix:** Use at least 24-32 hex characters:

```python
key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:32]  # 128 bits
```

**Reference:** [app/middleware/rate_limit.py](https://github.com/wangxq/gateway/blob/709cdb87378dd4c69bea157738ed13306c0d442d/app/middleware/rate_limit.py#L510-L516)

---

### 3. Missing Input Validation for API Key Length (CRITICAL)

**File:** `app/middleware/rate_limit.py`  
**Lines:** 510-516  
**Severity:** CRITICAL

**Issue:** No validation of API key length before hashing. Attackers can send extremely long keys (1MB+) to cause DoS via CPU exhaustion.

```python
if auth.startswith("Bearer "):
    api_key = auth[7:].strip()
    # No length check before expensive hash operation
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
```

**Fix:** Add length validation:

```python
if auth.startswith("Bearer "):
    api_key = auth[7:].strip()
    if len(api_key) > 512:  # Reasonable maximum
        raise HTTPException(status_code=400, detail="API key too long")
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:32]
```

---

### 4. Sync Regex Evaluation Without Timeout (CRITICAL)

**File:** `app/services/rule_service.py`  
**Lines:** 495-546  
**Severity:** CRITICAL

**Issue:** The sync `evaluate_prompt()` method uses regex without timeout protection. A single malicious rule can hang the entire server.

```python
def evaluate_prompt(self, prompt: str, week_number: int) -> RuleResult:
    """Note: Sync version does not have regex timeout protection."""
    # No timeout on .search() - vulnerable to ReDoS
    if self._compiled_patterns[rule.id].search(prompt):
```

**Fix:** Either remove sync version or add timeout protection:

```python
# Option 1: Deprecate and redirect to async version
def evaluate_prompt(self, prompt: str, week_number: int) -> RuleResult:
    import warnings
    warnings.warn("Sync evaluate_prompt is deprecated. Use evaluate_prompt_async")
    # Run async version in event loop
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(self.evaluate_prompt_async(prompt, week_number))
```

**Reference:** [app/services/rule_service.py](https://github.com/wangxq/gateway/blob/709cdb87378dd4c69bea157738ed13306c0d442d/app/services/rule_service.py#L495-L546)

---

## High Priority Issues

### 5. Race Condition in Auth Cache (HIGH)

**File:** `app/middleware/auth.py`  
**Lines:** 51-54  
**Severity:** HIGH

**Issue:** API key cache eviction is not atomic:

```python
if len(_api_key_cache) >= _cache_max_size:
    oldest_key = min(_api_key_cache, key=lambda k: _api_key_cache[k][1])
    del _api_key_cache[oldest_key]
```

Multiple coroutines can modify cache simultaneously, causing lost updates.

**Fix:** Use `asyncio.Lock()`:

```python
_api_key_cache_lock = asyncio.Lock()

async def _cache_student(token_hash: str, student: Student) -> None:
    async with _api_key_cache_lock:
        if len(_api_key_cache) >= _cache_max_size:
            oldest_key = min(_api_key_cache, key=lambda k: _api_key_cache[k][1])
            del _api_key_cache[oldest_key]
        _api_key_cache[token_hash] = (student.to_dict(), time.time())
```

---

### 6. Lost Updates During Quota Sync (HIGH)

**File:** `app/services/distributed_quota.py`  
**Lines:** 532-582  
**Severity:** HIGH

**Issue:** Between clearing `pending_syncs` and writing to database, new quota updates can occur and be lost.

**Fix:** Use read-modify-write pattern with proper locking:

```python
async def sync_to_database(self) -> int:
    async with self._sync_lock:
        pending = dict(self._pending_syncs)
        self._pending_syncs.clear()
    
    # Process pending updates...
    # Before clearing, verify no new updates for same student
```

---

### 7. Ineffective Size Limit for Chunked Encoding (HIGH)

**File:** `app/middleware/request_size.py`  
**Lines:** 38-56  
**Severity:** HIGH

**Issue:** Middleware only checks Content-Length header, which can be bypassed using chunked transfer encoding.

```python
# Comment admits limitation:
# "For requests without Content-Length (e.g., chunked encoding),
# the limit will be enforced during body reading by the route handler"
```

Attackers can bypass limit by omitting Content-Length and using chunked encoding.

**Fix:** Stream the body and enforce limits during reading, or use Starlette's built-in request size limiting.

---

### 8. Duplicate Rate Limit Configuration (HIGH)

**File:** `app/core/config.py`  
**Lines:** 39-41 and 84-86  
**Severity:** HIGH

**Issue:** Rate limit settings defined twice with different values:

```python
# Lines 39-41 (intended for stress testing)
rate_limit_requests_per_minute: int = 10000
rate_limit_burst_size: int = 2000

# Lines 84-86 (shadows the above)
rate_limit_requests_per_minute: int = 60  # This wins!
rate_limit_burst_size: int = 10
```

The second definition shadows the first, so stress testing values (10000/2000) are never used.

**Fix:** Remove duplicate at lines 84-86:

```python
# Remove these duplicate definitions:
# rate_limit_requests_per_minute: int = 60
# rate_limit_burst_size: int = 10
```

**Reference:** [app/core/config.py](https://github.com/wangxq/gateway/blob/709cdb87378dd4c69bea157738ed13306c0d442d/app/core/config.py#L39-L86)

---

## Medium Priority Issues

### 9. Excessive Base Pool Size (MEDIUM)

**File:** `app/core/config.py`  
**Line:** 29  
**Severity:** MEDIUM

**Issue:** `db_pool_size: int = 50` is excessive for asyncpg best practices (recommends 10-20).

**Fix:** Reduce to 10-20:

```python
db_pool_size: int = 10  # Warm connections to maintain
db_max_pool_size: int = 50  # Maximum connections
```

**Reference:** [asyncpg Documentation](https://magicstack.github.io/asyncpg/current/connections.html#connection-pools)

---

### 10. Missing max_queries Configuration (MEDIUM)

**File:** `app/db/async_session.py`  
**Lines:** 52-56  
**Severity:** MEDIUM

**Issue:** No `max_queries` limit in connect_args. Connections can accumulate memory bloat from prepared statements.

**Fix:** Add to connect_args:

```python
connect_args = {
    "command_timeout": settings.db_command_timeout,
    "max_cached_statement_lifetime": 0,
    "max_queries": 50000,  # Recycle after 50K queries
    "max_inactive_connection_lifetime": 300.0,  # 5 minutes
}
```

---

### 11. Regex Timeout Too Long (MEDIUM)

**File:** `app/services/rule_service.py`  
**Line:** 23  
**Severity:** MEDIUM

**Issue:** `REGEX_TIMEOUT_SECONDS = 1.0` is too long. With 10 rules evaluating serially, a request could block for 10+ seconds.

**Fix:** Reduce to 50-100ms:

```python
REGEX_TIMEOUT_SECONDS = 0.1  # 100ms maximum
```

---

## Low Priority Issues

### 12. Inconsistent HTTP Client Timeout Usage (LOW)

**File:** `app/core/http_client.py`  
**Lines:** 80-102  
**Severity:** LOW

**Issue:** `create_http_client()` uses simple timeout while `init_http_client()` uses granular timeouts.

**Fix:** Use granular timeouts consistently:

```python
def create_http_client(**kwargs) -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        connect=kwargs.get("connect", settings.httpx_connect_timeout),
        read=kwargs.get("read", settings.httpx_read_timeout),
        write=kwargs.get("write", settings.httpx_write_timeout),
        pool=kwargs.get("pool", settings.httpx_pool_timeout),
    )
    # ...
```

---

## Summary Table

| Severity | Issue | File | Lines |
|----------|-------|------|-------|
| CRITICAL | TOCTOU race in quota check | distributed_quota.py | 376-410 |
| CRITICAL | Hash collision (64-bit) | rate_limit.py | 515 |
| CRITICAL | Missing API key length validation | rate_limit.py | 510-516 |
| CRITICAL | Sync regex without timeout | rule_service.py | 495-546 |
| HIGH | Race condition in auth cache | auth.py | 51-54 |
| HIGH | Lost updates during sync | distributed_quota.py | 532-582 |
| HIGH | Chunked encoding bypass | request_size.py | 38-56 |
| HIGH | Duplicate rate limit config | config.py | 39-41, 84-86 |
| MEDIUM | Excessive pool size (50) | config.py | 29 |
| MEDIUM | Missing max_queries | async_session.py | 52-56 |
| MEDIUM | Regex timeout too long | rule_service.py | 23 |
| LOW | Inconsistent timeout usage | http_client.py | 80-102 |

---

## Positive Findings

The codebase demonstrates several excellent practices:

1. **FastAPI Lifespan** - Modern `@asynccontextmanager` pattern (not deprecated events)
2. **Dependency Injection** - Proper use of `Depends()` throughout
3. **Middleware Order** - Correct onion model ordering
4. **Constant-Time Comparison** - Using `hmac.compare_digest()` in auth
5. **HTTPX Context Manager** - Proper async client lifecycle management

---

## References

- [FastAPI Lifespan Documentation](https://fastapi.tiangolo.com/advanced/events/)
- [asyncpg Connection Pools](https://magicstack.github.io/asyncpg/current/connections.html)
- [httpx Advanced Configuration](https://www.python-httpx.org/advanced/#pool-configuration)
- [Redis Atomic Operations](https://redis.io/docs/manual/patterns/distributed-locks/)

---

**Reviewed with Claude Code** - Generated with [Claude Code](https://claude.ai/code)
