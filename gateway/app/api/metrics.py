"""Metrics and monitoring endpoints for the gateway.

This module provides Prometheus-compatible metrics endpoints for monitoring
the gateway's performance, health, and usage.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from gateway.app.core.logging import get_logger
from gateway.app.middleware.auth import require_admin
from gateway.app.services.request_router import get_request_router

logger = get_logger(__name__)
router = APIRouter()


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    count: int = 0
    total_duration: float = 0.0
    errors: int = 0


@dataclass
class MetricsCollector:
    """Collects and stores gateway metrics.

    This class is thread-safe and collects:
    - Request counts and latencies
    - Provider health status
    - Quota usage
    - Error rates
    """

    # Request metrics by endpoint
    _requests: Dict[str, RequestMetrics] = field(
        default_factory=lambda: defaultdict(lambda: RequestMetrics())
    )

    # Provider health status
    _provider_health: Dict[str, bool] = field(default_factory=dict)
    _provider_requests: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Quota metrics
    _quota_checks: int = 0
    _quota_exceeded: int = 0

    # Error counts by type
    _errors: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Async safety
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Start time for uptime calculation
    _start_time: float = field(default_factory=time.time)

    async def record_request(
        self, endpoint: str, duration: float, status_code: int
    ) -> None:
        """Record a request metric.

        Args:
            endpoint: The endpoint path
            duration: Request duration in seconds
            status_code: HTTP status code
        """
        async with self._lock:
            metrics = self._requests[endpoint]
            metrics.count += 1
            metrics.total_duration += duration
            if status_code >= 400:
                metrics.errors += 1

    async def record_provider_request(self, provider: str) -> None:
        """Record a provider request.

        Args:
            provider: Provider name
        """
        async with self._lock:
            self._provider_requests[provider] += 1

    async def update_provider_health(self, provider: str, healthy: bool) -> None:
        """Update provider health status.

        Args:
            provider: Provider name
            healthy: Whether the provider is healthy
        """
        async with self._lock:
            old_health = self._provider_health.get(provider)
            self._provider_health[provider] = healthy

            # Log health changes
            if old_health is not None and old_health != healthy:
                if healthy:
                    logger.info(f"Provider {provider} is now healthy")
                else:
                    logger.warning(f"Provider {provider} is now unhealthy")

    async def record_quota_check(self, exceeded: bool = False) -> None:
        """Record a quota check.

        Args:
            exceeded: Whether the quota was exceeded
        """
        async with self._lock:
            self._quota_checks += 1
            if exceeded:
                self._quota_exceeded += 1

    async def record_error(self, error_type: str) -> None:
        """Record an error.

        Args:
            error_type: Type of error
        """
        async with self._lock:
            self._errors[error_type] += 1

    async def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics.

        Returns:
            Dictionary with metrics summary
        """
        async with self._lock:
            total_requests = sum(m.count for m in self._requests.values())
            total_errors = sum(m.errors for m in self._requests.values())
            total_duration = sum(m.total_duration for m in self._requests.values())

            avg_latency = total_duration / total_requests if total_requests > 0 else 0
            error_rate = total_errors / total_requests if total_requests > 0 else 0

            # Calculate per-endpoint latencies
            endpoint_latencies = {}
            for endpoint, metrics in self._requests.items():
                if metrics.count > 0:
                    endpoint_latencies[endpoint] = {
                        "count": metrics.count,
                        "avg_duration_ms": round(
                            (metrics.total_duration / metrics.count) * 1000, 2
                        ),
                        "error_count": metrics.errors,
                    }

            return {
                "uptime_seconds": round(time.time() - self._start_time, 2),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": round(error_rate, 4),
                "average_latency_ms": round(avg_latency * 1000, 2),
                "endpoints": endpoint_latencies,
                "providers": {
                    name: {
                        "healthy": self._provider_health.get(name, False),
                        "requests": self._provider_requests.get(name, 0),
                    }
                    for name in set(
                        list(self._provider_health.keys())
                        + list(self._provider_requests.keys())
                    )
                },
                "quota": {
                    "checks": self._quota_checks,
                    "exceeded": self._quota_exceeded,
                    "exceeded_rate": round(self._quota_exceeded / self._quota_checks, 4)
                    if self._quota_checks > 0
                    else 0,
                },
                "errors_by_type": dict(self._errors),
            }

    async def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        async with self._lock:
            lines = []

            # Gateway requests total
            lines.append("# HELP gateway_requests_total Total number of requests")
            lines.append("# TYPE gateway_requests_total counter")
            for endpoint, metrics in self._requests.items():
                lines.append(
                    f'gateway_requests_total{{endpoint="{endpoint}"}} {metrics.count}'
                )

            # Gateway request duration
            lines.append(
                "\n# HELP gateway_request_duration_seconds Total request duration"
            )
            lines.append("# TYPE gateway_request_duration_seconds counter")
            for endpoint, metrics in self._requests.items():
                lines.append(
                    f'gateway_request_duration_seconds{{endpoint="{endpoint}"}} {metrics.total_duration}'
                )

            # Gateway errors total
            lines.append("\n# HELP gateway_errors_total Total number of errors")
            lines.append("# TYPE gateway_errors_total counter")
            total_errors = sum(m.errors for m in self._requests.values())
            lines.append(f"gateway_errors_total{{}} {total_errors}")

            # Provider health
            lines.append(
                "\n# HELP gateway_provider_health Provider health status (1=healthy, 0=unhealthy)"
            )
            lines.append("# TYPE gateway_provider_health gauge")
            for provider, healthy in self._provider_health.items():
                health_value = 1 if healthy else 0
                lines.append(
                    f'gateway_provider_health{{provider="{provider}"}} {health_value}'
                )

            # Provider requests
            lines.append(
                "\n# HELP gateway_provider_requests_total Total requests per provider"
            )
            lines.append("# TYPE gateway_provider_requests_total counter")
            for provider, count in self._provider_requests.items():
                lines.append(
                    f'gateway_provider_requests_total{{provider="{provider}"}} {count}'
                )

            # Quota metrics
            lines.append("\n# HELP gateway_quota_checks_total Total quota checks")
            lines.append("# TYPE gateway_quota_checks_total counter")
            lines.append(f"gateway_quota_checks_total{{}} {self._quota_checks}")

            lines.append(
                "\n# HELP gateway_quota_exceeded_total Total quota exceeded events"
            )
            lines.append("# TYPE gateway_quota_exceeded_total counter")
            lines.append(f"gateway_quota_exceeded_total{{}} {self._quota_exceeded}")

            # Uptime
            lines.append("\n# HELP gateway_uptime_seconds Gateway uptime in seconds")
            lines.append("# TYPE gateway_uptime_seconds gauge")
            lines.append(
                f"gateway_uptime_seconds{{}} {round(time.time() - self._start_time, 2)}"
            )

            return "\n".join(lines) + "\n"


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        MetricsCollector singleton instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    """Reset the global metrics collector (useful for testing)."""
    global _metrics_collector
    _metrics_collector = None


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics(admin=Depends(require_admin)) -> PlainTextResponse:
    """Prometheus-compatible metrics endpoint (admin only).

    Returns:
        Plain text response with Prometheus-formatted metrics
    """
    collector = get_metrics_collector()
    content = await collector.get_prometheus_metrics()
    return PlainTextResponse(
        content=content, media_type="text/plain; version=0.0.4; charset=utf-8"
    )


