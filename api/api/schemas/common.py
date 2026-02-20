"""Common / shared response schemas."""

from datetime import datetime
from pydantic import BaseModel, Field


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

