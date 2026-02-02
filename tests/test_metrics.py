"""Tests for metrics and monitoring endpoints."""

import os
import pytest
from fastapi.testclient import TestClient

from gateway.app.main import app
from gateway.app.api.metrics import (
    get_metrics_collector,
    reset_metrics_collector,
    MetricsCollector,
)


# Set test admin token for all tests in this module
os.environ["ADMIN_TOKEN"] = "test-admin-token-for-metrics"


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    @pytest.fixture(autouse=True)
    def reset_collector(self):
        """Reset collector before each test."""
        reset_metrics_collector()
        yield
        reset_metrics_collector()
    
    @pytest.mark.asyncio
    async def test_record_request(self):
        """Test recording a request."""
        collector = get_metrics_collector()
        await collector.record_request("/test", 0.5, 200)
        
        summary = await collector.get_summary()
        assert summary["total_requests"] == 1
        assert "/test" in summary["endpoints"]
    
    @pytest.mark.asyncio
    async def test_record_error(self):
        """Test recording an error."""
        collector = get_metrics_collector()
        await collector.record_request("/test", 0.5, 500)
        
        summary = await collector.get_summary()
        assert summary["total_errors"] == 1
        assert summary["error_rate"] == 1.0
    
    @pytest.mark.asyncio
    async def test_provider_health(self):
        """Test recording provider health."""
        collector = get_metrics_collector()
        await collector.update_provider_health("deepseek", True)
        await collector.update_provider_health("openai", False)
        
        summary = await collector.get_summary()
        assert summary["providers"]["deepseek"]["healthy"] is True
        assert summary["providers"]["openai"]["healthy"] is False
    
    @pytest.mark.asyncio
    async def test_quota_metrics(self):
        """Test quota metrics."""
        collector = get_metrics_collector()
        await collector.record_quota_check(exceeded=False)
        await collector.record_quota_check(exceeded=True)
        
        summary = await collector.get_summary()
        assert summary["quota"]["checks"] == 2
        assert summary["quota"]["exceeded"] == 1
        assert summary["quota"]["exceeded_rate"] == 0.5
    
    @pytest.mark.asyncio
    async def test_prometheus_format(self):
        """Test Prometheus metrics format."""
        collector = get_metrics_collector()
        await collector.record_request("/test", 0.5, 200)
        await collector.update_provider_health("deepseek", True)
        
        metrics = await collector.get_prometheus_metrics()
        assert "gateway_requests_total" in metrics
        assert "gateway_provider_health" in metrics
        assert "deepseek" in metrics


class TestMetricsEndpoints:
    """Tests for metrics API endpoints."""
    
    @pytest.fixture(autouse=True)
    def reset_collector(self):
        """Reset collector before each test."""
        reset_metrics_collector()
        yield
        reset_metrics_collector()
    
    def test_prometheus_metrics_endpoint(self):
        """Test /metrics endpoint returns Prometheus format."""
        client = TestClient(app)
        admin_token = os.getenv("ADMIN_TOKEN", "admin-secret-token-change-in-production")
        response = client.get("/metrics", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "gateway_" in response.text
    
    def test_health_endpoint(self):
        """Test /health endpoint."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
    
    def test_stats_endpoint_requires_auth(self):
        """Test /stats endpoint requires admin auth."""
        client = TestClient(app)
        response = client.get("/stats")
        assert response.status_code == 401
    
    def test_stats_endpoint_with_auth(self):
        """Test /stats endpoint with admin token."""
        client = TestClient(app)
        admin_token = os.getenv("ADMIN_TOKEN", "admin-secret-token-change-in-production")
        
        response = client.get("/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "providers" in data
        assert "quota" in data
