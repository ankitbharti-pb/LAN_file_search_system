"""Response generation with optional LLM synthesis."""

import logging
import time
from typing import Literal

from config.settings import settings
from enrichment.llm_client import get_synthesis_llm_client
from enrichment.prompts import RESPONSE_SYNTHESIS_PROMPT
from indexing.embedder import embedder
from models.search_result import SearchResponse, SearchResultItem, SourceInfo
from search.semantic_cache import semantic_cache, CachedResponse
from search.enhanced_hybrid_search import enhanced_hybrid_search
from search.query_processor import query_processor, QueryIntent

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates search responses with optional LLM synthesis."""

    def __init__(self):
        self._llm_client = None

    async def generate(
        self,
        query: str,
        mode: Literal["auto", "retrieval", "synthesis"] = "auto",
        k: int = 10,
        filters: dict | None = None,
    ) -> SearchResponse:
        """
        Generate a search response.

        Args:
            query: Search query
            mode: Response mode (auto, retrieval, synthesis)
            k: Number of results
            filters: Optional search filters

        Returns:
            SearchResponse with results and optional synthesized answer
        """
        start_time = time.time()

        # Phase 1: Embed query ONCE, reuse throughout the pipeline
        t0 = time.time()
        query_embedding = embedder.embed(query, source="query")
        logger.info(f"[Latency] embed_query: {(time.time() - t0) * 1000:.0f}ms")

        # Step 1: Check cache (pass pre-computed embedding)
        t0 = time.time()
        cached = await semantic_cache.get(query, query_embedding=query_embedding)
        logger.info(f"[Latency] cache_check: {(time.time() - t0) * 1000:.0f}ms")
        if cached:
            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"[Latency] response_generator_total: {latency_ms:.0f}ms (cache hit)")
            response = cached.response
            response["latency_ms"] = latency_ms
            response["cache_hit"] = True
            response["response_tier"] = "cache"
            return SearchResponse(**response)

        # Step 2: Process query to understand intent
        t0 = time.time()
        intent = await query_processor.process(query)

        # Merge filters
        combined_filters = filters or {}
        if intent.doc_type_filter:
            combined_filters["doc_type"] = intent.doc_type_filter
        if intent.entity_filters:
            combined_filters["entities"] = intent.entity_filters
        logger.info(f"[Latency] query_processing: {(time.time() - t0) * 1000:.0f}ms")

        # Step 3: Execute search (pass pre-computed embedding)
        t0 = time.time()
        search_result = await enhanced_hybrid_search.search(
            query=query,
            k=k,
            filters=combined_filters if combined_filters else None,
            query_embedding=query_embedding,
        )
        results = search_result.results
        logger.info(f"[Latency] search_total: {(time.time() - t0) * 1000:.0f}ms")

        # Step 4: Determine response mode
        if mode == "auto":
            mode = "synthesis" if intent.needs_synthesis else "retrieval"

        # Step 5: Generate answer if synthesis mode
        answer = None
        response_tier: Literal["cache", "retrieval", "synthesis"] = "retrieval"

        if mode == "synthesis" and results:
            t0 = time.time()
            answer = await self._synthesize_answer(query, results)
            response_tier = "synthesis"
            logger.info(f"[Latency] synthesis: {(time.time() - t0) * 1000:.0f}ms")

        # Extract unique sources from results
        sources = self._extract_sources(results)

        # Build response
        latency_ms = (time.time() - start_time) * 1000
        response = SearchResponse(
            query=query,
            results=results,
            answer=answer,
            total_results=len(results),
            latency_ms=latency_ms,
            cache_hit=False,
            response_tier=response_tier,
            sources=sources,
        )

        # Cache the response (pass pre-computed embedding)
        t0 = time.time()
        document_ids = list(set(r.document_id for r in results))
        await semantic_cache.set(
            query=query,
            response=response.model_dump(),
            document_ids=document_ids,
            query_embedding=query_embedding,
        )
        logger.info(f"[Latency] cache_store: {(time.time() - t0) * 1000:.0f}ms")

        logger.info(f"[Latency] response_generator_total: {latency_ms:.0f}ms")
        return response

    async def _synthesize_answer(
        self,
        query: str,
        results: list[SearchResultItem],
    ) -> str:
        """Synthesize an answer from search results using LLM."""
        if self._llm_client is None:
            self._llm_client = get_synthesis_llm_client()

        # Format results for LLM
        results_text = self._format_results_for_llm(results)

        # Create prompt
        prompt = RESPONSE_SYNTHESIS_PROMPT.format(
            query=query,
            results=results_text,
        )

        try:
            answer = await self._llm_client.complete(
                prompt=prompt,
                max_tokens=settings.synthesis_max_tokens,
                temperature=settings.synthesis_temperature,
            )
            return answer.strip()
        except Exception as e:
            logger.error(f"Failed to synthesize answer: {e}")
            return None

    def _format_results_for_llm(self, results: list[SearchResultItem]) -> str:
        """Format search results for LLM consumption."""
        parts = []

        for i, result in enumerate(results[:settings.synthesis_max_chunks], 1):
            part = f"""
--- Source Chunk {i} ---
Document: {result.file_name}
Document Type: {result.detected_doc_type}
Section/Heading: {result.heading_path or 'N/A'}
Relevance Score: {result.score:.3f}
Temporal Context: {result.temporal_context or 'N/A'}
Content:
{result.chunk_text}
"""
            if result.entities:
                entities_str = ", ".join(f"{k}={v}" for k, v in list(result.entities.items())[:5])
                part += f"Key Info: {entities_str}\n"

            parts.append(part)

        return "\n".join(parts)

    def _extract_sources(self, results: list[SearchResultItem]) -> list[SourceInfo]:
        """Extract unique sources from search results."""
        sources_map: dict[str, SourceInfo] = {}

        for result in results:
            if result.document_id not in sources_map:
                sources_map[result.document_id] = SourceInfo(
                    document_id=result.document_id,
                    file_name=result.file_name,
                    file_type=result.file_type,
                    detected_doc_type=result.detected_doc_type,
                    chunks_used=1,
                    chunk_ids=[result.chunk_id],
                )
            else:
                sources_map[result.document_id].chunks_used += 1
                sources_map[result.document_id].chunk_ids.append(result.chunk_id)

        return list(sources_map.values())


# Global instance
response_generator = ResponseGenerator()
