"""Chunking and enrichment routes for advanced RAG pipeline."""

import logging

from fastapi import APIRouter, HTTPException, Query

from core.document_processor import document_processor
from indexing.metadata_store import metadata_store
from search.enhanced_hybrid_search import enhanced_hybrid_search
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chunking", tags=["chunking"])


# ============== Chunking Endpoints ==============


@router.post("/{doc_id}/chunk", response_model=ChunkingResponse)
async def chunk_document(doc_id: str):
    """
    Trigger chunking for a document.

    Automatically selects strategy based on file type and settings:
    - Tabular files (CSV, Excel): row-batch chunking
    - Documents with CHUNKING_STRATEGY=paragraph: paragraph chunking
    - Documents with CHUNKING_STRATEGY=hierarchical (default): hierarchical + semantic chunking
    """
    try:
        chunks_created = await document_processor.chunk_document(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ChunkingResponse(
        document_id=doc_id,
        chunks_created=chunks_created,
        status="chunked",
    )


@router.post("/{doc_id}/enrich", response_model=EnrichmentResponse)
async def enrich_chunks(doc_id: str):
    """
    Trigger LLM enrichment for all chunks of a document.

    Extracts metadata, keywords, entities, and hypothetical questions.
    """
    try:
        enriched, questions = await document_processor.enrich_chunks(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return EnrichmentResponse(
        document_id=doc_id,
        chunks_enriched=enriched,
        questions_generated=questions,
        status="enriched",
    )


@router.post("/{doc_id}/index-vectors", response_model=IndexingResponse)
async def index_vectors(doc_id: str):
    """
    Build multi-vector index for a document's chunks.

    Creates embeddings for main text, summaries, and questions.
    """
    try:
        result = await document_processor.index_vectors(doc_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return IndexingResponse(
        document_id=doc_id,
        main_vectors=result["main_vectors"],
        summary_vectors=result["summary_vectors"],
        question_vectors=result["question_vectors"],
        status="indexed",
    )


# ============== Chunk Viewing Endpoints ==============


@router.get("/{doc_id}/chunks", response_model=ChunkListResponse)
async def list_chunks(doc_id: str):
    """List all chunks for a document."""
    # Verify document exists
    document = await metadata_store.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = await metadata_store.get_chunks_by_document(doc_id)

    return ChunkListResponse(
        document_id=doc_id,
        total_chunks=len(chunks),
        chunks=[
            ChunkResponse(
                id=c.id,
                document_id=c.document_id,
                text=c.text[:200] + "..." if len(c.text) > 200 else c.text,
                content_type=c.content_type,
                hierarchy_level=c.hierarchy_level,
                parent_chunk_id=c.parent_chunk_id,
                heading_path=c.heading_path,
                chunk_index=c.chunk_index,
                is_semantic_boundary=c.is_semantic_boundary,
            )
            for c in chunks
        ],
    )


@router.get("/{doc_id}/chunks/{chunk_id}", response_model=ChunkDetailResponse)
async def get_chunk_detail(doc_id: str, chunk_id: str):
    """Get detailed chunk information with metadata."""
    # Get chunk with metadata
    data = await metadata_store.get_chunk_with_metadata(chunk_id)
    if not data:
        raise HTTPException(status_code=404, detail="Chunk not found")

    chunk = data["chunk"]
    metadata = data["metadata"]
    questions = data["questions"]

    # Verify it belongs to the document
    if chunk.document_id != doc_id:
        raise HTTPException(status_code=404, detail="Chunk not found in this document")

    return ChunkDetailResponse(
        chunk=ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            text=chunk.text,
            content_type=chunk.content_type,
            hierarchy_level=chunk.hierarchy_level,
            parent_chunk_id=chunk.parent_chunk_id,
            heading_path=chunk.heading_path,
            chunk_index=chunk.chunk_index,
            is_semantic_boundary=chunk.is_semantic_boundary,
        ),
        metadata=metadata.model_dump() if metadata else None,
        questions=[q.model_dump() for q in questions],
    )


@router.get("/{doc_id}/chunk-tree", response_model=ChunkTreeResponse)
async def get_chunk_tree(doc_id: str):
    """Get hierarchical tree structure of chunks."""
    # Verify document exists
    document = await metadata_store.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get tree from metadata store
    tree_data = await metadata_store.get_chunk_tree(doc_id)

    # Convert to response model
    def convert_node(node: dict) -> ChunkTreeNode:
        return ChunkTreeNode(
            id=node["id"],
            text=node["text"],
            content_type=node["content_type"],
            hierarchy_level=node["hierarchy_level"],
            title=node.get("title"),
            summary=node.get("summary"),
            category=node.get("category"),
            children=[convert_node(c) for c in node.get("children", [])],
        )

    tree = [convert_node(n) for n in tree_data]
    total_chunks = sum(1 for _ in _flatten_tree(tree_data))

    return ChunkTreeResponse(
        document_id=doc_id,
        total_chunks=total_chunks,
        tree=tree,
    )


def _flatten_tree(nodes: list[dict]) -> list[dict]:
    """Flatten tree for counting."""
    for node in nodes:
        yield node
        yield from _flatten_tree(node.get("children", []))


# ============== Retrieval Debug Endpoints ==============


@router.post("/{doc_id}/test-retrieval", response_model=RetrievalDebugResponse)
async def test_retrieval(
    doc_id: str,
    query: str = Query(..., description="Search query to test"),
    k: int = Query(10, ge=1, le=50, description="Number of results"),
):
    """
    Test retrieval against a specific document with debug information.

    Shows results from all retrieval sources and RRF fusion details.
    """
    # Verify document exists
    document = await metadata_store.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Run enhanced search with debug
    result = await enhanced_hybrid_search.search(
        query=query,
        k=k,
        debug=True,
        document_id=doc_id,
    )

    # Format debug info
    debug_dict = None
    if result.debug_info:
        debug_dict = {
            "main_vector_results": [
                {"chunk_id": cid, "score": score}
                for cid, score in result.debug_info.main_vector_results
            ],
            "summary_vector_results": [
                {"chunk_id": cid, "score": score}
                for cid, score in result.debug_info.summary_vector_results
            ],
            "question_vector_results": [
                {"chunk_id": cid, "score": score}
                for cid, score in result.debug_info.question_vector_results
            ],
            "bm25_results": [
                {
                    "chunk_id": cid,
                    "score": score,
                    "matched_keywords": result.debug_info.bm25_matched_keywords.get(cid, []),
                }
                for cid, score in result.debug_info.bm25_results
            ],
            "rrf_scores": result.debug_info.rrf_scores,
            "source_attribution": result.debug_info.source_attribution,
        }

    return RetrievalDebugResponse(
        query=query,
        results=[r.model_dump() for r in result.results],
        debug=debug_dict,
    )

