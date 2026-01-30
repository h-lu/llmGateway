# 每周系统提示词功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现每周可配置的系统提示词功能，替代固定拦截模式，通过定制化的系统提示词引导学生针对性学习，并充分利用 KV 缓存降低 API 成本。

**Architecture:** 扩展数据库模型支持按周配置系统提示词，修改聊天 API 将周系统提示词注入到 messages 列表开头（完全替换模式），保留原有规则引擎作为可选的硬拦截后备机制，利用静态系统提示词前缀实现 KV 缓存优化。

**Tech Stack:** FastAPI, SQLAlchemy, SQLite/PostgreSQL, pytest

---

## 背景与现状

### 当前系统（固定拦截模式）
- `Rule` 模型：基于正则的拦截(block)和引导(guide)规则
- `rule_service.py`：规则引擎，返回 `RuleResult(action="blocked|guided|passed")`
- `chat.py`：根据规则结果决定直接返回拦截消息或在系统消息前插入引导语

### 新功能需求
- 支持按周配置系统提示词
- 完全替换用户的 system message
- 保留硬拦截能力作为后备
- 利用 KV 缓存降低同周请求成本

---

## Task 1: 数据库模型扩展

**Files:**
- Modify: `gateway/app/db/models.py`
- Test: `tests/test_weekly_prompt_model.py`

**Step 1: 编写模型测试**

```python
# tests/test_weekly_prompt_model.py
import pytest
from datetime import datetime
from gateway.app.db.models import WeeklySystemPrompt


def test_weekly_prompt_creation():
    """Test WeeklySystemPrompt model creation."""
    prompt = WeeklySystemPrompt(
        week_start=1,
        week_end=2,
        system_prompt="你是一个编程助教，本周重点学习变量...",
        description="第1-2周：基础概念",
        is_active=True,
    )
    assert prompt.week_start == 1
    assert prompt.week_end == 2
    assert "编程助教" in prompt.system_prompt
    assert prompt.is_active is True


def test_weekly_prompt_week_range_validation():
    """Test week range validation."""
    # Valid: start < end
    prompt = WeeklySystemPrompt(week_start=1, week_end=3)
    assert prompt.week_start <= prompt.week_end
    
    # Valid: single week
    prompt = WeeklySystemPrompt(week_start=5, week_end=5)
    assert prompt.week_start == prompt.week_end


def test_weekly_prompt_is_active_default():
    """Test default is_active is True."""
    prompt = WeeklySystemPrompt(week_start=1, week_end=1)
    assert prompt.is_active is True


def test_weekly_prompt_is_current_week():
    """Test is_current_week helper logic."""
    prompt = WeeklySystemPrompt(week_start=3, week_end=5)
    
    # Week 2: not in range
    assert not (prompt.week_start <= 2 <= prompt.week_end)
    
    # Week 3: in range
    assert prompt.week_start <= 3 <= prompt.week_end
    
    # Week 5: in range
    assert prompt.week_start <= 5 <= prompt.week_end
    
    # Week 6: not in range
    assert not (prompt.week_start <= 6 <= prompt.week_end)
```

**Step 2: 运行测试确认失败**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_model.py -v
```

Expected: FAIL with "WeeklySystemPrompt not defined"

**Step 3: 添加 WeeklySystemPrompt 模型**

```python
# gateway/app/db/models.py
# 在 Rule 类之后添加

class WeeklySystemPrompt(Base):
    """Weekly system prompt configuration.
    
    Allows configuring custom system prompts for specific week ranges
    to guide student learning progressively throughout the course.
    """
    
    __tablename__ = "weekly_system_prompts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    week_end: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<WeeklySystemPrompt(id={self.id}, weeks={self.week_start}-{self.week_end})>"
    
    def is_current_week(self, week_number: int) -> bool:
        """Check if given week number falls within this prompt's range."""
        return self.week_start <= week_number <= self.week_end
```

**Step 4: 运行测试确认通过**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_model.py -v
```

Expected: PASS

**Step 5: 创建数据库迁移（如使用 Alembic）**

```bash
# 如果有 alembic 配置
cd /Users/wangxq/Documents/python && alembic revision --autogenerate -m "add weekly_system_prompts table"
```

如无 Alembic，创建初始化 SQL：

```sql
-- gateway/app/db/migrations/add_weekly_prompts.sql
CREATE TABLE IF NOT EXISTS weekly_system_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start INTEGER NOT NULL,
    week_end INTEGER NOT NULL,
    system_prompt TEXT NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_weekly_prompts_weeks ON weekly_system_prompts(week_start, week_end);
CREATE INDEX idx_weekly_prompts_active ON weekly_system_prompts(is_active);
```

**Step 6: Commit**

```bash
cd /Users/wangxq/Documents/python && git add gateway/app/db/models.py tests/test_weekly_prompt_model.py
git commit -m "feat(db): add WeeklySystemPrompt model for weekly system prompt configuration"
```

---

## Task 2: 数据访问层 (CRUD)

**Files:**
- Create: `gateway/app/db/weekly_prompt_crud.py`
- Modify: `gateway/app/db/crud.py` (re-export)
- Test: `tests/test_weekly_prompt_crud.py`

**Step 1: 编写 CRUD 测试**

