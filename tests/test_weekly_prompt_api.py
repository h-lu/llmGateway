"""API integration tests for weekly system prompt endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from gateway.app.main import app
from gateway.app.db.models import WeeklySystemPrompt
from gateway.app.services.weekly_prompt_service import get_weekly_prompt_service, reset_weekly_prompt_service


@pytest.fixture
async def client():
    """Provide HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache before each test."""
    reset_weekly_prompt_service()
    yield


class TestCreatePrompt:
    """Test POST /admin/weekly-prompts endpoint."""
    
    @pytest.mark.asyncio
    async def test_create_prompt_success(self, client):
        """Test creating a weekly prompt returns 201 with correct data."""
        response = await client.post("/admin/weekly-prompts", json={
            "week_start": 1,
            "week_end": 2,
            "system_prompt": "你是一个Python助教，本周学习基础概念",
            "description": "第1-2周：基础概念"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["week_start"] == 1
        assert data["week_end"] == 2
        assert "Python助教" in data["system_prompt"]
        assert data["description"] == "第1-2周：基础概念"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    @pytest.mark.asyncio
    async def test_create_prompt_validation_error_week_range(self, client):
        """Test validation fails when week_end < week_start."""
        response = await client.post("/admin/weekly-prompts", json={
            "week_start": 5,
            "week_end": 3,  # Invalid: less than week_start
            "system_prompt": "测试提示词",
            "description": "测试"
        })
        
        assert response.status_code == 422
        data = response.json()
        assert "week_end" in str(data["detail"])
    
    @pytest.mark.asyncio
    async def test_create_prompt_validation_error_week_out_of_range(self, client):
        """Test validation fails when week number > 52."""
        response = await client.post("/admin/weekly-prompts", json={
            "week_start": 1,
            "week_end": 53,  # Invalid: > 52
            "system_prompt": "测试提示词",
        })
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_prompt_validation_error_short_content(self, client):
        """Test validation fails when system_prompt < 10 chars."""
        response = await client.post("/admin/weekly-prompts", json={
            "week_start": 1,
            "week_end": 1,
            "system_prompt": "太短",  # Invalid: < 10 chars
        })
        
        assert response.status_code == 422


class TestListPrompts:
    """Test GET /admin/weekly-prompts endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_prompts(self, client):
        """Test listing all prompts returns created items."""
        # Create a prompt first
        await client.post("/admin/weekly-prompts", json={
            "week_start": 1,
            "week_end": 2,
            "system_prompt": "测试提示词内容",
        })
        
        response = await client.get("/admin/weekly-prompts")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["week_start"] == 1
    
    @pytest.mark.asyncio
    async def test_list_prompts_active_only(self, client):
        """Test filtering active prompts only."""
        # Create then delete (soft delete) a prompt
        create_resp = await client.post("/admin/weekly-prompts", json={
            "week_start": 3,
            "week_end": 4,
            "system_prompt": "将被删除的提示词",
        })
        prompt_id = create_resp.json()["id"]
        
        await client.delete(f"/admin/weekly-prompts/{prompt_id}")
        
        # Get all prompts
        all_resp = await client.get("/admin/weekly-prompts")
        all_count = len(all_resp.json())
        
        # Get active only
        active_resp = await client.get("/admin/weekly-prompts?active_only=true")
        active_count = len(active_resp.json())
        
        assert active_count < all_count


class TestUpdatePrompt:
    """Test PUT /admin/weekly-prompts/{id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_update_prompt_success(self, client):
        """Test updating a prompt returns updated data."""
        # Create first
        create_resp = await client.post("/admin/weekly-prompts", json={
            "week_start": 1,
            "week_end": 1,
            "system_prompt": "原始提示词内容",
        })
        prompt_id = create_resp.json()["id"]
        
        # Update
        response = await client.put(f"/admin/weekly-prompts/{prompt_id}", json={
            "system_prompt": "更新后的提示词内容",
            "description": "添加描述"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["system_prompt"] == "更新后的提示词内容"
        assert data["description"] == "添加描述"
        assert data["week_start"] == 1  # Unchanged
    
    @pytest.mark.asyncio
    async def test_update_prompt_not_found(self, client):
        """Test updating non-existent prompt returns 404."""
        response = await client.put("/admin/weekly-prompts/99999", json={
            "system_prompt": "更新后的提示词内容",
        })
        
        assert response.status_code == 404


class TestDeletePrompt:
    """Test DELETE /admin/weekly-prompts/{id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_delete_prompt_success(self, client):
        """Test soft deleting a prompt returns 204."""
        # Create first
        create_resp = await client.post("/admin/weekly-prompts", json={
            "week_start": 5,
            "week_end": 6,
            "system_prompt": "将被删除的提示词",
        })
        prompt_id = create_resp.json()["id"]
        
        # Delete
        response = await client.delete(f"/admin/weekly-prompts/{prompt_id}")
        
        assert response.status_code == 204
        
        # Verify soft delete (should not appear in active list)
        list_resp = await client.get("/admin/weekly-prompts?active_only=true")
        prompts = list_resp.json()
        assert not any(p["id"] == prompt_id for p in prompts)
    
    @pytest.mark.asyncio
    async def test_delete_prompt_not_found(self, client):
        """Test deleting non-existent prompt returns 404."""
        response = await client.delete("/admin/weekly-prompts/99999")
        
        assert response.status_code == 404


class TestCacheInvalidation:
    """Test cache invalidation on write operations."""
    
    @pytest.mark.asyncio
    async def test_create_prompt_invalidates_cache(self, client):
        """Test creating prompt invalidates service cache."""
        # Pre-populate cache
        service = get_weekly_prompt_service()
        service._cached_week = 1
        service._cached_prompt = MagicMock()
        service._cache_valid = True
        
        # Create new prompt for same week
        await client.post("/admin/weekly-prompts", json={
            "week_start": 1,
            "week_end": 1,
            "system_prompt": "新的提示词内容",
        })
        
        # Cache should be invalidated
        assert service._cache_valid is False
    
    @pytest.mark.asyncio
    async def test_update_prompt_invalidates_cache(self, client):
        """Test updating prompt invalidates service cache."""
        # Create
        create_resp = await client.post("/admin/weekly-prompts", json={
            "week_start": 2,
            "week_end": 2,
            "system_prompt": "原始提示词",
        })
        prompt_id = create_resp.json()["id"]
        
        # Pre-populate cache
        service = get_weekly_prompt_service()
        service._cached_week = 2
        service._cached_prompt = MagicMock()
        service._cache_valid = True
        
        # Update
        await client.put(f"/admin/weekly-prompts/{prompt_id}", json={
            "system_prompt": "更新后的提示词",
        })
        
        # Cache should be invalidated
        assert service._cache_valid is False


class TestDatabaseErrorHandling:
    """Test database error handling returns 500."""
    
    @pytest.mark.asyncio
    async def test_database_error_on_create_returns_500(self, client):
        """Test database error during create returns 500."""
        with patch("gateway.app.api.weekly_prompts.create_weekly_prompt") as mock_create:
            mock_create.side_effect = SQLAlchemyError("Database connection failed")
            
            response = await client.post("/admin/weekly-prompts", json={
                "week_start": 1,
                "week_end": 1,
                "system_prompt": "测试提示词内容",
            })
            
            assert response.status_code == 500
            assert "Database error" in response.json()["detail"]
