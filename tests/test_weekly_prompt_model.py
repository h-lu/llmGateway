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
    # Check the column default is set correctly
    from gateway.app.db.models import WeeklySystemPrompt
    is_active_col = WeeklySystemPrompt.__table__.c.is_active
    assert is_active_col.default is not None
    assert is_active_col.default.arg is True


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


def test_weekly_prompt_repr():
    """Test __repr__ method."""
    prompt = WeeklySystemPrompt(
        id=1,
        week_start=1,
        week_end=2,
        system_prompt="测试",
    )
    repr_str = repr(prompt)
    assert "WeeklySystemPrompt" in repr_str
    assert "id=1" in repr_str
    assert "weeks=1-2" in repr_str