```python
# tests/test_weekly_prompt_crud.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.weekly_prompt_crud import (
    get_active_prompt_for_week,
    get_all_weekly_prompts,
    create_weekly_prompt,
)
from gateway.app.db.models import WeeklySystemPrompt


@pytest.mark.asyncio
async def test_get_active_prompt_for_week_found():
    """Test getting active prompt for current week."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    expected_prompt = WeeklySystemPrompt(
        id=1,
        week_start=1,
        week_end=2,
        system_prompt="第1-2周提示词",
        is_active=True,
    )
    mock_result.scalar_one_or_none.return_value = expected_prompt
    mock_session.execute.return_value = mock_result
    
    result = await get_active_prompt_for_week(mock_session, week_number=1)
    
    assert result is not None
    assert result.system_prompt == "第1-2周提示词"
    assert result.week_start == 1


@pytest.mark.asyncio
async def test_get_active_prompt_for_week_not_found():
    """Test when no prompt exists for week."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    result = await get_active_prompt_for_week(mock_session, week_number=99)
    
    assert result is None


@pytest.mark.asyncio
async def test_get_active_prompt_prefers_exact_match():
    """Test that more specific week ranges are preferred."""
    # This tests the ORDER BY logic
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    specific_prompt = WeeklySystemPrompt(
        id=2,
        week_start=3,
        week_end=3,  # 仅第3周
        system_prompt="第3周专用提示词",
        is_active=True,
    )
    mock_result.scalar_one_or_none.return_value = specific_prompt
    mock_session.execute.return_value = mock_result
    
    result = await get_active_prompt_for_week(mock_session, week_number=3)
    
    assert result is not None
    assert "第3周专用" in result.system_prompt
```

**Step 2: 运行测试确认失败**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_crud.py -v
```

Expected: FAIL with module not found

**Step 3: 实现 CRUD 函数**

```python
# gateway/app/db/weekly_prompt_crud.py
"""CRUD operations for WeeklySystemPrompt model."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import WeeklySystemPrompt


async def get_active_prompt_for_week(
    session: AsyncSession, 
    week_number: int
) -> Optional[WeeklySystemPrompt]:
    """Get the active system prompt for a specific week.
    
    If multiple prompts cover this week, returns the one with the narrowest range
    (most specific match first).
    
    Args:
        session: Database session
        week_number: Current week number
        
    Returns:
        WeeklySystemPrompt if found, None otherwise
    """
    stmt = (
        select(WeeklySystemPrompt)
        .where(WeeklySystemPrompt.is_active == True)
        .where(WeeklySystemPrompt.week_start <= week_number)
        .where(WeeklySystemPrompt.week_end >= week_number)
        .order_by(
            # Prefer narrower ranges (more specific matches)
            (WeeklySystemPrompt.week_end - WeeklySystemPrompt.week_start).asc(),
            WeeklySystemPrompt.updated_at.desc()
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_weekly_prompts(
    session: AsyncSession,
    active_only: bool = False
) -> List[WeeklySystemPrompt]:
    """Get all weekly system prompts.
    
    Args:
        session: Database session
        active_only: If True, only return active prompts
        
    Returns:
        List of WeeklySystemPrompt objects
    """
    stmt = select(WeeklySystemPrompt)
    if active_only:
        stmt = stmt.where(WeeklySystemPrompt.is_active == True)
    stmt = stmt.order_by(WeeklySystemPrompt.week_start.asc())
    
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_weekly_prompt(
    session: AsyncSession,
    week_start: int,
    week_end: int,
    system_prompt: str,
    description: Optional[str] = None,
) -> WeeklySystemPrompt:
    """Create a new weekly system prompt.
    
    Args:
        session: Database session
        week_start: Start week number (inclusive)
        week_end: End week number (inclusive)
        system_prompt: The system prompt content
        description: Optional description
        
    Returns:
        Created WeeklySystemPrompt object
    """
    prompt = WeeklySystemPrompt(
        week_start=week_start,
        week_end=week_end,
        system_prompt=system_prompt,
        description=description,
        is_active=True,
    )
    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return prompt


async def update_weekly_prompt(
    session: AsyncSession,
    prompt_id: int,
    **kwargs
) -> Optional[WeeklySystemPrompt]:
    """Update a weekly system prompt.
    
    Args:
        session: Database session
        prompt_id: ID of the prompt to update
        **kwargs: Fields to update
        
    Returns:
        Updated WeeklySystemPrompt if found, None otherwise
    """
    stmt = select(WeeklySystemPrompt).where(WeeklySystemPrompt.id == prompt_id)
    result = await session.execute(stmt)
    prompt = result.scalar_one_or_none()
    
    if prompt is None:
        return None
    
    for key, value in kwargs.items():
        if hasattr(prompt, key):
            setattr(prompt, key, value)
    
    await session.commit()
    await session.refresh(prompt)
    return prompt


async def delete_weekly_prompt(
    session: AsyncSession,
    prompt_id: int
) -> bool:
    """Delete (soft delete by deactivating) a weekly system prompt.
    
    Args:
        session: Database session
        prompt_id: ID of the prompt to delete
        
    Returns:
        True if deleted, False if not found
    """
    stmt = select(WeeklySystemPrompt).where(WeeklySystemPrompt.id == prompt_id)
    result = await session.execute(stmt)
    prompt = result.scalar_one_or_none()
    
    if prompt is None:
        return False
    
    prompt.is_active = False
    await session.commit()
    return True
```

**Step 4: 更新 crud.py re-export**

```python
# gateway/app/db/crud.py
# 在文件末尾添加

from gateway.app.db.weekly_prompt_crud import (
    get_active_prompt_for_week,
    get_all_weekly_prompts,
    create_weekly_prompt,
    update_weekly_prompt,
    delete_weekly_prompt,
)

__all__ = [
    # ... existing exports ...
    "get_active_prompt_for_week",
    "get_all_weekly_prompts",
    "create_weekly_prompt",
    "update_weekly_prompt",
    "delete_weekly_prompt",
]
```

**Step 5: 运行测试确认通过**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_crud.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
cd /Users/wangxq/Documents/python && git add gateway/app/db/weekly_prompt_crud.py gateway/app/db/crud.py tests/test_weekly_prompt_crud.py
git commit -m "feat(db): add CRUD operations for WeeklySystemPrompt"
```

---

## Task 3: 系统提示词服务层

**Files:**
- Create: `gateway/app/services/weekly_prompt_service.py`
- Modify: `gateway/app/services/__init__.py` (re-export)
- Test: `tests/test_weekly_prompt_service.py`

**Step 1: 编写服务测试**

```python
# tests/test_weekly_prompt_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.app.services.weekly_prompt_service import (
    WeeklyPromptService,
    get_weekly_prompt_service,
    inject_weekly_system_prompt,
)
from gateway.app.db.models import WeeklySystemPrompt


class TestWeeklyPromptService:
    """Test WeeklyPromptService."""
    
    @pytest.mark.asyncio
    async def test_get_prompt_for_week_cached(self):
        """Test service returns cached prompt."""
        service = WeeklyPromptService()
        
        # Mock the cache hit
        cached_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="第1-2周提示词",
            is_active=True,
        )
        service._cached_prompt = cached_prompt
        service._cached_week = 1
        
        mock_session = AsyncMock()
        
        result = await service.get_prompt_for_week(mock_session, week_number=1)
        
        assert result == cached_prompt
        # Should not hit database when cached
        mock_session.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_prompt_for_week_db_fetch(self):
        """Test service fetches from DB when not cached."""
        service = WeeklyPromptService()
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        db_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="从数据库获取",
            is_active=True,
        )
        mock_result.scalar_one_or_none.return_value = db_prompt
        mock_session.execute.return_value = mock_result
        
        result = await service.get_prompt_for_week(mock_session, week_number=1)
        
        assert result is not None
        assert result.system_prompt == "从数据库获取"
        # Should be cached now
        assert service._cached_week == 1
        assert service._cached_prompt == db_prompt
    
    @pytest.mark.asyncio
    async def test_get_prompt_for_week_no_config(self):
        """Test when no prompt is configured for the week."""
        service = WeeklyPromptService()
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await service.get_prompt_for_week(mock_session, week_number=99)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_week_change(self):
        """Test cache is invalidated when week changes."""
        service = WeeklyPromptService()
        
        # Set cache for week 1
        service._cached_week = 1
        service._cached_prompt = MagicMock()
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        new_prompt = WeeklySystemPrompt(
            id=2,
            week_start=2,
            week_end=2,
            system_prompt="第2周",
            is_active=True,
        )
        mock_result.scalar_one_or_none.return_value = new_prompt
        mock_session.execute.return_value = mock_result
        
        # Request week 2
        result = await service.get_prompt_for_week(mock_session, week_number=2)
        
        assert result.system_prompt == "第2周"


class TestInjectWeeklySystemPrompt:
    """Test inject_weekly_system_prompt function."""
    
    @pytest.mark.asyncio
    async def test_inject_replaces_system_message(self):
        """Test weekly prompt replaces existing system message."""
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="【每周提示】本周学习变量",
            is_active=True,
        )
        
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "学生问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "【每周提示】本周学习变量"
        assert result[1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_inject_adds_system_message(self):
        """Test weekly prompt is added when no system message exists."""
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="【每周提示】",
            is_active=True,
        )
        
        messages = [
            {"role": "user", "content": "学生问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "【每周提示】"
    
    @pytest.mark.asyncio
    async def test_inject_no_prompt(self):
        """Test messages unchanged when no weekly prompt."""
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "学生问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, None)
        
        assert result == messages
```

**Step 2: 运行测试确认失败**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_service.py -v
```

Expected: FAIL with module not found

**Step 3: 实现服务层**

```python
# gateway/app/services/weekly_prompt_service.py
"""Weekly system prompt service with caching support.

