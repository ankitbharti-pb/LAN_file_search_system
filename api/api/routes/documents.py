"""Documents endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Query

from api.schemas import Document, DocumentSummary
from indexing.metadata_store import metadata_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(
    skip: int = Query(default=0, ge=0, description="Number of documents to skip"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum documents to return"),
) -> list[DocumentSummary]:
    """List all indexed documents with pagination."""
    try:
        documents = await metadata_store.get_all_documents(skip=skip, limit=limit)
        return documents
    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/documents/{document_id}", response_model=Document)
async def get_document(document_id: str) -> Document:
    """Get detailed information about a specific document."""
    try:
        document = await metadata_store.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")
