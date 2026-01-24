"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
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
from indexing.metadata_store import metadata_store
from indexing.vector_index import vector_index
from indexing.keyword_index import keyword_index
from indexing.multi_vector_index import multi_vector_index
from search.semantic_cache import semantic_cache

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting LAN File Search System")

    # Initialize database
    await metadata_store.initialize()
    logger.info("Database initialized")

    # Load indexes
    vector_index.load()
    keyword_index.load()
    multi_vector_index.load()
    semantic_cache.load()
    logger.info("Indexes loaded")

    # Preload ML models for faster first request
    logger.info("Preloading ML models...")
    from processing.layout_detector import layout_detector
    from indexing.embedder import embedder

    _ = layout_detector.model  # Load DocLayout-YOLO
    _ = embedder.model         # Load embedding model
    logger.info("ML models preloaded successfully")

    # Create watch folder if it doesn't exist
    settings.watch_folder.mkdir(parents=True, exist_ok=True)
    logger.info(f"Watch folder: {settings.watch_folder}")

    # Note: Auto-processing removed - all processing is now manual via /processing endpoints

    yield

    # Shutdown
    logger.info("Shutting down LAN File Search System")

    # Save indexes
    vector_index.save()
    keyword_index.save()
    multi_vector_index.save()
    semantic_cache.save()
    logger.info("Indexes saved")


# Create FastAPI app
app = FastAPI(
    title="LAN File Search System",
    description="Search and query documents on your local network",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for LAN access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(search_router)
app.include_router(documents_router)
app.include_router(stats_router)
app.include_router(admin_router)
app.include_router(files_router)
app.include_router(processing_router)
app.include_router(chunking_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