This service manages weekly system prompt retrieval and injection,
optimized for KV cache efficiency by maintaining consistent prompt
prefixes within the same week.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.core.logging import get_logger
from gateway.app.db.models import WeeklySystemPrompt
from gateway.app.db.weekly_prompt_crud import get_active_prompt_for_week

logger = get_logger(__name__)


class WeeklyPromptService:
    """Service for managing weekly system prompts.
    
    Implements in-memory caching for the current week's prompt
    to minimize database queries and maximize consistency.
    
    Cache strategy:
    - Cache the prompt for the current week
    - Invalidate when week number changes
    - Single instance per application (use get_weekly_prompt_service())
    """
    
    def __init__(self):
        self._cached_week: Optional[int] = None
        self._cached_prompt: Optional[WeeklySystemPrompt] = None
    
    async def get_prompt_for_week(
        self,
        session: AsyncSession,
        week_number: int
    ) -> Optional[WeeklySystemPrompt]:
        """Get the system prompt for a specific week.
        
        Uses in-memory caching to avoid repeated DB queries
        for the same week.
        
        Args:
            session: Database session
            week_number: Current week number
            
        Returns:
            WeeklySystemPrompt if configured, None otherwise
        """
        # Check cache
        if self._cached_week == week_number and self._cached_prompt is not None:
            logger.debug(f"Using cached prompt for week {week_number}")
            return self._cached_prompt
        
        # Cache miss or week changed - fetch from DB
        logger.debug(f"Fetching prompt for week {week_number} from database")
        prompt = await get_active_prompt_for_week(session, week_number)
        
        # Update cache
        self._cached_week = week_number
        self._cached_prompt = prompt
        
        if prompt:
            logger.info(
                f"Loaded weekly prompt for week {week_number}",
                extra={
                    "week_number": week_number,
                    "prompt_id": prompt.id,
                    "week_range": f"{prompt.week_start}-{prompt.week_end}",
                }
            )
        else:
            logger.warning(f"No weekly prompt configured for week {week_number}")
        
        return prompt
    
    def invalidate_cache(self) -> None:
        """Invalidate the current cache."""
        self._cached_week = None
        self._cached_prompt = None
        logger.info("Weekly prompt cache invalidated")
    
    def reload(self) -> None:
        """Force reload on next request."""
        self.invalidate_cache()


