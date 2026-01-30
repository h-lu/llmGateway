"""Tests for quota checking functionality."""

import pytest
from fastapi.testclient import TestClient

from gateway.app.db.models import Student
from gateway.app.main import app
from gateway.app.exceptions import QuotaExceededError


client = TestClient(app)


class TestQuotaCheck:
    """Test suite for quota checking in chat completions."""
    
    def test_quota_exceeded_raises_error(self):
        """Test that QuotaExceededError is raised when quota is exceeded."""
        # Create a mock student with exceeded quota
        student = Student(
            id="test_student",
            name="Test Student",
            email="test@example.com",
            api_key_hash="test_hash",
            current_week_quota=1000,
            used_quota=1000  # Exactly at limit
        )
        
        from gateway.app.api.chat import check_student_quota
        
        with pytest.raises(QuotaExceededError) as exc_info:
            check_student_quota(student, week_number=5)
        
        error = exc_info.value
        assert error.remaining == 0
        assert error.reset_week == 6
        assert "quota exceeded" in str(error).lower()
    
    def test_quota_negative_raises_error(self):
        """Test that QuotaExceededError is raised when quota is negative."""
        student = Student(
            id="test_student",
            name="Test Student",
            email="test@example.com",
            api_key_hash="test_hash",
            current_week_quota=1000,
            used_quota=1500  # Over limit
        )
        
        from gateway.app.api.chat import check_student_quota
        
        with pytest.raises(QuotaExceededError) as exc_info:
            check_student_quota(student, week_number=3)
        
        error = exc_info.value
        assert error.remaining == -500
        assert error.reset_week == 4
        assert "quota exceeded" in str(error).lower()
    
    def test_quota_available_returns_remaining(self):
        """Test that check returns remaining quota when available."""
        student = Student(
            id="test_student",
            name="Test Student",
            email="test@example.com",
            api_key_hash="test_hash",
            current_week_quota=1000,
            used_quota=500  # Under limit
        )
        
        from gateway.app.api.chat import check_student_quota
        
        remaining = check_student_quota(student, week_number=2)
        assert remaining == 500
    
    def test_quota_zero_quota_raises_error(self):
        """Test that zero quota raises error immediately."""
        student = Student(
            id="test_student",
            name="Test Student",
            email="test@example.com",
            api_key_hash="test_hash",
            current_week_quota=0,
            used_quota=0
        )
        
        from gateway.app.api.chat import check_student_quota
        
        with pytest.raises(QuotaExceededError) as exc_info:
            check_student_quota(student, week_number=1)
        
        error = exc_info.value
        assert error.remaining == 0
        assert error.reset_week == 2


class TestQuotaErrorResponse:
    """Test the QuotaExceededError response format."""
    
    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        error = QuotaExceededError(
            remaining=0,
            reset_week=5,
            detail="Custom error message"
        )
        
        assert error.remaining == 0
        assert error.reset_week == 5
        assert "Custom error message" in str(error)
        assert "Quota resets at week 5" in str(error)
    
    def test_default_error_message(self):
        """Test that default error message is generated correctly."""
        error = QuotaExceededError(remaining=100, reset_week=3)
        
        assert "quota exceeded" in str(error).lower()
        assert error.remaining == 100
        assert error.reset_week == 3


class TestQuotaExceptionHandler:
    """Test the exception handler produces correct HTTP responses."""
    
    def test_quota_exceeded_handler_response(self):
        """Test that the exception handler returns correct JSONResponse."""
        from gateway.app.main import create_app
        from fastapi import Request
        from unittest.mock import MagicMock
        
        app_instance = create_app()
        
        # Find the handler
        handler = None
        for exc_class, exc_handler in app_instance.exception_handlers.items():
            if exc_class is QuotaExceededError:
                handler = exc_handler
                break
        
        assert handler is not None, "QuotaExceededError handler not found"
        
        # Create a mock request and exception
        mock_request = MagicMock(spec=Request)
        exc = QuotaExceededError(remaining=0, reset_week=5)
        
        # Call the handler directly
        import asyncio
        response = asyncio.run(handler(mock_request, exc))
        
        assert response.status_code == 429
        assert response.body == b'{"error":"quota_exceeded","message":"Weekly token quota exceeded. Remaining: 0 tokens. Quota resets at week 5.","remaining_tokens":0,"reset_week":5}'
