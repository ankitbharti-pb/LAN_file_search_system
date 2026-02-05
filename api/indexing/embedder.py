"""Text embedding using sentence-transformers."""

import logging
from typing import List

import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Wrapper around sentence-transformers for text embedding."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded successfully")
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self.model.get_sentence_embedding_dimension()

    def embed(self, text: str, source: str = "") -> np.ndarray:
        """Embed a single text string."""
        if not text.strip():
            return np.zeros(self.dimension)

        logger.info(f"[Embed] source={source}, text='{text[:80]}...' ({len(text)} chars)")
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize for cosine similarity
        )
        return embedding

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embed multiple texts efficiently."""
        if not texts:
            return np.zeros((0, self.dimension))

        # Filter empty texts
        non_empty_indices = [i for i, t in enumerate(texts) if t.strip()]
        non_empty_texts = [texts[i] for i in non_empty_indices]

        if not non_empty_texts:
            return np.zeros((len(texts), self.dimension))

        # Encode non-empty texts
        embeddings = self.model.encode(
            non_empty_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(non_empty_texts) > 100,
        )

        # Create result array with zeros for empty texts
        result = np.zeros((len(texts), self.dimension))
        for idx, embedding in zip(non_empty_indices, embeddings):
            result[idx] = embedding

        return result

    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        # Since embeddings are normalized, dot product = cosine similarity
        return float(np.dot(embedding1, embedding2))

    def find_similar(
        self,
        query_embedding: np.ndarray,
        embeddings: np.ndarray,
        top_k: int = 10,
    ) -> List[tuple[int, float]]:
        """Find most similar embeddings to query."""
        if len(embeddings) == 0:
            return []

        # Calculate similarities (dot product since normalized)
        similarities = np.dot(embeddings, query_embedding)

        # Get top-k indices
        k = min(top_k, len(similarities))
        top_indices = np.argpartition(similarities, -k)[-k:]
        top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

        return [(int(idx), float(similarities[idx])) for idx in top_indices]


# Global instance
embedder = Embedder()
