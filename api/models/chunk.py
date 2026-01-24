"""Chunk domain model."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """Represents a text chunk from a document."""

    id: str = Field(description="Unique chunk identifier")
    document_id: str = Field(description="Parent document ID")
    text: str = Field(description="Original chunk content")
    contextualized_text: str = Field(
        description="Enriched text with document context (what gets embedded)"
    )
    content_type: Literal["paragraph", "table", "list", "summary", "schema", "heading", "title", "section_header", "figure"] = Field(
        default="paragraph", description="Type of content in this chunk"
    )
    page: int | None = Field(default=None, description="Page number for PDFs")
    sheet_name: str | None = Field(default=None, description="Sheet name for Excel")
    heading_path: str | None = Field(
        default=None, description="Section hierarchy (e.g., '1. Introduction > 1.1 Overview')"
    )
    entities: dict[str, Any] = Field(
        default_factory=dict, description="Entities specific to this chunk"
    )
    chunk_index: int = Field(default=0, description="Position in document")

    # Hierarchical chunking fields
    parent_chunk_id: str | None = Field(
        default=None, description="Parent chunk ID for hierarchical structure"
    )
    hierarchy_level: int = Field(
        default=0, description="Level in hierarchy (0=doc, 1=h1, 2=h2, etc.)"
    )
    bbox: list[float] | None = Field(
        default=None, description="Bounding box [x1, y1, x2, y2] from layout detection"
    )
    layout_label: str | None = Field(
        default=None, description="Layout detection label (title, text, table, figure)"
    )

    # Semantic chunking fields
    is_semantic_boundary: bool = Field(
        default=False, description="Whether this chunk starts at a semantic boundary"
    )
    semantic_similarity_prev: float | None = Field(
        default=None, description="Similarity score with previous chunk (for detecting topic shifts)"
    )


class ChunkWithScore(BaseModel):
    """Chunk with search relevance score."""

    chunk: Chunk
    score: float = Field(description="Relevance score (0-1)")
    source: Literal["vector", "keyword", "hybrid", "main_vector", "summary_vector", "question_vector", "bm25"] = Field(
        default="hybrid", description="Which search method found this chunk"
    )


class ChunkMetadata(BaseModel):
    """LLM-enriched metadata for a chunk."""

    chunk_id: str = Field(description="Associated chunk ID")
    title: str | None = Field(default=None, description="Brief 3-8 word title")
    summary: str | None = Field(default=None, description="1-2 sentence summary")
    keywords: list[str] = Field(default_factory=list, description="5-10 keywords")
    entities: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Extracted entities {people, organizations, dates, amounts, locations}"
    )
    category: Literal["definition", "procedure", "data", "narrative", "example", "reference"] | None = Field(
        default=None, description="Content category"
    )
    contextual_description: str | None = Field(
        default=None, description="2-3 sentences explaining chunk's role in document"
    )
    enriched_at: datetime | None = Field(default=None, description="When enrichment was performed")


class ChunkQuestion(BaseModel):
    """Hypothetical question that a chunk answers."""

    id: int | None = Field(default=None, description="Question ID")
    chunk_id: str = Field(description="Associated chunk ID")
    question: str = Field(description="Hypothetical question")
    vector_id: str | None = Field(default=None, description="Vector ID in question index")


class VectorEmbedding(BaseModel):
    """Tracks vector embeddings for multi-vector retrieval."""

    id: str = Field(description="Vector ID")
    chunk_id: str = Field(description="Associated chunk ID")
    vector_type: Literal["main", "summary", "question"] = Field(
        description="Type of embedding"
    )
    source_text: str | None = Field(default=None, description="Text that was embedded")
    question_id: int | None = Field(
        default=None, description="Question ID for question vectors"
    )


class ChunkWithMetadata(BaseModel):
    """Chunk with its enriched metadata and questions."""

    chunk: Chunk
    metadata: ChunkMetadata | None = None
    questions: list[ChunkQuestion] = Field(default_factory=list)
