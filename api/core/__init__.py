"""Core modules for the LAN File Search System."""

from core.document_processor import DocumentProcessor, document_processor
from core.file_watcher import FileWatcher, file_watcher

__all__ = [
    "DocumentProcessor",
    "document_processor",
    "FileWatcher",
    "file_watcher",
]
