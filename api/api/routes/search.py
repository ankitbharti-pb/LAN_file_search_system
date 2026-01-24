"""Search endpoint."""

import logging
from fastapi import APIRouter, HTTPException

from api.schemas import SearchRequest, SearchResponse
from search.response_generator import response_generator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Search"])


@router.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest) -> SearchResponse:
    """
    Search indexed documents.

    Supports three response modes:
    - **auto**: Automatically chooses based on query complexity
    - **retrieval**: Returns matching chunks without synthesis
    - **synthesis**: Uses LLM to generate a comprehensive answer
    """
    try:
        response = await response_generator.generate(
            query=request.query,
            mode=request.mode,
            k=request.limit,
            filters=request.filters,
        )
        return response
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
