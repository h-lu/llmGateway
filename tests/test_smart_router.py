"""Tests for smart router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

from gateway.app.db.models import Student
from gateway.app.services.smart_router import (
    KeyType,
    QuotaExceededWithGuidanceError,
    RoutingDecision,
    SmartRouter,
)


class TestSmartRouter:
    """Test smart routing logic."""
    
    @pytest.fixture
    def router(self):
        """Create router instance."""
        return SmartRouter()
    
    @pytest.fixture
    def student_with_own_key(self):
        """Create student with own provider key."""
        student = MagicMock(spec=Student)
        student.id = "student-123"
        student.has_own_provider_key = True
        student.provider_type = "deepseek"
        student.get_provider_api_key = MagicMock(return_value="sk-student-key")
        return student
    
    @pytest.fixture
    def student_without_key(self):
        """Create student without own key."""
        student = MagicMock(spec=Student)
        student.id = "student-456"
        student.has_own_provider_key = False
        student.current_week_quota = 10000
        student.used_quota = 0
        return student
    
    @pytest.fixture
    def student_quota_exceeded(self):
        """Create student with exceeded quota."""
        student = MagicMock(spec=Student)
        student.id = "student-789"
        student.has_own_provider_key = False
        student.current_week_quota = 10000
        student.used_quota = 10000
        return student
    
    async def test_route_with_student_key(self, router, student_with_own_key):
        """Test routing when student has own key."""
        decision = await router.route(student_with_own_key, "deepseek-chat")
        
        assert decision.key_type == KeyType.STUDENT
        assert decision.provider_name == "deepseek"
        assert decision.api_key == "sk-student-key"
        assert decision.cost_per_1m_tokens == (0.55, 2.19)
    
    async def test_route_with_teacher_key(self, router, student_without_key):
        """Test routing with teacher key when student has quota."""
        with patch.object(router, '_check_quota', return_value=True):
            with patch.object(router.config, 'teacher_deepseek_api_key', 'sk-teacher-key'):
                decision = await router.route(student_without_key, "deepseek-chat")
        
        assert decision.key_type == KeyType.TEACHER_DEEPSEEK
        assert decision.provider_name == "deepseek"
    
    async def test_route_quota_exceeded(self, router, student_quota_exceeded):
        """Test routing when quota exceeded."""
        with patch.object(router, '_check_quota', return_value=False):
            with pytest.raises(QuotaExceededWithGuidanceError) as exc_info:
                await router.route(student_quota_exceeded, "deepseek-chat")
        
        error = exc_info.value
        assert error.student_id == "student-789"
        assert error.remaining == 0
        assert "配置自己的 DeepSeek API Key" in error.message
    
    async def test_student_key_openrouter(self, router):
        """Test routing with student's OpenRouter key."""
        student = MagicMock(spec=Student)
        student.has_own_provider_key = True
        student.provider_type = "openrouter"
        student.get_provider_api_key = MagicMock(return_value="sk-or-student-key")
        
        decision = await router.route(student, "deepseek-chat")
        
        assert decision.key_type == KeyType.STUDENT
        assert decision.provider_name == "openrouter"
        assert decision.fallback_models is not None
        assert len(decision.fallback_models) > 0
