"""Core modules for the LAN File Search System."""

from core.document_processor import DocumentProcessor, document_processor
from core.utils import generate_document_id, compute_file_hash

__all__ = [
    "DocumentProcessor",
    "document_processor",
    "generate_document_id",
    "compute_file_hash",
]