# Global instance
_weekly_prompt_service: Optional[WeeklyPromptService] = None


def get_weekly_prompt_service() -> WeeklyPromptService:
    """Get the global WeeklyPromptService instance (singleton).
    
    Returns:
        WeeklyPromptService singleton instance
    """
    global _weekly_prompt_service
    if _weekly_prompt_service is None:
        _weekly_prompt_service = WeeklyPromptService()
    return _weekly_prompt_service


async def inject_weekly_system_prompt(
    messages: List[Dict[str, Any]],
    weekly_prompt: Optional[WeeklySystemPrompt]
) -> List[Dict[str, Any]]:
    """Inject weekly system prompt into messages.
    
    Replaces any existing system message with the weekly prompt.
    If no system message exists, adds one at the beginning.
    
    This ensures all students in the same week receive identical
    system prompt prefixes, maximizing KV cache efficiency.
    
    Args:
        messages: Original message list
        weekly_prompt: Weekly system prompt to inject, or None to skip
        
    Returns:
        Modified message list with weekly system prompt
    """
    if weekly_prompt is None:
        return messages
    
    # Create new system message from weekly prompt
    system_message = {
        "role": "system",
        "content": weekly_prompt.system_prompt
    }
    
    # Check if first message is already system
    if messages and messages[0].get("role") == "system":
        # Replace existing system message
        new_messages = [system_message] + messages[1:]
        logger.debug(
            "Replaced existing system message with weekly prompt",
            extra={"prompt_id": weekly_prompt.id}
        )
    else:
        # Add system message at the beginning
        new_messages = [system_message] + messages
        logger.debug(
            "Added weekly prompt as system message",
            extra={"prompt_id": weekly_prompt.id}
        )
    
    return new_messages


async def get_and_inject_weekly_prompt(
    session: AsyncSession,
    messages: List[Dict[str, Any]],
    week_number: int
) -> List[Dict[str, Any]]:
    """Convenience function: get weekly prompt and inject into messages.
    
    Args:
        session: Database session
        messages: Original message list
        week_number: Current week number
        
    Returns:
        Modified message list with weekly system prompt (if configured)
    """
    service = get_weekly_prompt_service()
    weekly_prompt = await service.get_prompt_for_week(session, week_number)
    return await inject_weekly_system_prompt(messages, weekly_prompt)
```

**Step 4: 更新 services/__init__.py**

```python
# gateway/app/services/__init__.py
# 添加 re-export

from gateway.app.services.weekly_prompt_service import (
    WeeklyPromptService,
    get_weekly_prompt_service,
    inject_weekly_system_prompt,
    get_and_inject_weekly_prompt,
)

__all__ = [
    # ... existing exports ...
    "WeeklyPromptService",
    "get_weekly_prompt_service",
    "inject_weekly_system_prompt",
    "get_and_inject_weekly_prompt",
]
```

**Step 5: 运行测试确认通过**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_service.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
cd /Users/wangxq/Documents/python && git add gateway/app/services/weekly_prompt_service.py gateway/app/services/__init__.py tests/test_weekly_prompt_service.py
git commit -m "feat(services): add WeeklyPromptService with caching and injection"
```

---

## Task 4: 修改聊天 API 集成

**Files:**
- Modify: `gateway/app/api/chat.py` (core logic)
- Test: `tests/test_chat_weekly_prompt.py` (integration tests)

**Step 1: 编写集成测试**

