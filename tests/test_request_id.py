"""Tests for request ID middleware and W3C Trace Context support."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from gateway.app.core.tracing import (
    TraceContext,
    get_current_trace_context,
    set_current_trace_context,
    get_trace_id,
    get_traceparent_header,
)
from gateway.app.middleware.request_id import (
    RequestIdMiddleware,
    get_request_id,
    get_trace_context,
    get_trace_id as get_request_trace_id,
    get_traceparent,
)


class TestTraceContext:
    """Test TraceContext class."""
    
    def test_generate_new(self):
        """Test generating a new trace context."""
        context = TraceContext.generate_new()
        
        assert context.version == "00"
        assert len(context.trace_id) == 32
        assert len(context.parent_id) == 16
        assert context.flags == 1  # Default sampled
        assert context.is_sampled is True
    
    def test_from_valid_traceparent(self):
        """Test parsing valid traceparent header."""
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        context = TraceContext.from_traceparent(traceparent)
        
        assert context is not None
        assert context.version == "00"
        assert context.trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert context.parent_id == "b7ad6b7169203331"
        assert context.flags == 1
        assert context.is_sampled is True
    
    def test_from_traceparent_uppercase(self):
        """Test parsing traceparent with uppercase hex."""
        traceparent = "00-0AF7651916CD43DD8448EB211C80319C-B7AD6B7169203331-01"
        context = TraceContext.from_traceparent(traceparent)
        
        assert context is not None
        assert context.trace_id == "0af7651916cd43dd8448eb211c80319c"
    
    def test_from_invalid_traceparent(self):
        """Test parsing invalid traceparent headers."""
        invalid_cases = [
            "",  # Empty
            "invalid",  # Not enough parts
            "00-123-456-01",  # Wrong ID lengths
            "xx-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",  # Invalid version
            "00-invalid-b7ad6b7169203331-01",  # Invalid trace_id
            "00-0af7651916cd43dd8448eb211c80319c-invalid-01",  # Invalid parent_id
            "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-xx",  # Invalid flags
        ]
        
        for traceparent in invalid_cases:
            context = TraceContext.from_traceparent(traceparent)
            assert context is None, f"Expected None for: {traceparent}"
    
    def test_to_traceparent(self):
        """Test converting to traceparent string."""
        context = TraceContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            parent_id="b7ad6b7169203331",
            flags=1,
            version="00"
        )
        
        traceparent = context.to_traceparent()
        assert traceparent == "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    
    def test_is_sampled(self):
        """Test sampled flag detection."""
        sampled = TraceContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            parent_id="b7ad6b7169203331",
            flags=1
        )
        assert sampled.is_sampled is True
        
        not_sampled = TraceContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            parent_id="b7ad6b7169203331",
            flags=0
        )
        assert not_sampled.is_sampled is False
    
    def test_create_child(self):
        """Test creating child context."""
        parent = TraceContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            parent_id="b7ad6b7169203331",
            flags=1
        )
        child = parent.create_child()
        
        # Trace ID should remain the same
        assert child.trace_id == parent.trace_id
        # Parent ID should be different
        assert child.parent_id != parent.parent_id
        assert len(child.parent_id) == 16
        # Flags should be preserved
        assert child.flags == parent.flags
    
    def test_invalid_trace_id(self):
        """Test validation of invalid trace_id."""
        with pytest.raises(ValueError):
            TraceContext(trace_id="invalid", parent_id="b7ad6b7169203331")
        
        with pytest.raises(ValueError):
            TraceContext(trace_id="tooshort", parent_id="b7ad6b7169203331")
    
    def test_invalid_parent_id(self):
        """Test validation of invalid parent_id."""
        with pytest.raises(ValueError):
            TraceContext(
                trace_id="0af7651916cd43dd8448eb211c80319c",
                parent_id="invalid"
            )
        
        with pytest.raises(ValueError):
            TraceContext(
                trace_id="0af7651916cd43dd8448eb211c80319c",
                parent_id="tooshort"
            )


class TestContextVars:
    """Test context variable functions."""
    
    def test_set_and_get_trace_context(self):
        """Test setting and getting trace context."""
        context = TraceContext.generate_new()
        
        set_current_trace_context(context)
        retrieved = get_current_trace_context()
        
        assert retrieved == context
    
    def test_get_trace_id(self):
        """Test getting trace ID from context."""
        context = TraceContext.generate_new()
        set_current_trace_context(context)
        
        trace_id = get_trace_id()
        assert trace_id == context.trace_id
    
    def test_get_trace_id_no_context(self):
        """Test getting trace ID when no context is set."""
        set_current_trace_context(None)
        
        trace_id = get_trace_id()
        assert trace_id is None
    
    def test_get_traceparent_header(self):
        """Test getting traceparent header."""
        context = TraceContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            parent_id="b7ad6b7169203331",
            flags=1
        )
        set_current_trace_context(context)
        
        header = get_traceparent_header()
        assert header == "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


class TestRequestIdMiddleware:
    """Test RequestIdMiddleware with W3C Trace Context."""
    
    @pytest.fixture
    def app(self):
        """Create test FastAPI app with middleware."""
        app = FastAPI()
        app.add_middleware(RequestIdMiddleware)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            request_id = get_request_id(request)
            trace_context = get_trace_context(request)
            trace_id = get_request_trace_id(request)
            traceparent = get_traceparent(request)
            
            return {
                "request_id": request_id,
                "has_trace_context": trace_context is not None,
                "trace_id": trace_id,
                "traceparent": traceparent,
            }
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)
    
    def test_request_id_generation(self, client):
        """Test that request ID is generated."""
        response = client.get("/test")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["request_id"] != "unknown"
        assert len(data["request_id"]) > 0
    
    def test_request_id_from_header(self, client):
        """Test that request ID is extracted from header."""
        custom_id = "my-custom-request-id"
        response = client.get("/test", headers={"X-Request-ID": custom_id})
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["request_id"] == custom_id
    
    def test_request_id_in_response(self, client):
        """Test that request ID is returned in response."""
        response = client.get("/test")
        
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0
    
    def test_traceparent_generation(self, client):
        """Test that traceparent is generated."""
        response = client.get("/test")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["has_trace_context"] is True
        assert data["trace_id"] is not None
        assert len(data["trace_id"]) == 32
        assert data["traceparent"] is not None
    
    def test_traceparent_from_header(self, client):
        """Test that traceparent is extracted from header."""
        incoming_traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        response = client.get("/test", headers={"traceparent": incoming_traceparent})
        
        assert response.status_code == 200
        data = response.json()
        
        # Trace ID should be preserved from incoming context
        assert data["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
        
        # But traceparent should be different (child span)
        returned_traceparent = response.headers.get("traceparent")
        assert returned_traceparent is not None
        assert returned_traceparent != incoming_traceparent
        
        # The trace ID part should match
        returned_parts = returned_traceparent.split("-")
        assert returned_parts[1] == "0af7651916cd43dd8448eb211c80319c"
    
    def test_traceparent_in_response(self, client):
        """Test that traceparent is returned in response."""
        response = client.get("/test")
        
        assert "traceparent" in response.headers
        traceparent = response.headers["traceparent"]
        
        # Validate format
        parts = traceparent.split("-")
        assert len(parts) == 4
        assert len(parts[1]) == 32  # trace_id
        assert len(parts[2]) == 16  # parent_id
    
    def test_invalid_traceparent_ignored(self, client):
        """Test that invalid traceparent is ignored and new one generated."""
        response = client.get("/test", headers={"traceparent": "invalid"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have generated a new trace context
        assert data["has_trace_context"] is True
        assert data["trace_id"] is not None


class TestProviderTracePropagation:
    """Test that trace context is passed to providers."""
    
    def test_base_provider_get_request_headers(self):
        """Test BaseProvider._get_request_headers with traceparent."""
        from gateway.app.providers.base import BaseProvider
        
        class TestProvider(BaseProvider):
            async def chat_completion(self, payload, traceparent=None):
                pass
            
            async def stream_chat(self, payload, traceparent=None):
                yield ""
            
            async def health_check(self, timeout=2.0):
                return True
        
        provider = TestProvider(
            base_url="https://api.test.com/v1",
            api_key="test-key"
        )
        
        # Without traceparent
        headers = provider._get_request_headers()
        assert "traceparent" not in headers
        
        # With traceparent
        headers = provider._get_request_headers(
            traceparent="00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        )
        assert headers["traceparent"] == "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        
        # Original headers should be preserved
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