@router.get("/stats")
async def gateway_stats(admin=Depends(require_admin)) -> dict[str, Any]:
    """Detailed gateway statistics (admin only).

    Args:
        admin: Admin user (injected via dependency)

    Returns:
        JSON response with detailed statistics
    """
    collector = get_metrics_collector()
    return await collector.get_summary()


@router.get("/metrics/router")
async def get_router_stats(admin=Depends(require_admin)) -> dict[str, Any]:
    """Request router statistics (admin only).

    Provides real-time visibility into streaming vs normal request
    capacity utilization and rejection rates.

    Args:
        admin: Admin user (injected via dependency)

    Returns:
        JSON response with router statistics including:
        - Active requests per type
        - Capacity limits and utilization
        - Total processed and rejected counts
    """
    router = get_request_router()
    return router.get_stats()


class MetricsMiddleware:
    """Middleware to collect request metrics.

        This middleware should be added to the FastAPI app to automatically
    collect request metrics.

        Example:
            app.add_middleware(MetricsMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """Process request and collect metrics."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Capture status code
        status_code = 200

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            duration = time.time() - start_time

            # Record metric
            collector = get_metrics_collector()
            endpoint = scope.get("path", "unknown")
            await collector.record_request(endpoint, duration, status_code)


async def record_provider_health(provider: str, healthy: bool) -> None:
    """Record provider health status.

    This is a convenience function that can be called from other modules.

    Args:
        provider: Provider name
        healthy: Whether the provider is healthy
    """
    collector = get_metrics_collector()
    await collector.update_provider_health(provider, healthy)


async def record_provider_request(provider: str) -> None:
    """Record a provider request.

    Args:
        provider: Provider name
    """
    collector = get_metrics_collector()
    await collector.record_provider_request(provider)


async def record_quota_check(exceeded: bool = False) -> None:
    """Record a quota check.

    Args:
        exceeded: Whether the quota was exceeded
    """
    collector = get_metrics_collector()
    await collector.record_quota_check(exceeded)
