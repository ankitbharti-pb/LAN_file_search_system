"""Maximum Marginal Relevance (MMR) for diverse search results.

MMR balances relevance with diversity by selecting documents that are both
relevant to the query and dissimilar to already-selected documents.

Reference: "The Use of MMR, Diversity-Based Reranking for Reordering Documents
and Producing Summaries" (Carbonell & Goldstein, 1998)
"""

import logging
from typing import List, Tuple

import numpy as np

from config.settings import settings
from indexing.embedder import embedder

logger = logging.getLogger(__name__)


class MMRSelector:
    """Select diverse results using Maximum Marginal Relevance.

    MMR formula: MMR = arg max [lambda * Sim(d, q) - (1-lambda) * max(Sim(d, d_selected))]

    Where:
    - lambda controls relevance vs diversity tradeoff
    - Sim(d, q) is query-document similarity
    - Sim(d, d_selected) is document-document similarity

    Higher lambda = more relevance, lower lambda = more diversity.
    """

    def __init__(self, lambda_param: float | None = None):
        """Initialize MMR selector.

        Args:
            lambda_param: Relevance/diversity tradeoff (0-1). Defaults to settings.mmr_lambda.
        """
        self.lambda_param = lambda_param if lambda_param is not None else settings.mmr_lambda

    def select(
        self,
        query_embedding: np.ndarray,
        results: List[Tuple[str, float, str]],
        k: int,
        lambda_param: float | None = None,
    ) -> List[Tuple[str, float]]:
        """Select top-k diverse results using MMR.

        Args:
            query_embedding: Query embedding vector
            results: List of (chunk_id, score, chunk_text) tuples
            k: Number of results to select
            lambda_param: Override lambda parameter

        Returns:
            List of (chunk_id, mmr_score) tuples
        """
        if not results:
            return []

        if len(results) <= k:
            return [(cid, score) for cid, score, _ in results]

        lambda_val = lambda_param if lambda_param is not None else self.lambda_param

        # Embed all candidate texts in a single batch call
        texts = [text for _, _, text in results]
        doc_embeddings = embedder.embed_batch(texts)

        # Normalize embeddings
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-9)
        doc_norms = doc_embeddings / (np.linalg.norm(doc_embeddings, axis=1, keepdims=True) + 1e-9)

        # Compute query-document similarities
        query_sims = np.dot(doc_norms, query_norm)

        # Track selected indices
        selected_indices: List[int] = []
        remaining_indices = list(range(len(results)))

        # Greedily select k documents using MMR
        for _ in range(k):
            if not remaining_indices:
                break

            best_score = float("-inf")
            best_idx = remaining_indices[0]

            for idx in remaining_indices:
                # Relevance score (query similarity)
                relevance = query_sims[idx]

                # Diversity penalty (max similarity to already selected)
                if selected_indices:
                    selected_embeddings = doc_norms[selected_indices]
                    doc_sim = np.dot(selected_embeddings, doc_norms[idx])
                    max_sim_to_selected = float(np.max(doc_sim))
                else:
                    max_sim_to_selected = 0.0

                # MMR score
                mmr_score = lambda_val * relevance - (1 - lambda_val) * max_sim_to_selected

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx

            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

        # Return selected results with MMR scores
        mmr_results = []
        for i, idx in enumerate(selected_indices):
            chunk_id = results[idx][0]
            # Use normalized position-based score for consistency
            mmr_score = 1.0 - (i / len(selected_indices)) * 0.5  # 1.0 to 0.5 range
            mmr_results.append((chunk_id, mmr_score))

        logger.debug(f"MMR selected {len(mmr_results)} diverse results (lambda={lambda_val})")
        return mmr_results

    def rerank_with_diversity(
        self,
        query: str,
        results: List[Tuple[str, float, str]],
        k: int,
    ) -> List[Tuple[str, float]]:
        """Convenience method: embed query and apply MMR.

        Args:
            query: Search query text
            results: List of (chunk_id, score, chunk_text) tuples
            k: Number of results to select

        Returns:
            List of (chunk_id, mmr_score) tuples
        """
        query_embedding = embedder.embed(query)
        return self.select(query_embedding, results, k)


# Global instance with lazy configuration
mmr_selector = MMRSelector()
