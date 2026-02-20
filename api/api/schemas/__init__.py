"""API request / response schemas.

Re-exports every public schema so that existing imports like
``from api.schemas import HealthResponse`` continue to work.
"""

# -- common -----------------------------------------------------------------
from api.schemas.common import (
    ErrorResponse,
    HealthResponse,
    StatsResponse,
    ReindexRequest,
    ReindexResponse,
    ClearCacheResponse,
)

# -- files ------------------------------------------------------------------
from api.schemas.files import (
    FolderItem,
    FolderContents,
    CreateFolderRequest,
    CreateFolderResponse,
    UploadResponse,
    FilePreview,
    DeleteResponse,
)

# -- processing -------------------------------------------------------------
from api.schemas.processing import (
    ProcessingStatus,
    LayoutDetectionResponse,
    PageInfo,
    PagesListResponse,
    DetectionInfo,
    PageLayoutResponse,
    MarkdownResponse,
    MarkdownUpdateRequest,
    VLMStatusResponse,
    TextExtractionResponse,
)

# -- chunking ---------------------------------------------------------------
from api.schemas.chunking import (
    ChunkResponse,
    ChunkDetailResponse,
    ChunkListResponse,
    ChunkTreeNode,
    ChunkTreeResponse,
    ChunkingResponse,
    EnrichmentResponse,
    IndexingResponse,
    RetrievalDebugResponse,
)

# -- search -----------------------------------------------------------------
from api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SourceInfo,
)

# -- model re-exports (kept for backwards compatibility) --------------------
from models.document import Document, DocumentSummary

__all__ = [
    # common
    "ErrorResponse",
    "HealthResponse",
    "StatsResponse",
    "ReindexRequest",
    "ReindexResponse",
    "ClearCacheResponse",
    # files
    "FolderItem",
    "FolderContents",
    "CreateFolderRequest",
    "CreateFolderResponse",
    "UploadResponse",
    "FilePreview",
    "DeleteResponse",
    # processing
    "ProcessingStatus",
    "LayoutDetectionResponse",
    "PageInfo",
    "PagesListResponse",
    "DetectionInfo",
    "PageLayoutResponse",
    "MarkdownResponse",
    "MarkdownUpdateRequest",
    "VLMStatusResponse",
    "TextExtractionResponse",
    # chunking
    "ChunkResponse",
    "ChunkDetailResponse",
    "ChunkListResponse",
    "ChunkTreeNode",
    "ChunkTreeResponse",
    "ChunkingResponse",
    "EnrichmentResponse",
    "IndexingResponse",
    "RetrievalDebugResponse",
    # search
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "SourceInfo",
    # model re-exports
    "Document",
    "DocumentSummary",
]

