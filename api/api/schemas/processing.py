"""Processing-workflow response schemas.

Moved from ``api/api/routes/processing.py`` to keep route files focused
on endpoint logic.
"""

from pydantic import BaseModel


class ProcessingStatus(BaseModel):
    """Document processing status response."""

    document_id: str
    file_name: str
    file_type: str
    processing_status: str
    page_count: int | None = None
    has_layout: bool = False
    has_markdown: bool = False


class LayoutDetectionResponse(BaseModel):
    """Layout detection result response."""

    document_id: str
    pages: int
    status: str


class PageInfo(BaseModel):
    """Information about a single page."""

    page_number: int
    has_image: bool
    has_annotated_image: bool
    has_unfiltered_annotated_image: bool = False
    has_layout: bool
    detection_count: int = 0
    unfiltered_detection_count: int = 0
    boxes_removed_by_filter: int = 0


class PagesListResponse(BaseModel):
    """List of pages for a document."""

    document_id: str
    total_pages: int
    pages: list[PageInfo]


class DetectionInfo(BaseModel):
    """Single detection info."""

    bbox: list[float]
    label: str
    confidence: float


class PageLayoutResponse(BaseModel):
    """Layout detection results for a page."""

    page_number: int
    detections: list[DetectionInfo]


class MarkdownResponse(BaseModel):
    """Markdown content response."""

    document_id: str
    extracted_markdown: str | None
    reviewed_markdown: str | None
    processing_status: str


class MarkdownUpdateRequest(BaseModel):
    """Request to update reviewed markdown."""

    markdown: str


class VLMStatusResponse(BaseModel):
    """VLM availability status response."""

    status: str
    provider: str = ""
    model_loaded: bool = False
    configured_model: str = ""
    available_models: list[str] = []
    error: str | None = None


class TextExtractionResponse(BaseModel):
    """Text extraction result response."""

    document_id: str
    markdown: str
    status: str

