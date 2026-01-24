"""API module for the LAN File Search System."""

from api.routes import (
    health_router,
    search_router,
    documents_router,
    stats_router,
    admin_router,
    files_router,
    processing_router,
    chunking_router,
)
from api.schemas import (
    HealthResponse,
    StatsResponse,
    ReindexRequest,
    ReindexResponse,
    ClearCacheResponse,
    ErrorResponse,
)

__all__ = [
    "health_router",
    "search_router",
    "documents_router",
    "stats_router",
    "admin_router",
    "files_router",
    "processing_router",
    "chunking_router",
    "HealthResponse",
    "StatsResponse",
    "ReindexRequest",
    "ReindexResponse",
    "ClearCacheResponse",
    "ErrorResponse",
]
