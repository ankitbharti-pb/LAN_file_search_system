"""API routes for the LAN File Search System."""

from api.routes.health import router as health_router
from api.routes.search import router as search_router
from api.routes.documents import router as documents_router
from api.routes.stats import router as stats_router
from api.routes.admin import router as admin_router
from api.routes.files import router as files_router
from api.routes.processing import router as processing_router
from api.routes.chunking import router as chunking_router

__all__ = [
    "health_router",
    "search_router",
    "documents_router",
    "stats_router",
    "admin_router",
    "files_router",
    "processing_router",
    "chunking_router",
]
