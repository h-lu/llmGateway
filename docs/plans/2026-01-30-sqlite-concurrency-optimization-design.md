# SQLite 高并发优化设计文档

## 问题分析

### 根本原因

1. **SQLite 文件级锁定机制**
   - SQLite 在写入时锁定整个数据库文件
   - 默认超时仅 5 秒，超时后返回 "database is locked" 错误
   - 多个并发写入请求竞争锁，导致大量失败

2. **当前配置问题**
   - 使用 `NullPool`：每个请求新建连接，增加竞争
   - 未启用 WAL (Write-Ahead Logging) 模式
   - 未设置 `busy_timeout` 自动重试机制

### 测试结果对比

| 并发用户 | 优化前成功率 | 主要瓶颈 |
|---------|------------|---------|
| 100 | 1.39% | Provider 未配置 |
| 100 | 9.63% | 速率限制 |
| 50 | 42.86% | SQLite 锁定 |
| 30 | 69.23% | SQLite 锁定 |
| **20** | **96.20%** | **最佳配置** |
| 25 | 82.44% | 轻微竞争 |

---

## 优化方案

### 方案 1: SQLite 参数优化（推荐）

**核心策略**: 启用 WAL 模式 + 增加超时 + 使用单连接池

#### 1.1 启用 WAL (Write-Ahead Logging) 模式

```python
# 连接时执行 PRAGMA
PRAGMA journal_mode = WAL;
```

**效果**:
- 读写并发：允许一个写入者和多个读取者同时进行
- 性能提升：写操作不阻塞读操作
- 恢复更快：崩溃恢复更高效

#### 1.2 设置 busy_timeout

```python
# 连接时执行 PRAGMA
PRAGMA busy_timeout = 30000;  # 30 秒
```

**效果**:
- 自动重试：获取锁失败时自动等待
- 避免立即报错：减少 "database is locked" 错误

#### 1.3 使用 StaticPool

```python
from sqlalchemy.pool import StaticPool

engine = create_async_engine(
    url,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
```

**效果**:
- 单连接复用：所有请求共享一个连接
- 避免连接竞争：减少连接创建开销

#### 1.4 完整引擎配置

```python
def get_async_engine(database_url: str | None = None):
    global _async_engine
    if _async_engine is None:
        url = database_url or settings.database_url
        
        # Convert to async SQLite URL
        if url.startswith("sqlite+pysqlite://"):
            url = url.replace("sqlite+pysqlite://", "sqlite+aiosqlite://", 1)
        elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        
        if "sqlite" in url:
            # SQLite 高并发优化配置
            _async_engine = create_async_engine(
                url,
                echo=False,
                future=True,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30.0,  # 连接超时 30 秒
                },
            )
            
            # 启用 WAL 模式和 busy_timeout
            @event.listens_for(_async_engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.execute("PRAGMA busy_timeout = 30000")  # 30 秒
                cursor.execute("PRAGMA synchronous = NORMAL")  # WAL 模式推荐
                cursor.close()
        else:
            # PostgreSQL 等其他数据库使用连接池
            _async_engine = create_async_engine(
                url,
                echo=False,
                future=True,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_timeout=settings.db_pool_timeout,
                pool_recycle=settings.db_pool_recycle,
            )
    return _async_engine
```

---

### 方案 2: 生产环境迁移 PostgreSQL

**适用场景**: 高并发生产环境

```python
# .env 配置
database_url = "postgresql+asyncpg://user:pass@localhost/teachproxy"
```

**优势**:
- 真正的并发支持：MVCC 实现真正的读写并发
- 行级锁定：写入不阻塞整个表
- 连接池友好：支持真正的连接池

---

## 实施步骤

### Step 1: 修改 async_session.py

1. 导入 `StaticPool` 和 `event`
2. 修改引擎创建逻辑
3. 添加 WAL 模式和 busy_timeout 设置

### Step 2: 测试验证

```bash
# 100 用户高并发测试
python tests/stress/test_multi_user_stress.py --users 100 --duration 60
```

**预期结果**: 成功率 > 90%

### Step 3: 监控指标

- 成功率
- P95/P99 延迟
- 数据库锁定错误数量

---

## 风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| WAL 文件过大 | 中 | 磁盘空间 | 定期 checkpoint |
| 性能回退 | 低 | 响应时间 | 保留回滚方案 |
| 数据一致性 | 低 | 数据完整性 | 充分测试 |

---

## 参考资源

- [SQLAlchemy SQLite Dialect](http://docs.sqlalchemy.org/en/latest/dialects/sqlite.html)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Concurrent Access](https://sqlite.org/lang_transaction.html)
