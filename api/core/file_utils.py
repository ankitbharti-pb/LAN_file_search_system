"""Shared file and path utility functions.

Centralises file-type detection, path validation, and processing
directory helpers that were previously duplicated across routes,
processors, and parsers.
"""

import os
from pathlib import Path

from fastapi import HTTPException

from config.settings import settings
from core.constants import TABULAR_EXTENSIONS


# -- File type helpers -------------------------------------------------------

def get_file_type(file_path: Path) -> str:
    """Return the lowercase extension without the leading dot."""
    return file_path.suffix.lower().lstrip(".")


def is_tabular(file_type: str) -> bool:
    """Check whether *file_type* (e.g. ``"csv"``) is a tabular format."""
    return file_type.lower() in TABULAR_EXTENSIONS


# -- Processing directory ----------------------------------------------------

def get_processing_dir(doc_id: str) -> Path:
    """Return ``data/processing/<doc_id>`` — the working directory for a
    document's intermediate artefacts (rendered pages, annotated images, etc.).
    """
    return settings.data_folder / "processing" / doc_id


# -- Watch-folder path helpers -----------------------------------------------

def validate_watch_folder_path(path: str) -> Path:
    """Validate and resolve *path* ensuring it stays inside the watch folder.

    Returns the resolved :class:`Path`.  Raises :class:`HTTPException` (400)
    on directory-traversal attempts.
    """
    if path in ("", ".", "/"):
        return settings.watch_folder

    # Normalise separators
    path = path.lstrip("/\\").replace("/", os.sep)

    full_path = (settings.watch_folder / path).resolve()

    try:
        full_path.relative_to(settings.watch_folder.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid path: path must be within documents folder",
        )

    return full_path


def get_relative_path(full_path: Path) -> str:
    """Return the POSIX relative path from the watch folder root.

    Always uses forward slashes for cross-platform URL compatibility.
    """
    try:
        rel = full_path.resolve().relative_to(settings.watch_folder.resolve())
        return rel.as_posix()
    except ValueError:
        return ""