```python
# tests/test_chat_weekly_prompt.py
"""Integration tests for weekly system prompt in chat API."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.app.api.chat import chat_completions
from gateway.app.db.models import WeeklySystemPrompt, Student


class TestChatWeeklyPromptIntegration:
    """Test weekly system prompt integration in chat API."""
    
    @pytest.mark.asyncio
    @patch("gateway.app.api.chat.evaluate_prompt_async")
    @patch("gateway.app.api.chat.get_current_week_number")
    @patch("gateway.app.api.chat.get_weekly_prompt_service")
    async def test_chat_uses_weekly_system_prompt(
        self,
        mock_get_service,
        mock_get_week,
        mock_evaluate,
    ):
        """Test that chat API injects weekly system prompt."""
        # Setup mocks
        mock_get_week.return_value = 1
        
        # Mock rule evaluation - passed
        mock_result = MagicMock()
        mock_result.action = "passed"
        mock_result.rule_id = None
        mock_result.message = None
        mock_evaluate.return_value = mock_result
        
        # Mock weekly prompt service
        mock_service = MagicMock()
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="【第1-2周】请引导学生理解变量概念",
            is_active=True,
        )
        mock_service.get_prompt_for_week = AsyncMock(return_value=weekly_prompt)
        mock_get_service.return_value = mock_service
        
        # Mock load balancer
        mock_load_balancer = MagicMock()
        mock_provider = MagicMock()
        mock_provider.chat_completion = AsyncMock(return_value={
            "choices": [{"message": {"content": "AI回复"}}],
            "usage": {"total_tokens": 100}
        })
        mock_load_balancer.get_provider = AsyncMock(return_value=mock_provider)
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "什么是变量？"}],
            "stream": False,
        })
        mock_request.headers = {}
        
        # Mock student
        mock_student = MagicMock(spec=Student)
        mock_student.id = 1
        mock_student.current_week_quota = 10000
        mock_student.used_quota = 0
        
        # Mock other dependencies
        mock_logger = MagicMock()
        mock_logger.log_conversation = MagicMock()
        
        with patch("gateway.app.api.chat.check_and_reserve_quota", new_callable=AsyncMock) as mock_quota, \
             patch("gateway.app.api.chat.get_async_logger", return_value=mock_logger):
            
            mock_quota.return_value = 9000
            
            # Call the endpoint
            response = await chat_completions(
                request=mock_request,
                background_tasks=MagicMock(),
                student=mock_student,
                async_logger=mock_logger,
                load_balancer=mock_load_balancer,
            )
            
            # Verify provider was called with modified messages
            call_args = mock_provider.chat_completion.call_args
            payload = call_args[0][0]
            messages = payload["messages"]
            
            # First message should be the weekly system prompt
            assert messages[0]["role"] == "system"
            assert "【第1-2周】" in messages[0]["content"]
            
            # Second message should be the user question
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "什么是变量？"
    
    @pytest.mark.asyncio
    @patch("gateway.app.api.chat.evaluate_prompt_async")
    @patch("gateway.app.api.chat.get_current_week_number")
    @patch("gateway.app.api.chat.get_weekly_prompt_service")
    async def test_chat_no_weekly_prompt_uses_original(
        self,
        mock_get_service,
        mock_get_week,
        mock_evaluate,
    ):
        """Test that original messages are used when no weekly prompt configured."""
        mock_get_week.return_value = 99  # Week with no prompt
        
        mock_result = MagicMock()
        mock_result.action = "passed"
        mock_evaluate.return_value = mock_result
        
        # No weekly prompt configured
        mock_service = MagicMock()
        mock_service.get_prompt_for_week = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service
        
        mock_load_balancer = MagicMock()
        mock_provider = MagicMock()
        mock_provider.chat_completion = AsyncMock(return_value={
            "choices": [{"message": {"content": "AI回复"}}],
            "usage": {"total_tokens": 100}
        })
        mock_load_balancer.get_provider = AsyncMock(return_value=mock_provider)
        
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "原有系统消息"},
                {"role": "user", "content": "问题"},
            ],
            "stream": False,
        })
        mock_request.headers = {}
        
        mock_student = MagicMock(spec=Student)
        mock_student.id = 1
        mock_student.current_week_quota = 10000
        mock_student.used_quota = 0
        
        mock_logger = MagicMock()
        
        with patch("gateway.app.api.chat.check_and_reserve_quota", new_callable=AsyncMock) as mock_quota, \
             patch("gateway.app.api.chat.get_async_logger", return_value=mock_logger):
            
            mock_quota.return_value = 9000
            
            response = await chat_completions(
                request=mock_request,
                background_tasks=MagicMock(),
                student=mock_student,
                async_logger=mock_logger,
                load_balancer=mock_load_balancer,
            )
            
            # Verify original system message is preserved
            call_args = mock_provider.chat_completion.call_args
            payload = call_args[0][0]
            messages = payload["messages"]
            
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "原有系统消息"
    
    @pytest.mark.asyncio
    @patch("gateway.app.api.chat.evaluate_prompt_async")
    @patch("gateway.app.api.chat.get_current_week_number")
    @patch("gateway.app.api.chat.get_weekly_prompt_service")
    async def test_chat_blocked_rule_takes_precedence(
        self,
        mock_get_service,
        mock_get_week,
        mock_evaluate,
    ):
        """Test that blocked rules still work with weekly prompt feature."""
        mock_get_week.return_value = 1
        
        # Rule blocks the request
        mock_result = MagicMock()
        mock_result.action = "blocked"
        mock_result.rule_id = "rule:direct_answer"
        mock_result.message = "检测到直接要答案，请先自己思考"
        mock_evaluate.return_value = mock_result
        
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "给我这道题的答案"}],
            "stream": False,
        })
        mock_request.headers = {}
        
        mock_student = MagicMock(spec=Student)
        mock_student.id = 1
        
        mock_logger = MagicMock()
        
        with patch("gateway.app.api.chat.get_async_logger", return_value=mock_logger):
            response = await chat_completions(
                request=mock_request,
                background_tasks=MagicMock(),
                student=mock_student,
                async_logger=mock_logger,
                load_balancer=MagicMock(),
            )
            
            # Should return blocked response
            assert response.status_code == 200
            body = response.body.decode()
            assert "blocked" in body
            assert "请先自己思考" in body
```

**Step 2: 运行测试确认失败**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_chat_weekly_prompt.py -v
```

Expected: FAIL (tests fail because implementation not done)

**Step 3: 修改 chat.py 集成每周提示词**

```python
# gateway/app/api/chat.py
# 在 imports 中添加

from gateway.app.services.weekly_prompt_service import (
    get_weekly_prompt_service,
    inject_weekly_system_prompt,
)
```

```python
# gateway/app/api/chat.py
# 修改 chat_completions 函数

