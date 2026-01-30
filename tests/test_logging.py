"""Tests for structured logging configuration."""

import json
import logging
from unittest.mock import patch

import pytest

from gateway.app.core.logging import (
    JSONFormatter,
    ContextFilter,
    RequestIdFilter,
    get_logger,
    get_logging_config,
    get_log_context,
    setup_logging,
)


class TestJSONFormatter:
    """Test JSON formatter for structured logging."""
    
    def test_basic_json_format(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert "timestamp" in data
        assert "source" in data
        assert data["source"]["file"] == "test.py"
        assert data["source"]["line"] == 1
    
    def test_json_format_with_context(self):
        """Test JSON formatting with context fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Request processed",
            args=(),
            exc_info=None,
        )
        
        # Add context fields
        record.trace_id = "abc123def456"
        record.student_id = "student-123"
        record.provider = "deepseek"
        record.duration_ms = 150.5
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["trace_id"] == "abc123def456"
        assert data["student_id"] == "student-123"
        assert data["provider"] == "deepseek"
        assert data["duration_ms"] == 150.5
    
    def test_json_format_with_extra_fields(self):
        """Test JSON formatting with extra custom fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Custom event",
            args=(),
            exc_info=None,
        )
        
        # Add custom field
        record.custom_field = "custom_value"
        record.another_field = 42
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["extra"]["custom_field"] == "custom_value"
        assert data["extra"]["another_field"] == 42
    
    def test_json_format_with_exception(self):
        """Test JSON formatting with exception info."""
        import sys
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert "exception" in data
        # exception should be a list of traceback lines
        exception_text = "".join(data["exception"])
        assert "ValueError" in exception_text
        assert "Test error" in exception_text
    
    def test_json_format_unicode(self):
        """Test JSON formatting with unicode characters."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Unicode message: 你好世界 🌍",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert "你好世界 🌍" in data["message"]
    
    def test_json_format_custom_fields_list(self):
        """Test JSON formatter with custom fields list."""
        formatter = JSONFormatter(fields=["name", "levelname", "message"])
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        data = json.loads(output)
        
        # Standard fields should still be present
        assert data["level"] == "INFO"
        assert data["logger"] == "test"


class TestContextFilter:
    """Test context filter for adding default fields."""
    
    def test_adds_default_fields(self):
        """Test that context filter adds default fields."""
        filter_ = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        
        result = filter_.filter(record)
        
        assert result is True
        assert hasattr(record, "trace_id")
        assert hasattr(record, "student_id")
        assert hasattr(record, "provider")
        assert hasattr(record, "request_id")
        assert hasattr(record, "span_id")
        assert hasattr(record, "user_agent")
        assert hasattr(record, "path")
        assert hasattr(record, "method")
        assert hasattr(record, "status_code")
        assert hasattr(record, "duration_ms")
    
    def test_preserves_existing_values(self):
        """Test that context filter preserves existing values."""
        filter_ = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        
        record.trace_id = "existing-trace-id"
        record.student_id = "existing-student"
        
        filter_.filter(record)
        
        assert record.trace_id == "existing-trace-id"
        assert record.student_id == "existing-student"


class TestRequestIdFilterAlias:
    """Test RequestIdFilter backwards compatibility alias."""
    
    def test_request_id_filter_is_alias(self):
        """Test that RequestIdFilter is an alias for ContextFilter."""
        assert RequestIdFilter is ContextFilter


class TestGetLoggingConfig:
    """Test logging configuration generation."""
    
    def test_default_text_format(self):
        """Test default text format configuration."""
        with patch("gateway.app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "text"
            mock_settings.log_level = "INFO"
            
            config = get_logging_config()
        
        assert "formatters" in config
        assert "standard" in config["formatters"]
        assert "structured" in config["formatters"]
        assert "json" not in config["formatters"]
        assert config["handlers"]["console"]["formatter"] == "standard"
    
    def test_structured_format(self):
        """Test structured format configuration."""
        with patch("gateway.app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "structured"
            mock_settings.log_level = "DEBUG"
            
            config = get_logging_config()
        
        assert config["handlers"]["console"]["formatter"] == "structured"
        assert config["handlers"]["console"]["level"] == "DEBUG"
    
    def test_json_format(self):
        """Test JSON format configuration."""
        with patch("gateway.app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "json"
            mock_settings.log_level = "WARNING"
            
            config = get_logging_config()
        
        assert "json" in config["formatters"]
        assert config["handlers"]["console"]["formatter"] == "json"
        assert config["handlers"]["console"]["level"] == "WARNING"
    
    def test_context_filter_added(self):
        """Test that context filter is added to handlers."""
        config = get_logging_config()
        
        assert "filters" in config
        assert "context" in config["filters"]
        assert "context" in config["handlers"]["console"]["filters"]


class TestGetLogger:
    """Test get_logger function."""
    
    def test_get_logger_default_name(self):
        """Test getting logger with default name."""
        logger = get_logger()
        assert logger.name == "gateway"
    
    def test_get_logger_custom_name(self):
        """Test getting logger with custom name."""
        logger = get_logger("custom.module")
        assert logger.name == "custom.module"


class TestGetLogContext:
    """Test get_log_context helper function."""
    
    def test_basic_context(self):
        """Test creating basic log context."""
        context = get_log_context(
            trace_id="trace-123",
            student_id="student-456",
            provider="deepseek"
        )
        
        assert context["trace_id"] == "trace-123"
        assert context["student_id"] == "student-456"
        assert context["provider"] == "deepseek"
    
    def test_context_filters_none(self):
        """Test that None values are filtered out."""
        context = get_log_context(
            trace_id="trace-123",
            student_id=None,
            provider="deepseek"
        )
        
        assert "trace_id" in context
        assert "student_id" not in context
        assert "provider" in context
    
    def test_context_with_extra(self):
        """Test context with extra custom fields."""
        context = get_log_context(
            trace_id="trace-123",
            custom_field="value",
            another=42
        )
        
        assert context["trace_id"] == "trace-123"
        assert context["custom_field"] == "value"
        assert context["another"] == 42


class TestIntegration:
    """Integration tests for logging system."""
    
    def test_json_logging_output(self, capsys):
        """Test actual JSON logging output."""
        with patch("gateway.app.core.logging.settings") as mock_settings:
            mock_settings.log_format = "json"
            mock_settings.log_level = "INFO"
            
            setup_logging()
            logger = get_logger("test.integration")
            
            logger.info(
                "Integration test",
                extra={
                    "trace_id": "abc123",
                    "student_id": "student-1",
                    "provider": "openai"
                }
            )
            
            captured = capsys.readouterr()
            output = captured.out
            
            # Parse the JSON output
            data = json.loads(output.strip())
            
            assert data["level"] == "INFO"
            assert data["logger"] == "test.integration"
            assert data["message"] == "Integration test"
            assert data["trace_id"] == "abc123"
            assert data["student_id"] == "student-1"
            assert data["provider"] == "openai"
