"""Shared utility functions."""

import hashlib
from pathlib import Path


def generate_document_id(file_path: Path) -> str:
    """Generate a unique document ID from file path."""
    path_str = str(file_path.absolute())
    return hashlib.sha256(path_str.encode()).hexdigest()[:32]


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file content."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
