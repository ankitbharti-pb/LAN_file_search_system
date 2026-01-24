"""File watcher using watchdog for monitoring the shared folder."""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Literal

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from config.settings import settings
from parsers import parser_registry

logger = logging.getLogger(__name__)


class FileEventHandler(FileSystemEventHandler):
    """Handles file system events for supported file types."""

    def __init__(
        self,
        callback: Callable[[Path, Literal["created", "modified", "deleted"]], None],
        debounce_seconds: float = 2.0,
    ):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._pending_events: dict[str, tuple[str, float]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _is_supported(self, path: str) -> bool:
        """Check if file is a supported type."""
        return parser_registry.is_supported(Path(path))

    def _schedule_callback(self, path: str, action: Literal["created", "modified", "deleted"]):
        """Schedule a debounced callback."""
        import time

        # Store pending event with timestamp
        self._pending_events[path] = (action, time.time())

        # Schedule processing
        if self._loop:
            self._loop.call_later(
                self.debounce_seconds,
                lambda: self._process_pending(path),
            )

    def _process_pending(self, path: str):
        """Process a pending event if it hasn't been superseded."""
        import time

        if path not in self._pending_events:
            return

        action, timestamp = self._pending_events[path]

        # Check if this is still the latest event for this path
        if time.time() - timestamp >= self.debounce_seconds - 0.1:
            del self._pending_events[path]
            try:
                self.callback(Path(path), action)
            except Exception as e:
                logger.error(f"Error processing {action} event for {path}: {e}")

    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if event.is_directory:
            return
        if not self._is_supported(event.src_path):
            return
        logger.debug(f"File created: {event.src_path}")
        self._schedule_callback(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if event.is_directory:
            return
        if not self._is_supported(event.src_path):
            return
        logger.debug(f"File modified: {event.src_path}")
        self._schedule_callback(event.src_path, "modified")

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion."""
        if event.is_directory:
            return
        if not self._is_supported(event.src_path):
            return
        logger.debug(f"File deleted: {event.src_path}")
        self._schedule_callback(event.src_path, "deleted")


class FileWatcher:
    """Watches a directory for file changes."""

    def __init__(
        self,
        watch_path: Path | None = None,
        callback: Callable[[Path, Literal["created", "modified", "deleted"]], None] | None = None,
    ):
        self.watch_path = watch_path or settings.watch_folder
        self.callback = callback or self._default_callback
        self._observer: Observer | None = None
        self._event_handler: FileEventHandler | None = None

    def _default_callback(
        self, path: Path, action: Literal["created", "modified", "deleted"]
    ):
        """Default callback that logs events."""
        logger.info(f"File {action}: {path}")

    def start(self, loop: asyncio.AbstractEventLoop | None = None):
        """Start watching the directory."""
        if self._observer is not None:
            logger.warning("File watcher already running")
            return

        # Ensure watch path exists
        self.watch_path.mkdir(parents=True, exist_ok=True)

        # Create event handler
        self._event_handler = FileEventHandler(self.callback)
        self._event_handler._loop = loop or asyncio.get_event_loop()

        # Create and start observer
        self._observer = Observer()
        self._observer.schedule(
            self._event_handler,
            str(self.watch_path),
            recursive=True,
        )
        self._observer.start()

        logger.info(f"Started file watcher on: {self.watch_path}")

    def stop(self):
        """Stop watching the directory."""
        if self._observer is None:
            return

        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._event_handler = None

        logger.info("Stopped file watcher")

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._observer is not None and self._observer.is_alive()


# Global instance (initialized without callback - set in processing queue)
file_watcher = FileWatcher()
