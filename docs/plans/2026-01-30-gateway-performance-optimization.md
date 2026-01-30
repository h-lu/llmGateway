# Gateway 性能优化实施计划

> **For Kimi CLI:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于性能评估报告，实施高优先级优化项，提升网关性能和并发能力

**Architecture:** 
1. 分离流式响应数据库会话（避免长事务）
2. 添加 Weekly Prompt 内存缓存（减少 N+1 查询）
3. 优化流式响应缓冲区（减少 syscall）
4. 添加慢查询监控（性能可观测）

**Tech Stack:** FastAPI, SQLAlchemy, SQLite WAL, AsyncIO

---

## Task 1: 流式响应数据库会话分离

**Files:**
- Modify: `gateway/app/api/chat.py:154-328` (handle_streaming_response)
- Modify: `gateway/app/services/async_logger.py` (添加 async 保存方法)

**Step 1: 分析当前问题**

当前流式响应在 `stream_generator()` 内保持数据库会话打开，直到流结束。这会导致：
- 长事务占用数据库连接
- 并发高时连接池耗尽

**Step 2: 修改 handle_streaming_response 函数**

将数据库操作移到流生成器外部，使用后台任务保存：

```python
# 在流开始前收集必要数据
log_data = ConversationLogData(...)

# 流生成器只负责 yield 数据
async def stream_generator():
    ...
    yield data

# 流结束后使用后台任务保存
background_tasks.add_task(async_logger.save_conversation_async, log_data)
```

**Step 3: 验证修改**

Run: `python -c "from gateway.app.api.chat import handle_streaming_response; print('OK')"`
Expected: OK (no import error)

---

## Task 2: Weekly Prompt 内存缓存

**Files:**
- Modify: `gateway/app/services/weekly_prompt_service.py`
- Create: 内存缓存字典和缓存逻辑

**Step 1: 添加内存缓存**

```python
# 模块级别缓存
_weekly_prompt_cache: Dict[int, Optional[WeeklySystemPrompt]] = {}
_cache_lock = asyncio.Lock()

async def get_prompt_for_week_cached(
    session: AsyncSession, 
    week_number: int,
    use_cache: bool = True
) -> Optional[WeeklySystemPrompt]:
    """带缓存的版本"""
    if use_cache and week_number in _weekly_prompt_cache:
        return _weekly_prompt_cache[week_number]
    
    # 缓存未命中，查询数据库
    prompt = await get_prompt_for_week(session, week_number)
    
    async with _cache_lock:
        _weekly_prompt_cache[week_number] = prompt
    
    return prompt
```

**Step 2: 更新 chat.py 使用缓存版本**

```python
weekly_prompt = await weekly_prompt_service.get_prompt_for_week_cached(
    session, week_number
)
```

**Step 3: 验证**

Run: `python -c "from gateway.app.services.weekly_prompt_service import get_prompt_for_week_cached; print('OK')"`
Expected: OK

---

## Task 3: 流式响应缓冲区优化

**Files:**
- Modify: `gateway/app/api/chat.py:193-261` (stream_generator)

**Step 1: 实现缓冲区逻辑**

```python
async def stream_generator():
    buffer = []
    buffer_size = 0
    max_buffer_size = 4096  # 4KB
    
    async for line in provider.stream_chat(payload, traceparent):
        buffer.append(line + "\n\n")
        buffer_size += len(line) + 2
        
        if buffer_size >= max_buffer_size:
            yield "".join(buffer)
            buffer = []
            buffer_size = 0
    
    # 刷新剩余缓冲区
    if buffer:
        yield "".join(buffer)
```

**Step 2: 验证**

Run: 压力测试对比缓冲前后的 RPS
Expected: RPS 提升 10-20%

---

## Task 4: 添加慢查询监控

**Files:**
- Modify: `gateway/app/db/async_session.py`
- Add: SQLAlchemy 事件监听

**Step 1: 添加事件监听**

```python
from sqlalchemy import event
import time

@event.listens_for(_async_engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(_async_engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total_time = time.time() - context._query_start_time
    if total_time > 1.0:  # 超过1秒记录警告
        logger.warning(
            "Slow query detected",
            extra={
                "query_time": round(total_time, 3),
                "query": statement[:200],
            }
        )
```

**Step 2: 验证**

Run: `python -c "from gateway.app.db.async_session import get_async_engine; print('OK')"`
Expected: OK

---

## Task 5: Rate Limit 内存优化

**Files:**
- Modify: `gateway/app/middleware/rate_limit.py:69-150`

**Step 1: 添加 LRU 限制**

```python
from collections import OrderedDict

class InMemoryRateLimiter:
    def __init__(self, max_entries: int = 10000, ...):
        self._max_entries = max_entries
        self._window_storage: OrderedDict[str, RateLimitEntry] = OrderedDict()
        
    def _cleanup_if_needed(self):
        if len(self._window_storage) > self._max_entries:
            # 移除最旧的 20%
            remove_count = int(self._max_entries * 0.2)
            for _ in range(remove_count):
                self._window_storage.popitem(last=False)
```

**Step 2: 验证**

Run: `python -c "from gateway.app.middleware.rate_limit import InMemoryRateLimiter; print('OK')"`
Expected: OK

---

## Task 6: 集成测试验证

**Files:**
- Run: `tests/stress/test_multi_user_stress.py`

**Step 1: 重启网关**

```bash
pkill -f uvicorn
TEACHPROXY_MOCK_PROVIDER=true uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000 &
```

**Step 2: 100 用户压力测试**

```bash
python tests/stress/test_multi_user_stress.py --users 100 --duration 60
```

**Step 3: 验证性能提升**

Expected:
- 成功率 > 99.9% (vs 当前 99.56%)
- RPS > 35 (vs 当前 30.3)
- P95 延迟 < 700ms (vs 当前 763ms)

---

## 执行顺序

1. Task 1: 流式响应数据库会话分离
2. Task 2: Weekly Prompt 内存缓存
3. Task 3: 流式响应缓冲区优化
4. Task 4: 添加慢查询监控
5. Task 5: Rate Limit 内存优化
6. Task 6: 集成测试验证

---

## Rollback Plan

每个 Task 独立可回滚：
- 修改前备份原文件: `cp file.py file.py.backup`
- 如有问题恢复: `mv file.py.backup file.py`

关键文件备份列表：
- gateway/app/api/chat.py
- gateway/app/services/weekly_prompt_service.py
- gateway/app/db/async_session.py
- gateway/app/middleware/rate_limit.py
