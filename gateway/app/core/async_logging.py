"""Async logging support to reduce I/O blocking and latency jitter.

This module provides asynchronous logging handlers and processors that offload
I/O operations to a background thread, reducing the impact of log writes on
request latency.
"""

import atexit
import logging
import queue
import threading
import time
from typing import List, Optional


class AsyncLogHandler(logging.Handler):
    """Asynchronous log handler that offloads I/O to a background thread.

    This handler queues log records in memory and processes them asynchronously,
    preventing I/O operations from blocking the main application thread.

    Attributes:
        log_queue: Thread-safe queue for log records
        max_queue_size: Maximum number of records to queue before dropping
    """

    def __init__(self, max_queue_size: int = 10000):
        super().__init__()
        self.log_queue: queue.Queue[logging.LogRecord] = queue.Queue(
            maxsize=max_queue_size
        )
        self._shutdown = False

    def emit(self, record: logging.LogRecord) -> None:
        """Queue a log record for async processing.

        If the queue is full, the record is dropped to avoid blocking.

        Args:
            record: Log record to queue
        """
        if self._shutdown:
            return
        try:
            self.log_queue.put_nowait(record)
        except queue.Full:
            # Queue is full, drop the record to maintain low latency
            pass

    def flush(self) -> None:
        """Wait for queue to empty (best effort)."""
        while not self.log_queue.empty() and not self._shutdown:
            time.sleep(0.01)

    def shutdown(self) -> None:
        """Signal handler to shutdown and flush remaining records."""
        self._shutdown = True
        self.flush()


class BackgroundLogProcessor:
    """Processes logs in background thread with batching.

    This processor runs in a daemon thread, reading from the async handler's
    queue and forwarding records to the actual output handlers (console, file, etc.).

    Attributes:
        handler: The AsyncLogHandler to read from
        flush_interval: Seconds between explicit flushes
        batch_size: Maximum records to process per iteration
    """

    def __init__(
        self,
        handler: AsyncLogHandler,
        flush_interval: float = 1.0,
        batch_size: int = 100,
    ):
        self.handler = handler
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self._stop = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background processing thread."""
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the processor to stop and wait for completion."""
        self._stop = True
        if self._thread:
            self._thread.join(timeout=5.0)

    def _process_loop(self) -> None:
        """Main processing loop - runs in background thread."""
        last_flush = time.time()

        while not self._stop:
            try:
                # Collect a batch of records
                batch: List[logging.LogRecord] = []
                for _ in range(self.batch_size):
                    try:
                        record = self.handler.log_queue.get_nowait()
                        batch.append(record)
                    except queue.Empty:
                        break

                # Process batch - forward to actual handlers
                for record in batch:
                    self._emit_to_handlers(record)

                # Periodic flush
                if time.time() - last_flush > self.flush_interval:
                    self._flush_handlers()
                    last_flush = time.time()

                # Small sleep if no work to prevent busy-waiting
                if not batch:
                    time.sleep(0.001)

            except Exception:
                # Silently continue on errors to avoid crashing the background thread
                pass

        # Final flush on shutdown
        self._drain_and_flush()

    def _emit_to_handlers(self, record: logging.LogRecord) -> None:
        """Emit a record to all non-async handlers in the root logger."""
        for target_handler in logging.root.handlers:
            if not isinstance(target_handler, AsyncLogHandler):
                try:
                    target_handler.emit(record)
                except Exception:
                    pass

    def _flush_handlers(self) -> None:
        """Flush all non-async handlers."""
        for handler in logging.root.handlers:
            if not isinstance(handler, AsyncLogHandler):
                try:
                    handler.flush()
                except Exception:
                    pass

    def _drain_and_flush(self) -> None:
        """Drain remaining queue and flush all handlers on shutdown."""
        while not self.handler.log_queue.empty():
            try:
                record = self.handler.log_queue.get_nowait()
                self._emit_to_handlers(record)
            except queue.Empty:
                break
        self._flush_handlers()


class AsyncHandlerWrapper(logging.Handler):
    """Wrapper that makes any handler asynchronous.

    This provides a simpler interface for adding async behavior to
    existing handlers without modifying the logging configuration.

    Example:
        console_handler = logging.StreamHandler(sys.stdout)
        async_handler = AsyncHandlerWrapper(console_handler)
        logger.addHandler(async_handler)
    """

    def __init__(self, wrapped_handler: logging.Handler, max_queue_size: int = 10000):
        super().__init__()
        self.wrapped_handler = wrapped_handler
        self.async_handler = AsyncLogHandler(max_queue_size)
        self.processor = BackgroundLogProcessor(self.async_handler)
        self.processor.start()
        atexit.register(self.shutdown)

    def emit(self, record: logging.LogRecord) -> None:
        """Queue the record for async processing."""
        self.async_handler.emit(record)

    def flush(self) -> None:
        """Flush the wrapped handler."""
        self.wrapped_handler.flush()

    def shutdown(self) -> None:
        """Shutdown the async processor."""
        self.processor.stop()

    def close(self) -> None:
        """Close both async handler and wrapped handler."""
        self.shutdown()
        self.wrapped_handler.close()
        super().close()


# Global processor reference for cleanup
_processor_instance: Optional[BackgroundLogProcessor] = None


def setup_async_logging() -> Optional[AsyncLogHandler]:
    """Setup async logging for the application.

    Returns:
        The async handler if successfully set up, None otherwise.
    """
    global _processor_instance

    async_handler = AsyncLogHandler()
    processor = BackgroundLogProcessor(async_handler)
    processor.start()
    _processor_instance = processor

    # Register cleanup at exit
    atexit.register(processor.stop)

    return async_handler


def shutdown_async_logging() -> None:
    """Shutdown the async logging processor gracefully."""
    global _processor_instance
    if _processor_instance:
        _processor_instance.stop()
        _processor_instance = None
