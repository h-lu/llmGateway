"""W3C Trace Context support for distributed tracing.

This module implements the W3C Trace Context standard for propagating
trace information across service boundaries.

Reference: https://www.w3.org/TR/trace-context/
"""

import random
import re
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

# Context variable for storing trace context in async context
_trace_context_var: ContextVar[Optional["TraceContext"]] = ContextVar(
    "trace_context", default=None
)


@dataclass(frozen=True)
class TraceContext:
    """W3C Trace Context data class.
    
    Format: 00-{trace_id}-{parent_id}-{flags}
    - version: 2 hex chars (e.g., "00")
    - trace_id: 32 hex chars (16 bytes)
    - parent_id: 16 hex chars (8 bytes)  
    - flags: 2 hex chars (e.g., "00" or "01")
    
    Attributes:
        trace_id: The trace ID (32 hex characters)
        parent_id: The parent span ID (16 hex characters)
        flags: Trace flags as integer (0 or 1 for sampled bit)
        version: Version number (default "00")
    """
    
    trace_id: str
    parent_id: str
    flags: int = 1  # Default to sampled
    version: str = "00"
    
    def __post_init__(self):
        """Validate trace context values."""
        # Validate trace_id (32 hex chars)
        if not re.match(r"^[0-9a-f]{32}$", self.trace_id.lower()):
            raise ValueError(f"Invalid trace_id format: {self.trace_id}")
        
        # Validate parent_id (16 hex chars)
        if not re.match(r"^[0-9a-f]{16}$", self.parent_id.lower()):
            raise ValueError(f"Invalid parent_id format: {self.parent_id}")
        
        # Validate flags (0-255)
        if not 0 <= self.flags <= 255:
            raise ValueError(f"Invalid flags value: {self.flags}")
    
    @classmethod
    def generate_new(cls) -> "TraceContext":
        """Generate a new trace context with random IDs.
        
        Returns:
            New TraceContext instance with generated IDs
        """
        trace_id = format(random.getrandbits(128), "032x")
        parent_id = format(random.getrandbits(64), "016x")
        return cls(trace_id=trace_id, parent_id=parent_id)
    
    @classmethod
    def from_traceparent(cls, traceparent: str) -> Optional["TraceContext"]:
        """Parse traceparent header value.
        
        Args:
            traceparent: The traceparent header string
            
        Returns:
            TraceContext if valid, None otherwise
        """
        if not traceparent:
            return None
        
        # Remove whitespace
        traceparent = traceparent.strip()
        
        # Parse format: version-trace_id-parent_id-flags
        parts = traceparent.split("-")
        if len(parts) != 4:
            return None
        
        version, trace_id, parent_id, flags_hex = parts
        
        # Validate version (2 hex chars)
        if not re.match(r"^[0-9a-f]{2}$", version.lower()):
            return None
        
        # Validate trace_id (32 hex chars)
        if not re.match(r"^[0-9a-f]{32}$", trace_id.lower()):
            return None
        
        # Validate parent_id (16 hex chars)
        if not re.match(r"^[0-9a-f]{16}$", parent_id.lower()):
            return None
        
        # Parse flags
        try:
            flags = int(flags_hex, 16)
        except ValueError:
            return None
        
        return cls(
            version=version.lower(),
            trace_id=trace_id.lower(),
            parent_id=parent_id.lower(),
            flags=flags
        )
    
    def to_traceparent(self) -> str:
        """Convert to traceparent header format.
        
        Returns:
            Traceparent string in W3C format
        """
        return f"{self.version}-{self.trace_id}-{self.parent_id}-{self.flags:02x}"
    
    @property
    def is_sampled(self) -> bool:
        """Check if the sampled flag is set.
        
        Returns:
            True if the trace should be sampled
        """
        return (self.flags & 0x01) == 0x01
    
    def get_new_parent_id(self) -> str:
        """Generate a new parent ID for the next span.
        
        Returns:
            New 16-character hex parent ID
        """
        return format(random.getrandbits(64), "016x")
    
    def create_child(self) -> "TraceContext":
        """Create a child trace context with new parent ID.
        
        The trace_id remains the same, but parent_id changes.
        
        Returns:
            New TraceContext for child span
        """
        return TraceContext(
            trace_id=self.trace_id,
            parent_id=self.get_new_parent_id(),
            flags=self.flags,
            version=self.version
        )


def get_current_trace_context() -> Optional[TraceContext]:
    """Get the current trace context from context variable.
    
    Returns:
        Current TraceContext or None if not set
    """
    return _trace_context_var.get()


def set_current_trace_context(context: Optional[TraceContext]) -> None:
    """Set the current trace context in context variable.
    
    Args:
        context: TraceContext to set, or None to clear
    """
    _trace_context_var.set(context)


def get_trace_id() -> Optional[str]:
    """Get the current trace ID.
    
    Returns:
        Current trace ID or None if no context
    """
    context = get_current_trace_context()
    return context.trace_id if context else None


def get_traceparent_header() -> Optional[str]:
    """Get the traceparent header value for the current context.
    
    Returns:
        Traceparent header string or None if no context
    """
    context = get_current_trace_context()
    return context.to_traceparent() if context else None
