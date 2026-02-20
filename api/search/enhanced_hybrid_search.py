"""Enhanced hybrid search with multi-vector RRF fusion retrieval.

Supports HyDE (Hypothetical Document Embeddings) for improved query-document matching.
Includes optional cross-encoder re-ranking and MMR diversity.
Optimized with parallel HyDE+BM25 execution and batch DB queries.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import numpy as np

from config.settings import settings
from indexing.embedder import embedder
from indexing.multi_vector_index import multi_vector_index
from indexing.keyword_index import keyword_index
from indexing.metadata_store import metadata_store
from models.search_result import SearchResultItem
from search.hyde import hyde_expander

logger = logging.getLogger(__name__)

# Lazy imports for optional components
_reranker = None
_mmr_selector = None


def get_reranker():
    """Lazy load reranker to avoid loading model unless needed."""
    global _reranker
    if _reranker is None:
        from search.reranker import reranker
        _reranker = reranker
    return _reranker


def get_mmr_selector():
    """Lazy load MMR selector."""
    global _mmr_selector
    if _mmr_selector is None:
        from search.mmr import mmr_selector
        _mmr_selector = mmr_selector
    return _mmr_selector

SourceType = Literal["main_vector", "summary_vector", "question_vector", "bm25"]


@dataclass
class DebugInfo:
    """Debug information for retrieval analysis."""

    query: str = ""
    hyde_enabled: bool = False
    hyde_hypothetical: Optional[str] = None  # Generated hypothetical document
    main_vector_results: list[tuple[str, float]] = field(default_factory=list)
    summary_vector_results: list[tuple[str, float]] = field(default_factory=list)
    question_vector_results: list[tuple[str, float]] = field(default_factory=list)
    bm25_results: list[tuple[str, float]] = field(default_factory=list)
    bm25_matched_keywords: dict[str, list[str]] = field(default_factory=dict)  # chunk_id -> matched keywords
    rrf_scores: dict[str, dict] = field(default_factory=dict)  # chunk_id -> {source: score}
    final_ranking: list[tuple[str, float]] = field(default_factory=list)
    source_attribution: dict[str, list[SourceType]] = field(default_factory=dict)


@dataclass
class EnhancedSearchResult:
    """Search result with optional debug information."""

    results: list[SearchResultItem]
    debug_info: DebugInfo | None = None


class EnhancedHybridSearch:
    """Multi-source RRF fusion retrieval with debug capabilities."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        k_constant: int | None = None,
    ):
        """
        Initialize enhanced hybrid search.

        Args:
            weights: Weights for each retrieval source
            k_constant: RRF constant (higher = more emphasis on top ranks). Uses settings.rrf_k_constant if not provided.
        """
        self.weights = weights or settings.multi_vector_weights
        self.k_constant = k_constant if k_constant is not None else settings.rrf_k_constant

    async def search(
        self,
        query: str,
        k: int = 10,
        filters: dict[str, Any] | None = None,
        debug: bool = False,
        document_id: str | None = None,
        query_type: str | None = None,
        query_embedding: np.ndarray | None = None,
        preferred_categories: list[str] | None = None,
    ) -> EnhancedSearchResult:
        """
        Execute enhanced hybrid search with multi-vector retrieval.

        Args:
            query: Search query
            k: Number of results to return
            filters: Optional filters (doc_type, entities)
            debug: If True, include debug information
            document_id: If provided, search only within this document
            query_type: Query type for adaptive weights ('factual', 'exploratory', 'comparative', 'aggregation')
            query_embedding: Pre-computed query embedding (avoids redundant embed call)

        Returns:
            EnhancedSearchResult with results and optional debug info
        """
        search_start = time.time()
        debug_info = DebugInfo(query=query) if debug else None

        # Select weight profile based on query type (if provided and not overridden in constructor)
        if query_type and self.weights == settings.multi_vector_weights:
            self.weights = settings.get_weight_profile(query_type)

        # Ensure we have query embedding (Phase 1: single embed)
        if query_embedding is None:
            query_embedding = embedder.embed(query, source="query_fallback")

        # Apply filters to get candidate chunk IDs
        t0 = time.time()
        filter_chunk_ids = None
        if document_id:
            # Search within specific document
            doc_chunks = await metadata_store.get_chunks_by_document(document_id)
            filter_chunk_ids = [c.id for c in doc_chunks]
        elif filters:
            filter_doc_ids = await self._apply_filters(filters)
            if filter_doc_ids is not None:
                if len(filter_doc_ids) == 0:
                    logger.warning("Doc-type filter matched 0 documents, proceeding without filter")
                else:
                    chunks = []
                    for doc_id in filter_doc_ids:
                        doc_chunks = await metadata_store.get_chunks_by_document(doc_id)
                        chunks.extend(doc_chunks)
                    filter_chunk_ids = [c.id for c in chunks]

            # Apply chunk-level entity filters (intersects with existing filter)
            filter_chunk_ids = await self._apply_chunk_entity_filters(
                filters, filter_chunk_ids
            )
        logger.info(f"[Latency] filters: {(time.time() - t0) * 1000:.0f}ms")

        # Phase 2: Run HyDE and BM25 in parallel
        # BM25 doesn't need HyDE-enhanced embedding, so start it concurrently
        search_k = k * 3

        async def _run_bm25():
            if debug:
                return keyword_index.search_with_keywords(query, k=search_k), True
            return keyword_index.search(query, k=search_k), False

        async def _run_hyde():
            if settings.enable_hyde:
                return await hyde_expander.expand_query(query, query_embedding=query_embedding)
            return query_embedding, None

        # Launch BM25 and HyDE concurrently
        t0 = time.time()
        bm25_task = asyncio.create_task(_run_bm25())
        hyde_task = asyncio.create_task(_run_hyde())

        # Await HyDE (may take 1-3s for LLM call, BM25 runs during this wait)
        final_embedding, hypothetical_text = await hyde_task
        if debug_info:
            debug_info.hyde_enabled = settings.enable_hyde
            debug_info.hyde_hypothetical = hypothetical_text

        # Vector search with final embedding (HyDE-enhanced or raw)
        # Runs 3 FAISS indices in parallel internally via thread pool
        t_faiss = time.time()
        vector_results = multi_vector_index.search(
            final_embedding,
            k=search_k,
            filter_ids=filter_chunk_ids,
        )
        logger.info(f"[Latency] faiss_search: {(time.time() - t_faiss) * 1000:.0f}ms")

        main_results = vector_results.get("main", [])
        summary_results = vector_results.get("summary", [])
        question_results = vector_results.get("question", [])

        # Get BM25 results (should be done by now since it ran during HyDE wait)
        t_bm25 = time.time()
        bm25_raw, was_debug = await bm25_task
        logger.info(f"[Latency] bm25_await: {(time.time() - t_bm25) * 1000:.0f}ms")
        logger.info(f"[Latency] hyde_bm25_parallel: {(time.time() - t0) * 1000:.0f}ms")

        bm25_matched_keywords: dict[str, list[str]] = {}
        if was_debug:
            bm25_results = [(cid, score) for cid, score, _ in bm25_raw]
            bm25_matched_keywords = {cid: kw for cid, _, kw in bm25_raw}
        else:
            bm25_results = bm25_raw

        # Apply chunk filter to BM25 results if needed
        if filter_chunk_ids:
            filter_set = set(filter_chunk_ids)
            bm25_results = [
                (cid, score) for cid, score in bm25_results if cid in filter_set
            ]
            bm25_matched_keywords = {
                cid: kw for cid, kw in bm25_matched_keywords.items() if cid in filter_set
            }

        # Store debug info
        if debug_info:
            debug_info.main_vector_results = main_results[:20]
            debug_info.summary_vector_results = summary_results[:20]
            debug_info.question_vector_results = question_results[:20]
            debug_info.bm25_results = bm25_results[:20]
            debug_info.bm25_matched_keywords = {
                cid: bm25_matched_keywords.get(cid, [])
                for cid, _ in bm25_results[:20]
            }

        # RRF fusion
        t0 = time.time()
        fused, rrf_details = self._multi_source_rrf(
            main_results=main_results,
            summary_results=summary_results,
            question_results=question_results,
            bm25_results=bm25_results,
        )
        logger.info(f"[Latency] rrf_fusion: {(time.time() - t0) * 1000:.0f}ms")

        if debug_info:
            debug_info.rrf_scores = rrf_details

        # Apply category-based relevance boosting if preferred categories detected
        if preferred_categories:
            fused = await self._apply_category_boost(fused, preferred_categories)

        # Apply optional post-processing: re-ranking and/or MMR
        t0 = time.time()
        top_results = await self._apply_post_processing(
            query=query,
            query_embedding=query_embedding,
            fused_results=fused,
            k=k,
        )
        logger.info(f"[Latency] post_processing: {(time.time() - t0) * 1000:.0f}ms")

        if debug_info:
            debug_info.final_ranking = top_results[:k]

        # Phase 3: Batch DB queries instead of N+1 individual calls
        t0 = time.time()
        top_chunk_ids = [cid for cid, _ in top_results]
        top_scores = {cid: score for cid, score in top_results}

        # Batch fetch all chunks in ONE query
        chunks = await metadata_store.get_chunks_by_ids(top_chunk_ids)
        chunks_map = {c.id: c for c in chunks}

        # Batch fetch all documents in ONE query
        doc_ids = list(set(c.document_id for c in chunks))
        documents = await metadata_store.get_documents_by_ids(doc_ids)
        docs_map = {d.id: d for d in documents}

        # Batch fetch chunk metadata for temporal_context
        chunk_meta_map = await metadata_store.get_chunk_metadata_batch(top_chunk_ids)
        logger.info(f"[Latency] db_batch_fetch: {(time.time() - t0) * 1000:.0f}ms")

        # Build results from in-memory maps (no DB calls)
        t0 = time.time()
        results = []
        source_attribution: dict[str, list[SourceType]] = {}

        # Pre-build source ID sets (avoids rebuilding per chunk)
        main_ids = {cid for cid, _ in main_results}
        summary_ids = {cid for cid, _ in summary_results}
        question_ids = {cid for cid, _ in question_results}
        bm25_ids = {cid for cid, _ in bm25_results}

        for chunk_id in top_chunk_ids:
            chunk = chunks_map.get(chunk_id)
            if not chunk:
                continue
            document = docs_map.get(chunk.document_id)
            if not document:
                continue

            score = top_scores[chunk_id]
            highlights = self._create_highlights(chunk.text, query)

            # Get enriched metadata from chunk metadata if available
            meta = chunk_meta_map.get(chunk.id)
            temporal_ctx = meta.temporal_context if meta else None
            chunk_title = meta.title if meta else None
            chunk_keywords = meta.keywords if meta else []

            result_item = SearchResultItem(
                document_id=document.id,
                file_name=document.file_name,
                file_type=document.file_type,
                detected_doc_type=document.detected_doc_type,
                chunk_text=chunk.text[:500],
                chunk_id=chunk.id,
                score=score,
                page=chunk.page,
                sheet_name=chunk.sheet_name,
                heading_path=chunk.heading_path,
                highlights=highlights,
                entities=chunk.entities,
                temporal_context=temporal_ctx,
                chunk_title=chunk_title,
                chunk_keywords=chunk_keywords,
            )
            results.append(result_item)

            # Track source attribution from pre-built sets
            sources: list[SourceType] = []
            if chunk_id in main_ids:
                sources.append("main_vector")
            if chunk_id in summary_ids:
                sources.append("summary_vector")
            if chunk_id in question_ids:
                sources.append("question_vector")
            if chunk_id in bm25_ids:
                sources.append("bm25")
            source_attribution[chunk_id] = sources
        logger.info(f"[Latency] result_building: {(time.time() - t0) * 1000:.0f}ms")

        if debug_info:
            debug_info.source_attribution = source_attribution

        logger.info(f"[Latency] enhanced_search_total: {(time.time() - search_start) * 1000:.0f}ms")
        return EnhancedSearchResult(results=results, debug_info=debug_info)

    async def _apply_post_processing(
        self,
        query: str,
        query_embedding,
        fused_results: list[tuple[str, float]],
        k: int,
    ) -> list[tuple[str, float]]:
        """Apply optional post-processing: re-ranking and/or MMR.

        Args:
            query: Search query
            query_embedding: Query embedding vector
            fused_results: Results from RRF fusion
            k: Number of final results to return

        Returns:
            Post-processed list of (chunk_id, score) tuples
        """
        # Get more candidates for re-ranking/MMR
        candidate_k = min(len(fused_results), settings.reranker_top_k if settings.reranker_enabled else k * 2)
        candidates = fused_results[:candidate_k]

        # Fetch chunk texts for re-ranking or MMR (they need the text)
        if settings.reranker_enabled or settings.mmr_enabled:
            # Batch fetch chunks instead of N+1 queries
            candidate_ids = [cid for cid, _ in candidates]
            chunks = await metadata_store.get_chunks_by_ids(candidate_ids)
            text_map = {c.id: c.text for c in chunks}

            results_with_text = [
                (chunk_id, score, text_map.get(chunk_id, ""))
                for chunk_id, score in candidates
            ]

            # Apply cross-encoder re-ranking
            if settings.reranker_enabled:
                try:
                    reranker = get_reranker()
                    reranked = reranker.rerank(query, results_with_text, top_k=k)
                    logger.debug(f"Re-ranked {len(reranked)} results with cross-encoder")

                    # Update results_with_text with reranked scores for potential MMR
                    reranked_dict = {cid: score for cid, score in reranked}
                    results_with_text = [
                        (cid, reranked_dict.get(cid, score), text)
                        for cid, score, text in results_with_text
                        if cid in reranked_dict
                    ]
                    results_with_text.sort(key=lambda x: x[1], reverse=True)

                    # If MMR not enabled, return reranked results
                    if not settings.mmr_enabled:
                        return [(cid, score) for cid, score, _ in results_with_text[:k]]

                except Exception as e:
                    logger.error(f"Re-ranking failed, using RRF results: {e}")

            # Apply MMR for diversity
            if settings.mmr_enabled:
                try:
                    mmr = get_mmr_selector()
                    mmr_results = mmr.select(
                        query_embedding=query_embedding,
                        results=results_with_text,
                        k=k,
                    )
                    logger.debug(f"MMR selected {len(mmr_results)} diverse results")
                    return mmr_results
                except Exception as e:
                    logger.error(f"MMR failed, using previous results: {e}")

            # Return results without MMR if it failed
            return [(cid, score) for cid, score, _ in results_with_text[:k]]

        # No post-processing, return top k from RRF
        return fused_results[:k]

    def _multi_source_rrf(
        self,
        main_results: list[tuple[str, float]],
        summary_results: list[tuple[str, float]],
        question_results: list[tuple[str, float]],
        bm25_results: list[tuple[str, float]],
    ) -> tuple[list[tuple[str, float]], dict[str, dict]]:
        """
        Combine results from multiple sources using weighted RRF.

        Returns:
            Tuple of (sorted results, detailed RRF scores per chunk)
        """
        scores: dict[str, float] = {}
        details: dict[str, dict] = {}

        # Process each source
        sources = [
            ("main_vector", main_results, self.weights.get("main_vector", 0.35)),
            ("summary_vector", summary_results, self.weights.get("summary_vector", 0.15)),
            ("question_vector", question_results, self.weights.get("question_vector", 0.25)),
            ("bm25", bm25_results, self.weights.get("bm25", 0.25)),
        ]

        for source_name, results, weight in sources:
            for rank, (chunk_id, original_score) in enumerate(results, 1):
                rrf_score = weight / (self.k_constant + rank)

                if chunk_id not in scores:
                    scores[chunk_id] = 0
                    details[chunk_id] = {}

                scores[chunk_id] += rrf_score
                details[chunk_id][source_name] = {
                    "rank": rank,
                    "original_score": original_score,
                    "rrf_contribution": rrf_score,
                }

        # Sort by combined score
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_results, details

    async def _apply_category_boost(
        self,
        fused_results: list[tuple[str, float]],
        preferred_categories: list[str],
        boost_factor: float = 1.3,
    ) -> list[tuple[str, float]]:
        """Boost scores for chunks whose category matches the query intent.

        Args:
            fused_results: RRF-fused results
            preferred_categories: Categories to boost (e.g., ["procedure", "definition"])
            boost_factor: Multiplier for matching chunks (default 1.3 = 30% boost)

        Returns:
            Re-scored and re-sorted results
        """
        if not preferred_categories or not fused_results:
            return fused_results

        # Batch fetch metadata for top candidates only (limit to avoid large DB queries)
        candidate_ids = [cid for cid, _ in fused_results[:50]]
        chunk_meta_map = await metadata_store.get_chunk_metadata_batch(candidate_ids)

        preferred_set = set(preferred_categories)
        boosted = []
        for chunk_id, score in fused_results:
            meta = chunk_meta_map.get(chunk_id)
            if meta and meta.category and meta.category in preferred_set:
                boosted.append((chunk_id, score * boost_factor))
            else:
                boosted.append((chunk_id, score))

        # Re-sort by boosted score
        boosted.sort(key=lambda x: x[1], reverse=True)
        return boosted

    async def _apply_filters(self, filters: dict[str, Any]) -> list[str] | None:
        """Apply filters and return matching document IDs."""
        candidate_ids = None

        # Filter by document type
        if "doc_type" in filters and filters["doc_type"]:
            type_ids = await metadata_store.filter_documents_by_type(filters["doc_type"])
            candidate_ids = set(type_ids)

        # Filter by document-level entities
        if "entities" in filters and filters["entities"]:
            for key, value in filters["entities"].items():
                entity_ids = await metadata_store.filter_documents_by_entity(key, value)
                if candidate_ids is None:
                    candidate_ids = set(entity_ids)
                else:
                    candidate_ids &= set(entity_ids)

        return list(candidate_ids) if candidate_ids is not None else None

    async def _apply_chunk_entity_filters(
        self, filters: dict[str, Any], existing_chunk_ids: list[str] | None
    ) -> list[str] | None:
        """Apply chunk-level entity filters and return matching chunk IDs.

        Args:
            filters: Filter dict, expects "chunk_entities" key with {entity_key: entity_value}
            existing_chunk_ids: Pre-existing chunk filter to intersect with

        Returns:
            Filtered chunk IDs or None if no chunk_entities filter present
        """
        if "chunk_entities" not in filters or not filters["chunk_entities"]:
            return existing_chunk_ids

        chunk_candidate_ids = None
        for key, value in filters["chunk_entities"].items():
            matched_ids = await metadata_store.filter_chunks_by_entity(key, value)
            if chunk_candidate_ids is None:
                chunk_candidate_ids = set(matched_ids)
            else:
                chunk_candidate_ids &= set(matched_ids)

        if chunk_candidate_ids is None:
            return existing_chunk_ids

        # Intersect with existing chunk filter if present
        if existing_chunk_ids is not None:
            chunk_candidate_ids &= set(existing_chunk_ids)

        return list(chunk_candidate_ids) if chunk_candidate_ids else existing_chunk_ids

    def _create_highlights(self, text: str, query: str) -> list[str]:
        """Create highlighted snippets showing query matches."""
        highlights = []
        query_terms = query.lower().split()
        text_lower = text.lower()

        for term in query_terms:
            if len(term) < 2:
                continue

            if term in text_lower:
                # Find context around match
                idx = text_lower.find(term)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(term) + 50)

                snippet = text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."

                highlights.append(snippet)

                if len(highlights) >= 3:
                    break

        return highlights


# Global instance
enhanced_hybrid_search = EnhancedHybridSearch()
