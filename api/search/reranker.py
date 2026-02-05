"""Cross-encoder re-ranking for improved search relevance.

Uses a cross-encoder model to re-score query-document pairs for more accurate ranking.
Cross-encoders consider the full interaction between query and document, unlike
bi-encoders which encode them separately.
"""

import logging
import time
from typing import List, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Re-rank search results using a cross-encoder model.

    Cross-encoders are more accurate than bi-encoders for relevance scoring
    because they consider the full query-document interaction, but they're
    slower since they can't pre-compute document embeddings.

    Typical workflow:
    1. Use fast bi-encoder/BM25 to retrieve top N candidates
    2. Re-rank top N with cross-encoder for final ranking
    """

    def __init__(self, model_name: str | None = None):
        """Initialize the re-ranker.

        Args:
            model_name: Cross-encoder model name. Defaults to settings.reranker_model.
        """
        self.model_name = model_name or settings.reranker_model
        self._model = None

    @property
    def model(self):
        """Lazy load the cross-encoder model."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info(f"Loading cross-encoder model: {self.model_name}")
                self._model = CrossEncoder(self.model_name)
                logger.info("Cross-encoder model loaded successfully")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error(f"Failed to load cross-encoder model: {e}")
                raise
        return self._model

    def rerank(
        self,
        query: str,
        results: List[Tuple[str, float, str]],
        top_k: int | None = None,
        blend_ratio: float | None = None,
    ) -> List[Tuple[str, float]]:
        """Re-rank results using cross-encoder.

        Args:
            query: Search query
            results: List of (chunk_id, original_score, chunk_text) tuples
            top_k: Number of results to return. Defaults to settings.reranker_top_k.
            blend_ratio: Weight for cross-encoder score (0-1). Defaults to settings.reranker_blend_ratio.

        Returns:
            List of (chunk_id, blended_score) tuples, sorted by score descending
        """
        if not results:
            return []

        top_k = top_k or settings.reranker_top_k
        blend_ratio = blend_ratio if blend_ratio is not None else settings.reranker_blend_ratio

        # Limit to top_k for re-ranking (for performance)
        results_to_rerank = results[:top_k]

        # Prepare query-document pairs
        pairs = [(query, text) for _, _, text in results_to_rerank]

        try:
            # Get cross-encoder scores
            t0 = time.time()
            ce_scores = self.model.predict(pairs)
            logger.info(f"[Latency] reranker_predict: {(time.time() - t0) * 1000:.0f}ms ({len(pairs)} pairs)")

            # Normalize cross-encoder scores to 0-1 range
            min_score = min(ce_scores)
            max_score = max(ce_scores)
            score_range = max_score - min_score

            if score_range > 0:
                ce_scores_normalized = [(s - min_score) / score_range for s in ce_scores]
            else:
                ce_scores_normalized = [0.5] * len(ce_scores)

            # Blend scores: blend_ratio * ce_score + (1 - blend_ratio) * original_score
            blended_results = []
            for i, (chunk_id, original_score, _) in enumerate(results_to_rerank):
                # Normalize original score (assuming it's already roughly 0-1)
                blended_score = (
                    blend_ratio * ce_scores_normalized[i] +
                    (1 - blend_ratio) * original_score
                )
                blended_results.append((chunk_id, blended_score))

            # Sort by blended score descending
            blended_results.sort(key=lambda x: x[1], reverse=True)

            logger.debug(f"Re-ranked {len(blended_results)} results with cross-encoder")
            return blended_results

        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            # Fall back to original scores
            return [(chunk_id, score) for chunk_id, score, _ in results_to_rerank]

    def score_pair(self, query: str, text: str) -> float:
        """Score a single query-document pair.

        Args:
            query: Search query
            text: Document text

        Returns:
            Relevance score
        """
        try:
            score = self.model.predict([(query, text)])[0]
            return float(score)
        except Exception as e:
            logger.error(f"Scoring failed: {e}")
            return 0.0


# Global instance with lazy loading
reranker = CrossEncoderReranker()
