"""Enhanced hybrid search with multi-vector RRF fusion retrieval.

Supports HyDE (Hypothetical Document Embeddings) for improved query-document matching.
Includes optional cross-encoder re-ranking and MMR diversity.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

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

        Returns:
            EnhancedSearchResult with results and optional debug info
        """
        debug_info = DebugInfo(query=query) if debug else None

        # Select weight profile based on query type (if provided and not overridden in constructor)
        if query_type and self.weights == settings.multi_vector_weights:
            self.weights = settings.get_weight_profile(query_type)

        # Apply filters to get candidate chunk IDs
        filter_chunk_ids = None
        if document_id:
            # Search within specific document
            doc_chunks = await metadata_store.get_chunks_by_document(document_id)
            filter_chunk_ids = [c.id for c in doc_chunks]
        elif filters:
            filter_doc_ids = await self._apply_filters(filters)
            if filter_doc_ids is not None:
                if len(filter_doc_ids) == 0:
                    return EnhancedSearchResult(results=[], debug_info=debug_info)
                chunks = []
                for doc_id in filter_doc_ids:
                    doc_chunks = await metadata_store.get_chunks_by_document(doc_id)
                    chunks.extend(doc_chunks)
                filter_chunk_ids = [c.id for c in chunks]

        # Embed query with optional HyDE expansion
        hypothetical_text = None
        if settings.enable_hyde:
            query_embedding, hypothetical_text = await hyde_expander.expand_query(query)
            if debug_info:
                debug_info.hyde_enabled = True
                debug_info.hyde_hypothetical = hypothetical_text
        else:
            query_embedding = embedder.embed(query)

        # Search all vector indices
        search_k = k * 3
        vector_results = multi_vector_index.search_all(
            query_embedding,
            k=search_k,
            filter_ids=filter_chunk_ids,
        )

        main_results = vector_results.get("main", [])
        summary_results = vector_results.get("summary", [])
        question_results = vector_results.get("question", [])

        # Search BM25 keyword index
        bm25_matched_keywords: dict[str, list[str]] = {}
        if debug:
            # Use search_with_keywords to get matched keywords for debug
            bm25_results_with_kw = keyword_index.search_with_keywords(query, k=search_k)
            bm25_results = [(cid, score) for cid, score, _ in bm25_results_with_kw]
            bm25_matched_keywords = {cid: kw for cid, _, kw in bm25_results_with_kw}
        else:
            bm25_results = keyword_index.search(query, k=search_k)

        # Apply chunk filter to BM25 results if needed
        if filter_chunk_ids:
            filter_set = set(filter_chunk_ids)
            bm25_results = [
                (cid, score) for cid, score in bm25_results if cid in filter_set
            ]
            # Also filter keywords mapping
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
        fused, rrf_details = self._multi_source_rrf(
            main_results=main_results,
            summary_results=summary_results,
            question_results=question_results,
            bm25_results=bm25_results,
        )

        if debug_info:
            debug_info.rrf_scores = rrf_details

        # Apply optional post-processing: re-ranking and/or MMR
        top_results = await self._apply_post_processing(
            query=query,
            query_embedding=query_embedding,
            fused_results=fused,
            k=k,
        )

        if debug_info:
            debug_info.final_ranking = top_results[:k]

        results = []
        source_attribution: dict[str, list[SourceType]] = {}

        for chunk_id, score in top_results:
            result_item = await self._build_result_item(chunk_id, score, query)
            if result_item:
                results.append(result_item)

                # Track source attribution
                sources = self._get_sources(
                    chunk_id,
                    main_results,
                    summary_results,
                    question_results,
                    bm25_results,
                )
                source_attribution[chunk_id] = sources

        if debug_info:
            debug_info.source_attribution = source_attribution

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
            results_with_text = []
            for chunk_id, score in candidates:
                chunk = await metadata_store.get_chunk(chunk_id)
                if chunk:
                    results_with_text.append((chunk_id, score, chunk.text))
                else:
                    results_with_text.append((chunk_id, score, ""))

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

    def _get_sources(
        self,
        chunk_id: str,
        main_results: list[tuple[str, float]],
        summary_results: list[tuple[str, float]],
        question_results: list[tuple[str, float]],
        bm25_results: list[tuple[str, float]],
    ) -> list[SourceType]:
        """Determine which sources contributed to finding a chunk."""
        sources: list[SourceType] = []

        main_ids = {cid for cid, _ in main_results}
        summary_ids = {cid for cid, _ in summary_results}
        question_ids = {cid for cid, _ in question_results}
        bm25_ids = {cid for cid, _ in bm25_results}

        if chunk_id in main_ids:
            sources.append("main_vector")
        if chunk_id in summary_ids:
            sources.append("summary_vector")
        if chunk_id in question_ids:
            sources.append("question_vector")
        if chunk_id in bm25_ids:
            sources.append("bm25")

        return sources

    async def _apply_filters(self, filters: dict[str, Any]) -> list[str] | None:
        """Apply filters and return matching document IDs."""
        candidate_ids = None

        # Filter by document type
        if "doc_type" in filters and filters["doc_type"]:
            type_ids = await metadata_store.filter_documents_by_type(filters["doc_type"])
            candidate_ids = set(type_ids)

        # Filter by entities
        if "entities" in filters and filters["entities"]:
            for key, value in filters["entities"].items():
                entity_ids = await metadata_store.filter_documents_by_entity(key, value)
                if candidate_ids is None:
                    candidate_ids = set(entity_ids)
                else:
                    candidate_ids &= set(entity_ids)

        return list(candidate_ids) if candidate_ids is not None else None

    async def _build_result_item(
        self,
        chunk_id: str,
        score: float,
        query: str,
    ) -> SearchResultItem | None:
        """Build a search result item from a chunk."""
        # Get chunk from metadata store
        chunk = await metadata_store.get_chunk(chunk_id)
        if not chunk:
            return None

        # Get document
        document = await metadata_store.get_document(chunk.document_id)
        if not document:
            return None

        # Create highlights
        highlights = self._create_highlights(chunk.text, query)

        return SearchResultItem(
            document_id=document.id,
            file_name=document.file_name,
            file_type=document.file_type,
            detected_doc_type=document.detected_doc_type,
            chunk_text=chunk.text[:500],  # Truncate for response
            chunk_id=chunk.id,
            score=score,
            page=chunk.page,
            sheet_name=chunk.sheet_name,
            heading_path=chunk.heading_path,
            highlights=highlights,
            entities=chunk.entities,
        )

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
