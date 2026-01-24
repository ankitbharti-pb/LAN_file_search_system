"""Document domain model."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class DocumentEntity(BaseModel):
    """Key-value entity extracted from a document."""

    key: str
    value: str


class Document(BaseModel):
    """Represents an indexed document."""

    id: str = Field(description="Unique document identifier (SHA256 of file path)")
    file_path: str = Field(description="Full path to the file")
    file_name: str = Field(description="Display name of the file")
    file_type: str = Field(description="File extension (pdf, docx, xlsx, csv, pptx)")
    file_hash: str = Field(description="SHA256 hash of file content for change detection")
    detected_doc_type: str = Field(
        default="unknown", description="LLM-detected document type (invoice, report, etc.)"
    )
    summary: str = Field(default="", description="LLM-generated 2-3 sentence summary")
    entities: dict[str, Any] = Field(
        default_factory=dict, description="Dynamic key-value pairs extracted by LLM"
    )
    key_topics: list[str] = Field(
        default_factory=list, description="Main topics covered in the document"
    )
    table_descriptions: list[str] = Field(
        default_factory=list, description="Natural language descriptions of tables"
    )
    indexed_at: datetime = Field(default_factory=datetime.utcnow)

    # Tabular-specific fields
    sheet_names: list[str] | None = Field(
        default=None, description="Sheet names for Excel files"
    )
    column_schema: dict[str, str] | None = Field(
        default=None, description="Column headers with detected data types"
    )
    row_count: int | None = Field(default=None, description="Number of rows for tabular data")
    date_range: str | None = Field(
        default=None, description="Date range if date columns detected"
    )

    # Processing workflow fields
    processing_status: str = Field(
        default="pending",
        description="Processing status: pending|layout_detected|text_extracted|reviewed|indexed"
    )
    layout_data: str | None = Field(
        default=None, description="JSON layout detection results (PDF only)"
    )
    extracted_markdown: str | None = Field(
        default=None, description="Generated markdown from text extraction"
    )
    reviewed_markdown: str | None = Field(
        default=None, description="User-reviewed/edited markdown"
    )
    page_count: int | None = Field(
        default=None, description="Number of pages (PDF/PPTX)"
    )


class DocumentSummary(BaseModel):
    """Brief document info for listing."""

    id: str
    file_name: str
    file_type: str
    detected_doc_type: str
    summary: str
    indexed_at: datetime
