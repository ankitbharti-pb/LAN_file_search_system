"""Search result models."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Information about a source document used in the response."""

    document_id: str
    file_name: str
    file_type: str
    detected_doc_type: str
    chunks_used: int = Field(description="Number of chunks from this document")
    chunk_ids: list[str] = Field(default_factory=list, description="IDs of chunks used")


class SearchResultItem(BaseModel):
    """A single search result item."""

    document_id: str
    file_name: str
    file_type: str
    detected_doc_type: str
    chunk_text: str = Field(description="Matching chunk content")
    chunk_id: str
    score: float = Field(description="Relevance score (0-1)")
    page: int | None = Field(default=None, description="Page number if applicable")
    sheet_name: str | None = Field(default=None, description="Sheet name if applicable")
    heading_path: str | None = Field(default=None, description="Section path if applicable")
    highlights: list[str] = Field(
        default_factory=list, description="Highlighted matching text snippets"
    )
    entities: dict[str, Any] = Field(
        default_factory=dict, description="Relevant entities from this result"
    )
    temporal_context: str | None = Field(
        default=None, description="Temporal applicability of this result"
    )


class SearchResponse(BaseModel):
    """Complete search response."""

    query: str
    results: list[SearchResultItem]
    answer: str | None = Field(
        default=None, description="LLM-synthesized answer for complex queries"
    )
    total_results: int
    latency_ms: float
    cache_hit: bool = False
    response_tier: Literal["cache", "retrieval", "synthesis"] = "retrieval"
    sources: list[SourceInfo] = Field(
        default_factory=list, description="Unique sources used to generate the response"
    )


class SearchRequest(BaseModel):
    """Search request payload."""

    query: str = Field(min_length=1, max_length=1000)
    filters: dict[str, Any] | None = Field(
        default=None, description="Optional filters (doc_type, entities, etc.)"
    )
    limit: int = Field(default=10, ge=1, le=100)
    mode: Literal["auto", "retrieval", "synthesis"] = Field(
        default="auto",
        description="Response mode: auto selects based on query complexity",
    )