@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: Request, 
    background_tasks: BackgroundTasks,
    student: Student = Depends(require_api_key),
    async_logger: AsyncConversationLogger = Depends(get_async_logger),
    load_balancer: LoadBalancer = Depends(get_load_balancer_dependency),
    session: SessionDep = None,
) -> StreamingResponse | JSONResponse:
    """Handle chat completion requests.
    
    This endpoint:
    1. Validates the API key and checks quota
    2. Evaluates the prompt against rules (for blocking)
    3. Loads and injects weekly system prompt
    4. Forwards to the AI provider (with fallback support)
    5. Saves the conversation and updates quota (async via background tasks)
    
    Args:
        request: The incoming request
        background_tasks: FastAPI background tasks for async logging
        student: Authenticated student (from API key)
        async_logger: Async conversation logger instance
        
    Returns:
        StreamingResponse for streaming requests, or JSON response otherwise
        
    Raises:
        HTTPException: Various status codes for different error conditions
    """
    request_id = get_request_id(request)
    
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    
    messages: List[Dict[str, str]] = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="Messages array is required")
    
    prompt = messages[-1].get("content", "") if messages else ""
    
    # Get configuration from request
    model = body.get("model", settings.default_provider)
    max_tokens = body.get("max_tokens", 2048)
    temperature = body.get("temperature", 0.7)
    stream = body.get("stream", False)
    
    # Evaluate against rule engine (for blocking only)
    week_number = get_current_week_number()
    result = evaluate_prompt(prompt, week_number=week_number)
    
    if result.action == "blocked":
        logger.info(
            "Request blocked by rule",
            extra={
                "student_id": student.id,
                "rule_id": result.rule_id,
                "request_id": request_id
            }
        )
        
        # Schedule blocked conversation saving as background task
        log_data = ConversationLogData(
            student_id=student.id,
            prompt=prompt,
            response=result.message or "",
            tokens_used=0,
            action="blocked",
            rule_triggered=result.rule_id,
            week_number=week_number,
            max_tokens=0,
            request_id=request_id,
        )
        async_logger.log_conversation(background_tasks, log_data)
        
        return JSONResponse(
            content=create_blocked_response(result.message or "", result.rule_id),
            headers={"X-Request-ID": request_id}
        )
    
    # Load and inject weekly system prompt
    weekly_prompt_service = get_weekly_prompt_service()
    weekly_prompt = await weekly_prompt_service.get_prompt_for_week(session, week_number)
    modified_messages = await inject_weekly_system_prompt(messages, weekly_prompt)
    
    if weekly_prompt:
        logger.info(
            "Weekly system prompt injected",
            extra={
                "student_id": student.id,
                "week_number": week_number,
                "prompt_id": weekly_prompt.id,
                "request_id": request_id,
            }
        )
    
    # Check and reserve quota (session is managed by get_db() dependency)
    remaining = await check_and_reserve_quota(student, week_number, estimated_tokens=max_tokens, session=session)
    
    # Build payload for upstream
    payload = {
        "model": model,
        "messages": modified_messages,  # Use modified messages with weekly prompt
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    
    # Note: Guide action is deprecated in favor of weekly system prompts
    # Keep for backward compatibility but log a warning
    if result.action == "guided":
        logger.warning(
            "Guide action is deprecated, use weekly system prompts instead",
            extra={
                "student_id": student.id,
                "rule_id": result.rule_id,
                "request_id": request_id
            }
        )
        # Still apply the guide for backward compatibility
        guidance_system = {"role": "system", "content": f"[学习引导] {result.message}"}
        payload["messages"] = [guidance_system] + modified_messages
    
    # Initialize provider with load balancer and failover support
    last_error = None
    
    for attempt in range(MAX_FAILOVER_ATTEMPTS):
        try:
            provider = await load_balancer.get_provider()
            provider_name = getattr(provider, '__class__', None)
            if provider_name:
                provider_name = provider_name.__name__
            else:
                provider_name = "unknown"
            
            logger.info(
                f"Provider selected",
                extra={
                    "request_id": request_id,
                    "provider": provider_name,
                    "attempt": attempt + 1,
                    "strategy": load_balancer.strategy.value
                }
            )
            
            # Get traceparent for distributed tracing
            traceparent = get_traceparent(request)
            
            # Handle streaming vs non-streaming
            if stream:
                return await handle_streaming_response(
                    provider, payload, student, prompt, result,
                    week_number, max_tokens, request_id, model,
                    background_tasks, async_logger, traceparent
                )
            else:
                return await handle_non_streaming_response(
                    provider, payload, student, prompt, result,
                    week_number, max_tokens, request_id, model,
                    background_tasks, async_logger, traceparent
                )
                
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = e
            logger.warning(
                f"Provider failed on attempt {attempt + 1}, trying failover",
                extra={
                    "request_id": request_id,
                    "attempt": attempt + 1,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            # Mark provider as unhealthy for immediate failover
            try:
                provider_name = getattr(provider, '__class__', None)
                if provider_name:
                    provider_name = provider_name.__name__.lower().replace('provider', '')
                    load_balancer._health_checker.mark_unhealthy(provider_name)
            except Exception as mark_error:
                logger.debug(
                    f"Failed to mark provider unhealthy: {mark_error}",
                    extra={"request_id": request_id}
                )
            continue
        except RuntimeError as e:
            error_msg = str(e)
            logger.error(f"No providers available: {e}", extra={"request_id": request_id})
            
            if "No providers registered" in error_msg:
                detail = {
                    "error": "service_unavailable",
                    "message": "AI provider not configured. Please check provider settings."
                }
            elif "No healthy providers" in error_msg:
                detail = {
                    "error": "service_unavailable",
                    "message": "All AI providers are currently unhealthy. Please try again later."
                }
            else:
                detail = {
                    "error": "service_unavailable",
                    "message": "AI service temporarily unavailable. Please try again later."
                }
            raise HTTPException(status_code=503, detail=detail)
    
    # All failover attempts exhausted
    logger.error(
        f"All providers failed after {MAX_FAILOVER_ATTEMPTS} attempts",
        extra={
            "request_id": request_id,
            "last_error": str(last_error),
            "error_type": type(last_error).__name__ if last_error else None
        }
    )
    raise HTTPException(
        status_code=503,
        detail={
            "error": "service_unavailable",
            "message": "All AI providers are unavailable. Please try again later."
        }
    )
```

**Step 4: 运行测试确认通过**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_chat_weekly_prompt.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
cd /Users/wangxq/Documents/python && git add gateway/app/api/chat.py tests/test_chat_weekly_prompt.py
git commit -m "feat(api): integrate weekly system prompt into chat completions"
```

---

## Task 5: 管理 API 端点（可选但推荐）

**Files:**
- Create: `gateway/app/api/weekly_prompts.py`
- Modify: `gateway/app/main.py` (include router)
- Test: `tests/test_api_weekly_prompts.py`

**说明：** 这些端点允许管理员动态配置每周系统提示词，无需直接操作数据库。

**Step 1: 创建 API 路由**

```python
# gateway/app/api/weekly_prompts.py
"""Admin API endpoints for managing weekly system prompts."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from gateway.app.db.dependencies import SessionDep
from gateway.app.db.models import WeeklySystemPrompt
from gateway.app.db.weekly_prompt_crud import (
    get_all_weekly_prompts,
    create_weekly_prompt,
    update_weekly_prompt,
    delete_weekly_prompt,
)
from gateway.app.core.logging import get_logger
from gateway.app.services.weekly_prompt_service import get_weekly_prompt_service

router = APIRouter(prefix="/admin/weekly-prompts", tags=["admin"])
logger = get_logger(__name__)


class WeeklyPromptCreate(BaseModel):
    """Schema for creating a weekly system prompt."""
    week_start: int = Field(..., ge=1, le=52, description="Start week (1-52)")
    week_end: int = Field(..., ge=1, le=52, description="End week (1-52)")
    system_prompt: str = Field(..., min_length=10, description="System prompt content")
    description: Optional[str] = Field(None, max_length=255, description="Optional description")
    
    @field_validator("week_end")
    @classmethod
    def validate_week_range(cls, week_end: int, info) -> int:
        week_start = info.data.get("week_start")
        if week_start is not None and week_end < week_start:
            raise ValueError("week_end must be >= week_start")
        return week_end


class WeeklyPromptUpdate(BaseModel):
    """Schema for updating a weekly system prompt."""
    week_start: Optional[int] = Field(None, ge=1, le=52)
    week_end: Optional[int] = Field(None, ge=1, le=52)
    system_prompt: Optional[str] = Field(None, min_length=10)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class WeeklyPromptResponse(BaseModel):
    """Schema for weekly prompt response."""
    id: int
    week_start: int
    week_end: int
    system_prompt: str
    description: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[WeeklyPromptResponse])
async def list_weekly_prompts(
    session: SessionDep,
    active_only: bool = False,
) -> List[WeeklySystemPrompt]:
    """List all weekly system prompts."""
    prompts = await get_all_weekly_prompts(session, active_only=active_only)
    return prompts


@router.post("", response_model=WeeklyPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    data: WeeklyPromptCreate,
    session: SessionDep,
) -> WeeklySystemPrompt:
    """Create a new weekly system prompt."""
    prompt = await create_weekly_prompt(
        session=session,
        week_start=data.week_start,
        week_end=data.week_end,
        system_prompt=data.system_prompt,
        description=data.description,
    )
    
    # Invalidate cache so new prompt is used immediately
    get_weekly_prompt_service().invalidate_cache()
    
    logger.info(
        f"Created weekly prompt for weeks {data.week_start}-{data.week_end}",
        extra={"prompt_id": prompt.id}
    )
    return prompt


@router.put("/{prompt_id}", response_model=WeeklyPromptResponse)
async def update_prompt(
    prompt_id: int,
    data: WeeklyPromptUpdate,
    session: SessionDep,
) -> WeeklySystemPrompt:
    """Update a weekly system prompt."""
    update_data = data.model_dump(exclude_unset=True)
    
    prompt = await update_weekly_prompt(session, prompt_id, **update_data)
    
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Weekly prompt {prompt_id} not found"
        )
    
    # Invalidate cache
    get_weekly_prompt_service().invalidate_cache()
    
    logger.info(f"Updated weekly prompt {prompt_id}")
    return prompt


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: int,
    session: SessionDep,
) -> None:
    """Deactivate (soft delete) a weekly system prompt."""
    success = await delete_weekly_prompt(session, prompt_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Weekly prompt {prompt_id} not found"
        )
    
    # Invalidate cache
    get_weekly_prompt_service().invalidate_cache()
    
    logger.info(f"Deactivated weekly prompt {prompt_id}")
```

**Step 2: 在主应用中添加路由**

```python
# gateway/app/main.py
# 在 imports 中添加
from gateway.app.api.weekly_prompts import router as weekly_prompts_router

# 在 app.include_router 部分添加
app.include_router(weekly_prompts_router)
```

**Step 3: Commit**

```bash
cd /Users/wangxq/Documents/python && git add gateway/app/api/weekly_prompts.py gateway/app/main.py
git commit -m "feat(api): add admin endpoints for managing weekly system prompts"
```

---

## Task 6: 初始数据填充（示例配置）

**Files:**
- Create: `gateway/app/db/seeds/weekly_prompts.sql`

**Step 1: 创建示例配置**

```sql
-- gateway/app/db/seeds/weekly_prompts.sql
-- 示例：编程课程的每周系统提示词配置

-- 第1-2周：基础概念建立期
INSERT INTO weekly_system_prompts (week_start, week_end, system_prompt, description, is_active)
VALUES (
    1,
    2,
    '你是学生的编程学习伙伴。本周学习重点是变量和数据类型。

【本周目标】
- 理解变量是"存储数据的容器"
- 掌握基本数据类型：int, float, string, bool

【引导策略】
1. 当学生问代码问题时，先问："你认为这个变量应该存什么类型的数据？"
2. 鼓励学生用自然语言描述逻辑，再转化为代码
3. 如果学生直接要答案，请说："我可以帮你，但先告诉我你卡在哪一步了？"

【禁止行为】
- 不要直接写出完整代码
- 优先用比喻和例子解释概念',
    '第1-2周：基础概念建立期',
    1
);

-- 第3-4周：逻辑思维培养期
INSERT INTO weekly_system_prompts (week_start, week_end, system_prompt, description, is_active)
VALUES (
    3,
    4,
    '你是学生的编程教练。本周学习重点是条件语句和循环。

【本周目标】
- 培养"如果...那么..."的逻辑思维
- 理解循环的用途和执行流程

【引导策略】
1. 要求学生先画流程图或用伪代码描述思路
2. 用生活中的例子类比（如"过马路看红绿灯"）
3. 当学生犯错时，引导："让我们一步步跟踪变量的值..."

【苏格拉底式提问】
- "如果输入是X，输出会是什么？"
- "这个条件在什么情况下为假？"
- "你能用另一种方式实现同样的功能吗？"',
    '第3-4周：逻辑思维培养期',
    1
);

-- 第5-6周：独立解决问题期
INSERT INTO weekly_system_prompts (week_start, week_end, system_prompt, description, is_active)
VALUES (
    5,
    6,
    '你是学生的编程顾问。本周学习重点是函数和模块化。

【本周目标】
- 学会将大问题分解为小问题
- 理解函数封装的意义

【引导策略】
1. 鼓励学生先自己尝试 10 分钟，再寻求帮助
2. 只提供思路提示，不给出具体实现
3. 要求学生解释他们的代码为什么这样写

【本周特别要求】
- 学生必须先说明"这个功能应该接收什么参数，返回什么结果"
- 如果学生直接给代码，请反问："这个函数的作用是什么？"',
    '第5-6周：独立解决问题期',
    1
);

-- 第7-8周：综合应用期
INSERT INTO weekly_system_prompts (week_start, week_end, system_prompt, description, is_active)
VALUES (
    7,
    8,
    '你是学生的代码审查员。本周学习重点是综合运用和调试技能。

【本周目标】
- 能够独立调试错误
- 理解代码质量和可读性

【引导策略】
1. 学生提问时，先让他们用自己的话描述 bug 现象
2. 教授调试技巧：print 调试、二分法定位错误
3. 讨论代码优化："这段代码还能更简洁吗？"

【自主探索鼓励】
- "这个问题有多种解决方案，你想探索一下吗？"
- "如果你能修改一个条件，结果会怎样？"',
    '第7-8周：综合应用期',
    1
);
```

**Step 2: Commit**

```bash
cd /Users/wangxq/Documents/python && git add gateway/app/db/seeds/weekly_prompts.sql
git commit -m "chore(db): add sample weekly system prompt configurations"
```

---

## Task 7: 运行全部测试并验证

**Step 1: 运行所有相关测试**

```bash
cd /Users/wangxq/Documents/python && pytest tests/test_weekly_prompt_model.py tests/test_weekly_prompt_crud.py tests/test_weekly_prompt_service.py tests/test_chat_weekly_prompt.py -v
```

Expected: ALL PASS

**Step 2: 运行原有测试确保没有破坏**

```bash
cd /Users/wangxq/Documents/python && pytest tests/ -v --ignore=tests/test_*.py::Test*WeeklyPrompt* 2>/dev/null || pytest tests/ -v -k "not weekly"
```

Expected: Existing tests still pass

**Step 3: Commit 最终版本**

```bash
cd /Users/wangxq/Documents/python && git add -A
git commit -m "feat: complete weekly system prompt feature implementation

- Add WeeklySystemPrompt model for week-based configuration
- Add CRUD operations for prompt management
- Add WeeklyPromptService with caching support
- Integrate into chat completions API (replacing system message)
- Add admin API endpoints for prompt management
- Include sample configurations for 8-week course
- Maintain backward compatibility with rule-based blocking

KV Cache Optimization:
- Static weekly prompts as message prefix maximize cache hits
- All students in same week share identical system prompt
- In-memory service cache reduces DB queries"
```

---

## 实现要点总结

### KV 缓存优化

```
每周系统提示词作为静态前缀 → 同周所有请求共享 → 缓存命中率高

【缓存层级】
1. LLM Provider KV Cache: 同周同提示词共享
2. WeeklyPromptService Cache: 内存缓存当前周提示词
3. Database: 持久化存储配置
```

### 教育引导策略演进

```
旧模式: 拦截/引导 → 学生感受被拒绝 → 体验差
新模式: 系统提示词 → LLM 智能引导 → 体验好 + 效果佳
```

### 向后兼容性

```
- Rule 拦截仍然有效（安全第一）
- Guide 规则保留但记录弃用警告
- 无配置时保持原有行为
```

---

**计划已完成并保存到 `docs/plans/2026-01-29-weekly-system-prompt.md`。**

**两种执行选项：**

**1. Subagent-Driven (当前会话)** - 我为每个 Task 分派子代理，逐任务执行并审核，快速迭代

**2. Parallel Session (独立会话)** - 开启新会话执行计划

**选择哪种方式？**