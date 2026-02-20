"""Chunking / enrichment / indexing response schemas.

Moved from ``api/api/routes/chunking.py`` to keep route files focused
on endpoint logic.
"""

from __future__ import annotations

from pydantic import BaseModel


class ChunkResponse(BaseModel):
    """Single chunk response."""

    id: str
    document_id: str
    text: str
    content_type: str
    hierarchy_level: int
    parent_chunk_id: str | None
    heading_path: str | None
    chunk_index: int
    is_semantic_boundary: bool


class ChunkDetailResponse(BaseModel):
    """Detailed chunk with metadata."""

    chunk: ChunkResponse
    metadata: dict | None
    questions: list[dict]


class ChunkListResponse(BaseModel):
    """List of chunks response."""

    document_id: str
    total_chunks: int
    chunks: list[ChunkResponse]


class ChunkTreeNode(BaseModel):
    """Node in chunk hierarchy tree."""

    id: str
    text: str
    content_type: str
    hierarchy_level: int
    title: str | None
    summary: str | None
    category: str | None
    children: list[ChunkTreeNode] = []


class ChunkTreeResponse(BaseModel):
    """Hierarchical chunk tree response."""

    document_id: str
    total_chunks: int
    tree: list[ChunkTreeNode]


class ChunkingResponse(BaseModel):
    """Chunking operation response."""

    document_id: str
    chunks_created: int
    status: str


class EnrichmentResponse(BaseModel):
    """Enrichment operation response."""

    document_id: str
    chunks_enriched: int
    questions_generated: int
    status: str


class IndexingResponse(BaseModel):
    """Multi-vector indexing response."""

    document_id: str
    main_vectors: int
    summary_vectors: int
    question_vectors: int
    status: str


class RetrievalDebugResponse(BaseModel):
    """Debug response for retrieval testing."""

    query: str
    results: list[dict]
    debug: dict | None


# Rebuild forward references for self-referencing model
ChunkTreeNode.model_rebuild()

