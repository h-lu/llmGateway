"""Structured logging configuration for the gateway.

This module provides a structured logging setup using Python's standard
logging module with JSON formatting for production environments.
"""

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from gateway.app.core.config import settings
from gateway.app.core.async_logging import setup_async_logging, AsyncHandlerWrapper


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.
    
    Outputs log records as JSON objects for consumption by log aggregation
    systems like ELK Stack or Grafana Loki.
    
    Attributes:
        fields: List of fields to include in JSON output
    """
    
    # Standard fields always included
    STANDARD_FIELDS = ["name", "levelname", "message", "timestamp"]
    
    # Contextual fields for request tracking
    CONTEXT_FIELDS = [
        "trace_id",      # W3C trace context trace ID
        "span_id",       # W3C trace context span/parent ID
        "request_id",    # Request ID from X-Request-ID header
        "student_id",    # Student identifier
        "provider",      # LLM provider name (deepseek, openai, etc.)
        "user_agent",    # Client user agent
        "path",          # Request path
        "method",        # HTTP method
        "status_code",   # HTTP response status
        "duration_ms",   # Request duration in milliseconds
    ]
    
    def __init__(
        self,
        fields: Optional[list] = None,
        datefmt: Optional[str] = None,
    ):
        """Initialize JSON formatter.
        
        Args:
            fields: Custom fields to include (defaults to all standard + context)
            datefmt: Date format string (ISO8601 by default)
        """
        super().__init__(datefmt=datefmt)
        self.fields = fields or (self.STANDARD_FIELDS + self.CONTEXT_FIELDS)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON string representation of the log record
        """
        log_data: Dict[str, Any] = {}
        
        # Ensure message is formatted
        record.message = record.getMessage()
        
        # Standard fields
        log_data["timestamp"] = datetime.now().astimezone().isoformat()
        log_data["level"] = record.levelname
        log_data["logger"] = record.name
        log_data["message"] = record.message
        
        # Source location
        log_data["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        # Add configured context fields if present
        for field in self.CONTEXT_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None and value != "-":
                    log_data[field] = value
        
        # Add any extra fields from the record
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "asctime", "timestamp", "logger", "level", "source"
            ):
                if key not in self.CONTEXT_FIELDS:
                    if "extra" not in log_data:
                        log_data["extra"] = {}
                    log_data["extra"][key] = value
        
        # Add exception info if present
        if record.exc_info and record.exc_info != (None, None, None):
            import traceback
            log_data["exception"] = traceback.format_exception(*record.exc_info)
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """Logging filter that adds contextual fields to log records.
    
    Adds default values for trace_id, student_id, provider and other
    contextual fields if not already present in the log record.
    """
    
    # Fields with their default values
    CONTEXT_DEFAULTS = {
        "trace_id": None,
        "span_id": None,
        "request_id": None,
        "student_id": None,
        "provider": None,
        "user_agent": None,
        "path": None,
        "method": None,
        "status_code": None,
        "duration_ms": None,
    }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to log record if not present.
        
        Args:
            record: Log record to enrich
            
        Returns:
            True to allow the record through
        """
        for field, default in self.CONTEXT_DEFAULTS.items():
            if not hasattr(record, field):
                setattr(record, field, default)
        return True


# Backwards compatibility alias
RequestIdFilter = ContextFilter


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration dictionary.
    
    Returns:
        Logging configuration dict compatible with logging.config.dictConfig
    """
    log_format = getattr(settings, "log_format", "text").lower()
    log_level = getattr(settings, "log_level", "INFO").upper()
    
    formatters = {
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "structured": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s - trace_id=%(trace_id)s - student_id=%(student_id)s - provider=%(provider)s"
        },
    }
    
    # Add JSON formatter if requested
    if log_format == "json":
        formatters["json"] = {
            "()": "gateway.app.core.logging.JSONFormatter",
        }
        default_formatter = "json"
    else:
        default_formatter = "structured" if log_format == "structured" else "standard"
    
    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": default_formatter,
            "stream": sys.stdout,
            "filters": ["context"],
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "level": "ERROR",
            "formatter": default_formatter,
            "stream": sys.stderr,
            "filters": ["context"],
        },
    }
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "filters": {
            "context": {
                "()": "gateway.app.core.logging.ContextFilter",
            },
        },
        "handlers": handlers,
        "loggers": {
            "gateway": {
                "level": log_level,
                "handlers": ["console", "error_console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
    }


def setup_logging() -> None:
    """Configure logging for the application with async support."""
    config = get_logging_config()
    logging.config.dictConfig(config)
    
    # Setup async logging to reduce I/O blocking
    setup_async_logging()
    
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str = "gateway") -> logging.Logger:
    """Get a logger instance with the specified name.
    
    Args:
        name: Logger name, defaults to "gateway"
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_log_context(
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    request_id: Optional[str] = None,
    student_id: Optional[str] = None,
    provider: Optional[str] = None,
    **extra
) -> Dict[str, Any]:
    """Create a log context dictionary for use with extra parameter.
    
    This helper creates a properly formatted context dictionary for
    passing structured context to log messages.
    
    Args:
        trace_id: W3C trace context trace ID
        span_id: W3C trace context span ID
        request_id: Request ID
        student_id: Student identifier
        provider: LLM provider name
        **extra: Additional custom fields
        
    Returns:
        Dictionary suitable for passing as extra= parameter to logging calls
        
    Example:
        >>> logger.info(
        ...     "Processing request",
        ...     extra=get_log_context(
        ...         trace_id="abc123",
        ...         student_id="student-1",
        ...         provider="deepseek"
        ...     )
        ... )
    """
    context = {
        "trace_id": trace_id,
        "span_id": span_id,
        "request_id": request_id,
        "student_id": student_id,
        "provider": provider,
    }
    context.update(extra)
    # Filter out None values
    return {k: v for k, v in context.items() if v is not None}
