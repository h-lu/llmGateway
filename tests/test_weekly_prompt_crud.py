# tests/test_weekly_prompt_crud.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.weekly_prompt_crud import (
    get_active_prompt_for_week,
    get_all_weekly_prompts,
    create_weekly_prompt,
    update_weekly_prompt,
    delete_weekly_prompt,
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
async def test_get_all_weekly_prompts():
    """Test getting all weekly prompts."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    prompts = [
        WeeklySystemPrompt(id=1, week_start=1, week_end=2, system_prompt="第1-2周", is_active=True),
        WeeklySystemPrompt(id=2, week_start=3, week_end=4, system_prompt="第3-4周", is_active=True),
    ]
    mock_result.scalars.return_value.all.return_value = prompts
    mock_session.execute.return_value = mock_result
    
    result = await get_all_weekly_prompts(mock_session)
    
    assert len(result) == 2
    assert result[0].week_start == 1
    assert result[1].week_start == 3


@pytest.mark.asyncio
async def test_get_all_weekly_prompts_active_only():
    """Test getting only active weekly prompts."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    prompts = [
        WeeklySystemPrompt(id=1, week_start=1, week_end=2, system_prompt="活跃", is_active=True),
    ]
    mock_result.scalars.return_value.all.return_value = prompts
    mock_session.execute.return_value = mock_result
    
    result = await get_all_weekly_prompts(mock_session, active_only=True)
    
    assert len(result) == 1


@pytest.mark.asyncio
async def test_create_weekly_prompt():
    """Test creating a new weekly prompt."""
    mock_session = AsyncMock(spec=AsyncSession)
    
    result = await create_weekly_prompt(
        mock_session,
        week_start=5,
        week_end=6,
        system_prompt="第5-6周提示词",
        description="描述",
    )
    
    assert result.week_start == 5
    assert result.week_end == 6
    assert result.system_prompt == "第5-6周提示词"
    assert result.description == "描述"
    assert result.is_active is True
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_weekly_prompt():
    """Test updating a weekly prompt."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    existing_prompt = WeeklySystemPrompt(
        id=1,
        week_start=1,
        week_end=2,
        system_prompt="原提示词",
        is_active=True,
    )
    mock_result.scalar_one_or_none.return_value = existing_prompt
    mock_session.execute.return_value = mock_result
    
    result = await update_weekly_prompt(
        mock_session,
        prompt_id=1,
        system_prompt="更新后的提示词",
    )
    
    assert result is not None
    assert result.system_prompt == "更新后的提示词"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_weekly_prompt_not_found():
    """Test updating a non-existent weekly prompt."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    result = await update_weekly_prompt(
        mock_session,
        prompt_id=999,
        system_prompt="新提示词",
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_delete_weekly_prompt():
    """Test soft-deleting (deactivating) a weekly prompt."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    
    existing_prompt = WeeklySystemPrompt(
        id=1,
        week_start=1,
        week_end=2,
        system_prompt="提示词",
        is_active=True,
    )
    mock_result.scalar_one_or_none.return_value = existing_prompt
    mock_session.execute.return_value = mock_result
    
    result = await delete_weekly_prompt(mock_session, prompt_id=1)
    
    assert result is True
    assert existing_prompt.is_active is False
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_weekly_prompt_not_found():
    """Test deleting a non-existent weekly prompt."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    result = await delete_weekly_prompt(mock_session, prompt_id=999)
    
    assert result is False
