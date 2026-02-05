"""HyDE (Hypothetical Document Embeddings) for improved retrieval.

This module implements query expansion using hypothetical document generation.
Instead of directly embedding the query, we generate a hypothetical answer
and use its embedding for retrieval, bridging the semantic gap between
short queries and detailed documents.

Reference: "Precise Zero-Shot Dense Retrieval without Relevance Labels"
"""

import logging
from typing import Optional

import numpy as np

from config.settings import settings
from indexing.embedder import embedder

logger = logging.getLogger(__name__)

# System prompt for hypothetical document generation
HYDE_SYSTEM_PROMPT = """You are a helpful assistant that generates detailed, factual responses.
Your task is to write a comprehensive paragraph that directly answers the given question.
Focus on providing specific, informative content that would be found in a relevant document.
Do not include phrases like "I think" or "In my opinion" - write as if stating facts from a document."""

HYDE_USER_PROMPT = """Question: {query}

Write a detailed paragraph (150-250 words) that would be found in a document answering this question.
Include specific details, terminology, and context that would typically appear in a relevant document.
Write the answer directly without any preamble."""


class HyDEQueryExpander:
    """Generate hypothetical documents to improve retrieval accuracy.

    HyDE works by:
    1. Taking a user query
    2. Using an LLM to generate a hypothetical document that would answer the query
    3. Embedding the hypothetical document
    4. Using that embedding for retrieval (better matches with actual documents)

    This bridges the semantic gap between short queries and detailed documents.
    """

    def __init__(self):
        self._llm_client = None

    @property
    def llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            from enrichment.llm_client import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    async def generate_hypothetical(self, query: str) -> Optional[str]:
        """Generate a hypothetical document that would answer the query.

        Args:
            query: The user's search query

        Returns:
            A hypothetical document text, or None if generation fails
        """
        try:
            prompt = HYDE_USER_PROMPT.format(query=query)

            response = await self.llm_client.complete(
                prompt=prompt,
                system_prompt=HYDE_SYSTEM_PROMPT,
                max_tokens=500,
                temperature=0.7,  # Some creativity for diverse hypotheticals
            )

            if response and len(response.strip()) > 50:
                logger.debug(f"Generated hypothetical document ({len(response)} chars)")
                return response.strip()
            else:
                logger.warning("HyDE generated empty or too short response")
                return None

        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            return None

    def get_hyde_embedding(
        self,
        query: str,
        hypothetical: str,
        alpha: float = 0.5,
        query_embedding: np.ndarray | None = None,
    ) -> np.ndarray:
        """Combine query and hypothetical embeddings.

        Args:
            query: Original user query
            hypothetical: Generated hypothetical document
            alpha: Weight for hypothetical (0=query only, 1=hypothetical only)
            query_embedding: Pre-computed query embedding (avoids redundant embed call)

        Returns:
            Combined embedding vector (L2 normalized)
        """
        query_emb = query_embedding if query_embedding is not None else embedder.embed(query, source="hyde_query_fallback")
        hypo_emb = embedder.embed(hypothetical, source="hyde_hypothetical")

        # Weighted combination
        combined = (1 - alpha) * query_emb + alpha * hypo_emb

        # L2 normalize the result
        norm = np.linalg.norm(combined)
        if norm > 0:
            combined = combined / norm

        return combined

    def _calculate_adaptive_alpha(self, query: str) -> float:
        """Calculate alpha based on query characteristics.

        Short, simple queries should trust the original query more.
        Longer, complex queries benefit more from hypothetical documents.

        Args:
            query: The user's search query

        Returns:
            Alpha value between hyde_alpha_min and hyde_alpha_max
        """
        query_words = len(query.split())

        # Short factual queries (1-3 words): trust query more
        if query_words <= 3:
            return settings.hyde_alpha_min

        # Question queries with clear intent (4-8 words with '?')
        if query.endswith('?') and query_words <= 8:
            return (settings.hyde_alpha_min + settings.hyde_alpha_max) / 2

        # Medium complexity (4-10 words)
        if query_words <= 10:
            return settings.hyde_alpha_max * 0.8

        # Complex queries (10+ words): trust hypothetical more
        return settings.hyde_alpha_max

    async def expand_query(
        self,
        query: str,
        query_embedding: np.ndarray | None = None,
    ) -> tuple[np.ndarray, Optional[str]]:
        """Expand a query using HyDE and return the enhanced embedding.

        Args:
            query: The user's search query
            query_embedding: Pre-computed query embedding (avoids redundant embed call)

        Returns:
            Tuple of (embedding, hypothetical_text)
            If HyDE fails, returns (query_embedding, None)
        """
        if query_embedding is None:
            query_embedding = embedder.embed(query, source="hyde_expand_fallback")

        if not settings.enable_hyde:
            return query_embedding, None

        hypothetical = await self.generate_hypothetical(query)

        if hypothetical:
            # Calculate alpha - adaptive or fixed based on settings
            if settings.hyde_adaptive:
                alpha = self._calculate_adaptive_alpha(query)
            else:
                alpha = settings.hyde_alpha

            # Use weighted combination of query and hypothetical
            embedding = self.get_hyde_embedding(
                query, hypothetical, alpha=alpha, query_embedding=query_embedding
            )
            logger.debug(f"Using HyDE-enhanced query embedding (alpha={alpha:.2f})")
            return embedding, hypothetical
        else:
            # Fall back to regular query embedding
            logger.debug("HyDE failed, using regular query embedding")
            return query_embedding, None


# Global instance with lazy loading
hyde_expander = HyDEQueryExpander()
