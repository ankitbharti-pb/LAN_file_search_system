"""API request/response schemas."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


# Re-export from models for convenience
from models.search_result import SearchRequest, SearchResponse, SearchResultItem
from models.document import Document, DocumentSummary


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatsResponse(BaseModel):
    """System statistics response."""

    total_documents: int
    total_chunks: int
    documents_by_detected_type: dict[str, int]
    documents_by_file_type: dict[str, int]
    # Multi-vector index stats
    main_vectors: int
    summary_vectors: int
    question_vectors: int
    keyword_index_size: int
    cache_entries: int


class ReindexRequest(BaseModel):
    """Reindex request."""

    force: bool = Field(
        default=False,
        description="Force reindex even if files haven't changed",
    )


class ReindexResponse(BaseModel):
    """Reindex operation response."""

    status: str
    processed: int
    failed: int
    skipped: int
    message: str


class ClearCacheResponse(BaseModel):
    """Clear cache response."""

    status: str
    entries_cleared: int
    message: str


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str
    error_code: str | None = None


# File Browser Schemas
class FolderItem(BaseModel):
    """Item in a folder (file or subfolder)."""

    name: str
    type: Literal["file", "folder"]
    path: str  # Relative path from documents root
    size: int | None = None
    file_type: str | None = None
    is_supported: bool = False
    is_indexed: bool = False
    modified_at: datetime
    # Processing workflow fields
    doc_id: str | None = None
    processing_status: str | None = None  # pending|layout_detected|text_extracted|reviewed|indexed


class FolderContents(BaseModel):
    """Contents of a folder."""

    current_path: str
    parent_path: str | None
    items: list[FolderItem]


class CreateFolderRequest(BaseModel):
    """Request to create a new folder."""

    parent_path: str = Field(default="", description="Parent folder path (empty for root)")
    name: str = Field(..., min_length=1, max_length=255, description="New folder name")


class CreateFolderResponse(BaseModel):
    """Response after creating a folder."""

    path: str
    message: str


class UploadResponse(BaseModel):
    """Response after uploading files."""

    uploaded: list[str]
    failed: list[str]
    message: str


class FilePreview(BaseModel):
    """File preview content."""

    name: str
    path: str
    file_type: str
    size: int
    content_type: Literal["text", "table", "binary"]
    content: str | None = None  # Text content or JSON for tables
    is_indexed: bool = False
    indexed_summary: str | None = None
    # Processing workflow fields
    doc_id: str | None = None
    processing_status: str | None = None  # pending|layout_detected|text_extracted|reviewed|indexed
    page_count: int | None = None


class DeleteResponse(BaseModel):
    """Response after deleting a file."""

    path: str
    was_indexed: bool
    message: str
