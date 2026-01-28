"""Provider health checking module.

This module provides health check functionality for AI providers,
including periodic background checks and health status tracking.
"""

import asyncio
from typing import Dict, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from gateway.app.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class ProviderHealthChecker:
    """Manages health checks for multiple providers.
    
    This class provides:
    - Health status tracking for all providers
    - Periodic background health checks
    - Graceful shutdown support
    
    Usage:
        checker = ProviderHealthChecker()
        checker.register_provider("openai", openai_provider)
        checker.register_provider("deepseek", deepseek_provider)
        
        # Start background checks
        await checker.start()
        
        # Check health status
        if checker.is_healthy("openai"):
            # Use openai provider
            
        # Stop background checks
        await checker.stop()
    """
    
    def __init__(self, check_interval: float = 30.0):
        """Initialize the health checker.
        
        Args:
            check_interval: Time between health checks in seconds (default: 30.0)
        """
        self._providers: Dict[str, "BaseProvider"] = {}
        self._health_status: Dict[str, bool] = {}
        self._check_interval = check_interval
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
    
    def register_provider(self, name: str, provider: "BaseProvider") -> None:
        """Register a provider for health checking.
        
        Args:
            name: Unique identifier for the provider
            provider: The provider instance to check
        """
        self._providers[name] = provider
        # Initialize as healthy until first check
        self._health_status[name] = True
        logger.debug(f"Registered provider '{name}' for health checks")
    
    def unregister_provider(self, name: str) -> None:
        """Unregister a provider from health checking.
        
        Args:
            name: The provider identifier to remove
        """
        self._providers.pop(name, None)
        self._health_status.pop(name, None)
        logger.debug(f"Unregistered provider '{name}' from health checks")
    
    def is_healthy(self, provider_name: str) -> bool:
        """Check if a provider is healthy.
        
        Args:
            provider_name: The provider identifier
            
        Returns:
            True if healthy, False if unhealthy or not registered
        """
        return self._health_status.get(provider_name, False)
    
    def mark_unhealthy(self, provider_name: str) -> None:
        """Manually mark a provider as unhealthy.
        
        This is useful when a request fails and we want to immediately
        stop sending traffic to the provider without waiting for the
        next health check cycle.
        
        Args:
            provider_name: The provider identifier to mark unhealthy
        """
        if provider_name in self._health_status:
            if self._health_status[provider_name]:
                logger.warning(f"Provider '{provider_name}' marked as unhealthy due to request failure")
            self._health_status[provider_name] = False
    
    def get_all_status(self) -> Dict[str, bool]:
        """Get health status for all registered providers.
        
        Returns:
            Dictionary mapping provider names to health status
        """
        return self._health_status.copy()
    
    async def check_all(self) -> Dict[str, bool]:
        """Run health checks for all registered providers.
        
        Returns:
            Updated health status dictionary
        """
        results = {}
        
        for name, provider in self._providers.items():
            try:
                is_healthy = await provider.health_check()
                results[name] = is_healthy
                
                # Log status changes
                if self._health_status.get(name) != is_healthy:
                    if is_healthy:
                        logger.info(f"Provider '{name}' is now healthy")
                    else:
                        logger.warning(f"Provider '{name}' is now unhealthy")
                
                self._health_status[name] = is_healthy
            except Exception as e:
                logger.warning(f"Health check failed for '{name}': {e}")
                results[name] = False
                self._health_status[name] = False
        
        return results
    
    async def start(self) -> None:
        """Start the background health check task.
        
        This creates a background task that periodically checks
        all registered providers.
        """
        if self._task is not None:
            logger.debug("Health checker already running")
            return
        
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_checks())
        logger.info(f"Started health checker (interval: {self._check_interval}s)")
    
    async def stop(self) -> None:
        """Stop the background health check task.
        
        This gracefully shuts down the background task.
        """
        if self._task is None:
            return
        
        self._stop_event.set()
        
        try:
            # Wait for the task to complete with a timeout
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Health check task did not stop gracefully, cancelling")
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        finally:
            self._task = None
            logger.info("Stopped health checker")
    
    async def _run_checks(self) -> None:
        """Background task that runs periodic health checks."""
        while not self._stop_event.is_set():
            try:
                await self.check_all()
            except Exception as e:
                logger.error(f"Error during health check cycle: {e}")
            
            # Wait for the next check interval or until stopped
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._check_interval
                )
            except asyncio.TimeoutError:
                # Normal case: interval elapsed, continue to next check
                pass
