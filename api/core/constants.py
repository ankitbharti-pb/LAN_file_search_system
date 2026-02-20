"""Shared constants used across the application."""

# File type sets
TABULAR_EXTENSIONS: set[str] = {"csv", "xlsx", "xls"}
SUPPORTED_UPLOAD_EXTENSIONS: set[str] = {"pdf", "docx", "xlsx", "xls", "csv", "pptx"}

# Upload limits
MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB

