# PostgreSQL 迁移设计文档

**日期**: 2026-01-30
**作者**: Claude
**状态**: 设计中

## 1. 概述

将 TeachProxy 网关从 SQLite 迁移到 PostgreSQL，解决高并发场景下的数据库锁竞争问题。

**背景**:
- 压力测试显示 100 并发用户下 35% 请求失败（HTTP 500）
- SQLite WAL 模式仍无法满足高并发写入需求
- 需要支持生产级别的并发性能

**目标**:
- 支持更高并发（100+ 用户）
- 降低请求失败率至 < 5%
- 保持代码简洁，仅支持 PostgreSQL

## 2. 整体架构

### 2.1 数据库部署

采用 Docker Compose 管理两个 PostgreSQL 实例：

| 服务 | 端口 | 用途 |
|------|------|------|
| teachproxy_db | 5432 | 开发/生产数据库 |
| teachproxy_test | 5433 | pytest 测试数据库 |

### 2.2 连接字符串

```
postgresql+asyncpg://teachproxy:teachproxy123@localhost:5432/teachproxy
```

### 2.3 技术栈

- **PostgreSQL**: 16-alpine (Docker)
- **驱动**: asyncpg 0.29+
- **ORM**: SQLAlchemy 2.0 (async)

## 3. 组件变更

### 3.1 配置文件 (`gateway/app/core/config.py`)

```python
class Settings(BaseSettings):
    # PostgreSQL settings
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "teachproxy"
    db_password: str = "teachproxy123"
    db_name: str = "teachproxy"
    db_test_name: str = "teachproxy_test"

    # Connection pool settings
    db_pool_size: int = 20
    db_max_overflow: int = 40
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    @property
    def database_url(self) -> str:
        """动态构建数据库 URL"""
        if os.getenv("PYTEST_CURRENT_TEST"):
            return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_test_name}"
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
```

### 3.2 数据库引擎 (`gateway/app/db/async_session.py`)

移除 SQLite 特定代码，简化为：

```python
def get_async_engine(database_url: str | None = None):
    global _async_engine
    if _async_engine is None:
        url = database_url or settings.database_url

        _async_engine = create_async_engine(
            url,
            echo=False,
            future=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,
        )
    return _async_engine
```

### 3.3 数据模型 (`gateway/app/db/models.py`)

使用 PostgreSQL 特定类型：

```python
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ
from sqlalchemy import Index

class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        Index('idx_students_email', 'email'),
    )
    # ...

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index('idx_conversations_student_week', 'student_id', 'week_number'),
        Index('idx_conversations_timestamp', 'timestamp'),
    )
    # ...

class WeeklySystemPrompt(Base):
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## 4. Docker Compose 配置

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    container_name: teachproxy_db
    environment:
      POSTGRES_USER: teachproxy
      POSTGRES_PASSWORD: teachproxy123
      POSTGRES_DB: teachproxy
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U teachproxy"]
      interval: 5s
      timeout: 5s
      retries: 5

  postgres_test:
    image: postgres:16-alpine
    container_name: teachproxy_test_db
    environment:
      POSTGRES_USER: teachproxy
      POSTGRES_PASSWORD: teachproxy123
      POSTGRES_DB: teachproxy_test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U teachproxy"]

volumes:
  postgres_data:
```

## 5. 数据库初始化

```python
# gateway/app/db/init_db.py
async def init_database():
    """创建所有数据库表"""
    from gateway.app.db.base import Base
    from gateway.app.db.async_session import get_async_engine

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

# gateway/app/main.py
@app.on_event("startup")
async def startup_event():
    await init_database()
```

## 6. 测试配置

```python
# tests/conftest.py
@pytest.fixture(scope="session", autouse=True)
async def init_test_db():
    os.environ["PYTEST_CURRENT_TEST"] = "true"
    await init_database()
    yield
    await close_async_engine()
```

## 7. 依赖更新

```
# 移除
aiosqlite

# 新增
asyncpg>=0.29.0
```

## 8. 实施步骤

1. **添加 Docker Compose 和依赖**
   - 创建 `docker-compose.yml`
   - 更新 `requirements.txt`
   - 运行 `docker-compose up -d`

2. **修改配置层**
   - 更新 `config.py`
   - 创建 `.env.example`

3. **修改数据库层**
   - 简化 `async_session.py`
   - 更新 `models.py`

4. **更新测试配置**
   - 修改 `conftest.py`
   - 删除 SQLite 相关测试

5. **验证**
   - 运行 pytest
   - 运行压力测试

## 9. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| Docker 依赖 | 提供详细文档 |
| asyncpg 兼容性 | 固定版本 |
| 测试变慢 | 复用连接，健康检查 |
| DateTime 时区 | 统一使用 TIMESTAMPTZ |

## 10. 成功标准

- [ ] 所有 pytest 测试通过
- [ ] 压力测试（100用户，20分钟）成功率 > 95%
- [ ] 平均响应时间 < 200ms
- [ ] 无连接泄漏
- [ ] Docker Compose 一键启动
