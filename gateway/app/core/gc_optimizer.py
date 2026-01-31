"""Python garbage collection optimizer for low-latency applications.

This module provides utilities to optimize Python's garbage collector
for minimal pause times during request processing.
"""

import gc
import os
import sys
from typing import Optional

from gateway.app.core.logging import get_logger

logger = get_logger(__name__)


class GCOptimizer:
    """Optimize Python garbage collection for low-latency applications.
    
    This class manages GC thresholds and provides methods to disable GC
    during request handling and run collection during idle periods.
    
    Default GC thresholds: (700, 10, 10)
    - Generation 0: young objects, collected frequently
    - Generation 1: surviving objects, collected less frequently
    - Generation 2: long-lived objects, collected rarely
    
    Optimized thresholds: (500, 5, 5)
    - More aggressive young generation collection
    - Faster response to memory pressure
    - Reduced pause times by collecting more frequently in smaller batches
    """
    
    def __init__(self) -> None:
        self.original_thresholds: Optional[tuple[int, int, int]] = None
        self._gc_enabled: bool = True
    
    def optimize_for_latency(self) -> None:
        """Optimize GC for minimal pause times.
        
        Sets more aggressive thresholds for young generation collection
        to prevent large GC pauses during request processing.
        """
        self.original_thresholds = gc.get_threshold()
        
        # More aggressive young generation collection
        # Default is (700, 10, 10), we use (500, 5, 5)
        gc.set_threshold(500, 5, 5)
        
        if os.getenv("DEBUG_GC"):
            gc.set_debug(gc.DEBUG_STATS)
            logger.info("GC debug mode enabled")
        
        logger.info(
            "GC optimized for latency",
            extra={
                "original_thresholds": self.original_thresholds,
                "new_thresholds": gc.get_threshold(),
            }
        )
    
    def disable_gc_during_requests(self) -> None:
        """Disable GC during request handling.
        
        This prevents GC pauses from impacting request latency.
        Must be paired with enable_gc_after_requests() in a finally block.
        """
        self._gc_enabled = gc.isenabled()
        gc.disable()
    
    def enable_gc_after_requests(self) -> None:
        """Re-enable GC after request, collect young generation only.
        
        Performs a fast collection of generation 0 (young objects)
        to prevent memory accumulation without significant pause.
        """
        if self._gc_enabled:
            gc.enable()
        gc.collect(0)  # Fast collection of young generation
    
    def idle_collection(self) -> int:
        """Run GC during idle period.
        
        Performs collection of generations 0 and 1.
        Should be called periodically during low-traffic periods.
        
        Returns:
            Number of objects collected
        """
        collected = gc.collect(0)
        collected += gc.collect(1)
        return collected
    
    def get_stats(self) -> dict:
        """Get current GC statistics.
        
        Returns:
            Dictionary with thresholds, counts, and enabled status
        """
        return {
            "thresholds": gc.get_threshold(),
            "counts": gc.get_count(),
            "enabled": gc.isenabled(),
        }
    
    def restore_defaults(self) -> None:
        """Restore original GC thresholds.
        
        Call this on application shutdown to restore default GC behavior.
        """
        if self.original_thresholds:
            gc.set_threshold(*self.original_thresholds)
        gc.enable()
        logger.info("GC settings restored to defaults")


# Global instance
gc_optimizer = GCOptimizer()


def setup_gc_optimization() -> None:
    """Setup GC optimization for production.
    
    This function should be called at module load time to ensure
    GC is optimized before any requests are processed.
    """
    gc_optimizer.optimize_for_latency()
    # Initial full collection to clean up startup garbage
    gc.collect()
    print(
        f"GC optimized: thresholds={gc.get_threshold()}",
        file=sys.stderr
    )
