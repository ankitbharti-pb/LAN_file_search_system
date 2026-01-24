"""Chunking and enrichment routes for advanced RAG pipeline."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from config.settings import settings
from indexing.metadata_store import metadata_store
from indexing.hierarchical_chunker import hierarchical_chunker
from indexing.semantic_chunker import create_semantic_chunker
from indexing.chunk_enricher import chunk_enricher
from indexing.embedder import embedder
from indexing.multi_vector_index import multi_vector_index
from indexing.keyword_index import keyword_index
from models.chunk import Chunk, ChunkMetadata, ChunkQuestion, VectorEmbedding
from search.enhanced_hybrid_search import enhanced_hybrid_search, DebugInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/processing", tags=["chunking"])


# ============== Response Models ==============


class ChunkResponse(BaseModel):
    """Single chunk response."""

    id: str
    document_id: str
    text: str
    content_type: str
    hierarchy_level: int
    parent_chunk_id: str | None
    heading_path: str | None
    chunk_index: int
    is_semantic_boundary: bool


class ChunkDetailResponse(BaseModel):
    """Detailed chunk with metadata."""

    chunk: ChunkResponse
    metadata: dict | None
    questions: list[dict]


class ChunkListResponse(BaseModel):
    """List of chunks response."""

    document_id: str
    total_chunks: int
    chunks: list[ChunkResponse]


class ChunkTreeNode(BaseModel):
    """Node in chunk hierarchy tree."""

    id: str
    text: str
    content_type: str
    hierarchy_level: int
    title: str | None
    summary: str | None
    category: str | None
    children: list["ChunkTreeNode"] = []


class ChunkTreeResponse(BaseModel):
    """Hierarchical chunk tree response."""

    document_id: str
    total_chunks: int
    tree: list[ChunkTreeNode]


class ChunkingResponse(BaseModel):
    """Chunking operation response."""

    document_id: str
    chunks_created: int
    status: str


class EnrichmentResponse(BaseModel):
    """Enrichment operation response."""

    document_id: str
    chunks_enriched: int
    questions_generated: int
    status: str


class IndexingResponse(BaseModel):
    """Multi-vector indexing response."""

    document_id: str
    main_vectors: int
    summary_vectors: int
    question_vectors: int
    status: str


class RetrievalDebugResponse(BaseModel):
    """Debug response for retrieval testing."""

    query: str
    results: list[dict]
    debug: dict | None


# ============== Chunking Endpoints ==============


@router.post("/{doc_id}/chunk", response_model=ChunkingResponse)
async def chunk_document(doc_id: str):
    """
    Trigger hierarchical + semantic chunking for a document.

    For documents (PDF, DOCX, PPTX): Requires markdown to be available.
    For tabular files (CSV, Excel): Uses direct chunking without markdown.
    """
    # Get document
    document = await metadata_store.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check if tabular file - use direct chunking
    file_type = document.file_type.lower() if document.file_type else ""
    is_tabular = file_type in ("csv", "xlsx", "xls")

    if is_tabular:
        # Redirect to tabular chunking (no markdown needed)
        from api.routes.processing import chunk_tabular
        result = await chunk_tabular(doc_id)
        return ChunkingResponse(
            document_id=result.document_id,
            chunks_created=result.chunk_count,
            status=result.status,
        )

    # Get markdown content (for documents)
    markdown_data = await metadata_store.get_document_markdown(doc_id)
    if not markdown_data:
        raise HTTPException(status_code=400, detail="No markdown data found")

    # Use reviewed markdown if available, else extracted
    markdown = markdown_data.get("reviewed_markdown") or markdown_data.get("extracted_markdown")
    if not markdown:
        raise HTTPException(
            status_code=400,
            detail="No markdown content available. Extract text first."
        )

    # Parse layout data if available
    layout_data = None
    if document.layout_data:
        try:
            layout_data = json.loads(document.layout_data)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse layout data for {doc_id}")

    # Delete existing chunks
    await metadata_store.delete_chunks_by_document(doc_id)

    # Hierarchical chunking
    chunks = hierarchical_chunker.chunk_document(
        markdown=markdown,
        layout_data=layout_data,
        document_id=doc_id,
        file_name=document.file_name,
        detected_doc_type=document.detected_doc_type,
        entities=document.entities,
    )

    # Semantic chunking (refine large chunks)
    if settings.enable_semantic_chunking and chunks:
        semantic_chunker = create_semantic_chunker(embedder)
        chunks = semantic_chunker.refine_chunks(chunks, settings.max_chunk_size)

    # Save chunks
    await metadata_store.add_chunks(chunks)

    # Update status
    await metadata_store.update_document_status(doc_id, "chunked")

    logger.info(f"Created {len(chunks)} chunks for document {doc_id}")

    return ChunkingResponse(
        document_id=doc_id,
        chunks_created=len(chunks),
        status="chunked",
    )


@router.post("/{doc_id}/enrich", response_model=EnrichmentResponse)
async def enrich_chunks(doc_id: str):
    """
    Trigger LLM enrichment for all chunks of a document.

    Extracts metadata, keywords, entities, and hypothetical questions.
    """
    # Get document
    document = await metadata_store.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get chunks
    chunks = await metadata_store.get_chunks_by_document(doc_id)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No chunks found. Run chunking first."
        )

    # Prepare document context
    doc_context = {
        "file_name": document.file_name,
        "detected_doc_type": document.detected_doc_type,
        "summary": document.summary,
    }

    # Enrich chunks
    results = await chunk_enricher.enrich_batch(chunks, doc_context)

    # Save metadata and questions
    total_questions = 0
    for (metadata, questions), chunk in zip(results, chunks):
        # Save metadata
        await metadata_store.add_chunk_metadata(metadata)

        # Save questions
        if questions:
            await metadata_store.add_chunk_questions(chunk.id, questions)
            total_questions += len(questions)

    # Update status
    await metadata_store.update_document_status(doc_id, "enriched")

    logger.info(f"Enriched {len(chunks)} chunks with {total_questions} questions for {doc_id}")

    return EnrichmentResponse(
        document_id=doc_id,
        chunks_enriched=len(chunks),
        questions_generated=total_questions,
        status="enriched",
    )


@router.post("/{doc_id}/index-vectors", response_model=IndexingResponse)
async def index_vectors(doc_id: str):
    """
    Build multi-vector index for a document's chunks.

    Creates embeddings for main text, summaries, and questions.
    """
    # Get document
    document = await metadata_store.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get chunks
    chunks = await metadata_store.get_chunks_by_document(doc_id)
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No chunks found. Run chunking first."
        )

    main_count = 0
    summary_count = 0
    question_count = 0

    # Process each chunk
    for chunk in chunks:
        # Get metadata and questions
        metadata = await metadata_store.get_chunk_metadata(chunk.id)
        questions = await metadata_store.get_chunk_questions(chunk.id)

        # Main embedding (contextualized text)
        main_embedding = embedder.embed(chunk.contextualized_text)
        multi_vector_index.main_index.add(chunk.id, main_embedding)
        keyword_index.add(chunk.id, chunk.text)
        main_count += 1

        # Track vector embedding
        await metadata_store.add_vector_embedding(VectorEmbedding(
            id=chunk.id,
            chunk_id=chunk.id,
            vector_type="main",
            source_text=chunk.contextualized_text[:200],
        ))

        # Summary embedding (if available)
        if metadata and metadata.summary:
            summary_embedding = embedder.embed(metadata.summary)
            summary_id = f"{chunk.id}_summary"
            multi_vector_index.summary_index.add(summary_id, summary_embedding)
            summary_count += 1

            await metadata_store.add_vector_embedding(VectorEmbedding(
                id=summary_id,
                chunk_id=chunk.id,
                vector_type="summary",
                source_text=metadata.summary,
            ))

        # Question embeddings
        for question in questions:
            question_embedding = embedder.embed(question.question)
            question_vector_id = f"q_{chunk.id}_{question.id}"
            multi_vector_index.question_index.add(question_vector_id, question_embedding)
            multi_vector_index._question_to_chunk[question_vector_id] = chunk.id

            # Update question with vector ID
            if question.id:
                await metadata_store.update_question_vector_id(question.id, question_vector_id)

            await metadata_store.add_vector_embedding(VectorEmbedding(
                id=question_vector_id,
                chunk_id=chunk.id,
                vector_type="question",
                source_text=question.question,
                question_id=question.id,
            ))

            question_count += 1

    # Save indices
    multi_vector_index.save()
    keyword_index.save()

    # Update status
    await metadata_store.update_document_status(doc_id, "indexed")

    logger.info(
        f"Indexed document {doc_id}: "
        f"{main_count} main, {summary_count} summary, {question_count} question vectors"
    )

    return IndexingResponse(
        document_id=doc_id,
        main_vectors=main_count,
        summary_vectors=summary_count,
        question_vectors=question_count,
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


# Update ChunkTreeNode to allow forward references
ChunkTreeNode.model_rebuild()
