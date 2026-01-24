"""Admin endpoints."""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.schemas import ReindexRequest, ReindexResponse, ClearCacheResponse
from core.document_processor import document_processor
from search.semantic_cache import semantic_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

# Track background reindex status
_reindex_status = {"running": False, "result": None}


@router.post("/reindex", response_model=ReindexResponse)
async def trigger_reindex(
    background_tasks: BackgroundTasks,
    request: ReindexRequest = ReindexRequest(),
) -> ReindexResponse:
    """
    Trigger a full reindex of all documents.

    This operation runs in the background. Check /admin/reindex/status for progress.
    """
    global _reindex_status

    if _reindex_status["running"]:
        return ReindexResponse(
            status="in_progress",
            processed=0,
            failed=0,
            skipped=0,
            message="Reindex is already in progress",
        )

    # Start background reindex
    _reindex_status["running"] = True
    _reindex_status["result"] = None

    async def do_reindex():
        global _reindex_status
        try:
            result = await document_processor.reindex_all()
            _reindex_status["result"] = result
        except Exception as e:
            logger.error(f"Reindex failed: {e}", exc_info=True)
            _reindex_status["result"] = {"error": str(e)}
        finally:
            _reindex_status["running"] = False

    background_tasks.add_task(do_reindex)

    return ReindexResponse(
        status="started",
        processed=0,
        failed=0,
        skipped=0,
        message="Reindex started in background",
    )


@router.get("/reindex/status", response_model=ReindexResponse)
async def reindex_status() -> ReindexResponse:
    """Get the status of the current or last reindex operation."""
    if _reindex_status["running"]:
        return ReindexResponse(
            status="in_progress",
            processed=0,
            failed=0,
            skipped=0,
            message="Reindex is in progress",
        )

    result = _reindex_status["result"]
    if result is None:
        return ReindexResponse(
            status="idle",
            processed=0,
            failed=0,
            skipped=0,
            message="No reindex has been run",
        )

    if "error" in result:
        return ReindexResponse(
            status="failed",
            processed=0,
            failed=0,
            skipped=0,
            message=f"Reindex failed: {result['error']}",
        )

    return ReindexResponse(
        status="completed",
        processed=result.get("processed", 0),
        failed=result.get("failed", 0),
        skipped=result.get("skipped", 0),
        message="Reindex completed successfully",
    )


@router.post("/clear-cache", response_model=ClearCacheResponse)
async def clear_cache() -> ClearCacheResponse:
    """Clear all cached search responses."""
    try:
        entries = semantic_cache.size
        semantic_cache.clear()
        return ClearCacheResponse(
            status="success",
            entries_cleared=entries,
            message=f"Cleared {entries} cache entries",
        )
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
