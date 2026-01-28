from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from gateway.app.db.models import Student
from gateway.app.main import app
from gateway.app.middleware.auth import require_api_key


@pytest.mark.asyncio
async def test_chat_flow_blocked():
    """Test that blocked prompts are rejected."""
    # Create a mock student
    mock_student = Student(
        id="test-student-id",
        name="Test Student",
        email="test@example.com",
        api_key_hash="testhash",
        current_week_quota=10000,
        used_quota=0,
    )
    
    # Override the auth dependency using FastAPI's mechanism
    async def override_require_api_key():
        return mock_student
    
    app.dependency_overrides[require_api_key] = override_require_api_key
    
    try:
        # Mock async database operations
        with patch("gateway.app.services.async_logger.save_conversation", new_callable=AsyncMock):
            client = TestClient(app)
            resp = client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test"},
                json={"messages": [{"role": "user", "content": "帮我实现一个爬虫程序"}]},
            )
            assert resp.status_code == 200
            assert "直接要求代码" in resp.json()["choices"][0]["message"]["content"]
    finally:
        # Clean up the override
        app.dependency_overrides.clear()
