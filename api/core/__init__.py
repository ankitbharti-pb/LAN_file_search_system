"""Core modules for the LAN File Search System."""

from core.constants import TABULAR_EXTENSIONS, SUPPORTED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE
from core.document_processor import DocumentProcessor, document_processor
from core.file_utils import (
    get_file_type,
    get_processing_dir,
    get_relative_path,
    is_tabular,
    validate_watch_folder_path,
)
from core.utils import generate_document_id, compute_file_hash

__all__ = [
    # Constants
    "TABULAR_EXTENSIONS",
    "SUPPORTED_UPLOAD_EXTENSIONS",
    "MAX_UPLOAD_SIZE",
    # Document processor
    "DocumentProcessor",
    "document_processor",
    # File utilities
    "get_file_type",
    "get_processing_dir",
    "get_relative_path",
    "is_tabular",
    "validate_watch_folder_path",
    # Hash utilities
    "generate_document_id",
    "compute_file_hash",
]
