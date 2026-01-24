"""Statistics endpoint."""

import logging
from fastapi import APIRouter, HTTPException

from api.schemas import StatsResponse
from indexing.metadata_store import metadata_store
from indexing.vector_index import vector_index
from indexing.keyword_index import keyword_index
from search.semantic_cache import semantic_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Statistics"])


@router.get("/stats", response_model=StatsResponse)
async def get_statistics() -> StatsResponse:
    """Get system statistics."""
    try:
        db_stats = await metadata_store.get_statistics()

        return StatsResponse(
            total_documents=db_stats["total_documents"],
            total_chunks=db_stats["total_chunks"],
            documents_by_detected_type=db_stats["documents_by_detected_type"],
            documents_by_file_type=db_stats["documents_by_file_type"],
            vector_index_size=vector_index.size,
            keyword_index_size=keyword_index.size,
            cache_entries=semantic_cache.size,
        )
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")
