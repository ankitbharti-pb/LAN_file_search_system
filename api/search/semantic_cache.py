"""Semantic cache for query responses."""

import logging
import pickle
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from config.settings import settings
from indexing.embedder import embedder

logger = logging.getLogger(__name__)


@dataclass
class CachedResponse:
    """Cached search response."""

    query: str
    response: dict[str, Any]
    document_ids: list[str]  # Documents that contributed to response
    created_at: float = field(default_factory=time.time)


class SemanticCache:
    """LRU cache with vectorized semantic similarity matching."""

    def __init__(
        self,
        similarity_threshold: float | None = None,
        ttl_seconds: int | None = None,
        max_entries: int | None = None,
    ):
        self.similarity_threshold = similarity_threshold or settings.cache_similarity_threshold
        self.ttl_seconds = ttl_seconds or settings.cache_ttl_seconds
        self.max_entries = max_entries or settings.cache_max_entries

        self._cache: OrderedDict[str, CachedResponse] = OrderedDict()
        self._embeddings: dict[str, np.ndarray] = {}

        # Vectorized lookup: pre-built matrix of all cached embeddings
        self._embedding_matrix: np.ndarray | None = None
        self._embedding_keys: list[str] = []
        self._matrix_dirty: bool = True

    async def get(
        self,
        query: str,
        query_embedding: np.ndarray | None = None,
    ) -> CachedResponse | None:
        """Get a cached response for a semantically similar query.

        Args:
            query: Search query text
            query_embedding: Pre-computed query embedding (avoids redundant embed call)
        """
        if not self._cache:
            return None

        if query_embedding is None:
            query_embedding = embedder.embed(query)

        # Rebuild matrix if dirty
        if self._matrix_dirty:
            self._rebuild_matrix()

        if self._embedding_matrix is None or len(self._embedding_keys) == 0:
            return None

        # Vectorized similarity: single matrix multiply instead of O(N) loop
        # query (768,) @ matrix.T (768, N) -> scores (N,)
        scores = self._embedding_matrix @ query_embedding
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score < self.similarity_threshold:
            return None

        best_key = self._embedding_keys[best_idx]
        cached = self._cache.get(best_key)
        if cached is None:
            return None

        # Check TTL
        if time.time() - cached.created_at > self.ttl_seconds:
            self._remove(best_key)
            return None

        # Update LRU access order - O(1) with OrderedDict
        self._cache.move_to_end(best_key)

        logger.debug(f"Cache hit: '{query}' matched '{cached.query}' (score={best_score:.3f})")
        return cached

    async def set(
        self,
        query: str,
        response: dict[str, Any],
        document_ids: list[str],
        query_embedding: np.ndarray | None = None,
    ) -> None:
        """Cache a response.

        Args:
            query: Search query text
            response: Response data to cache
            document_ids: Document IDs that contributed to response
            query_embedding: Pre-computed query embedding (avoids redundant embed call)
        """
        cache_key = self._generate_key(query)

        if query_embedding is None:
            query_embedding = embedder.embed(query)

        cached = CachedResponse(
            query=query,
            response=response,
            document_ids=document_ids,
        )

        # Evict if at capacity - O(1) with OrderedDict
        while len(self._cache) >= self.max_entries:
            self._evict_oldest()

        # Store
        self._cache[cache_key] = cached
        self._embeddings[cache_key] = query_embedding
        self._matrix_dirty = True

        logger.debug(f"Cached response for: '{query}'")

    def invalidate_for_document(self, document_id: str) -> int:
        """Invalidate all cache entries that reference a document."""
        to_remove = []

        for cache_key, cached in self._cache.items():
            if document_id in cached.document_ids:
                to_remove.append(cache_key)

        for cache_key in to_remove:
            self._remove(cache_key)

        if to_remove:
            logger.debug(f"Invalidated {len(to_remove)} cache entries for document {document_id}")

        return len(to_remove)

    def clear(self) -> None:
        """Clear the entire cache."""
        count = len(self._cache)
        self._cache.clear()
        self._embeddings.clear()
        self._embedding_matrix = None
        self._embedding_keys = []
        self._matrix_dirty = True
        logger.info(f"Cleared {count} cache entries")

    def save(self, path: Path | None = None) -> None:
        """Save cache to disk."""
        path = path or settings.cache_path
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "cache": dict(self._cache),
            "embeddings": {k: v.tolist() for k, v in self._embeddings.items()},
            "access_order": list(self._cache.keys()),
        }

        with open(path, "wb") as f:
            pickle.dump(data, f)

        logger.info(f"Saved {len(self._cache)} cache entries to {path}")

    def load(self, path: Path | None = None) -> bool:
        """Load cache from disk."""
        path = path or settings.cache_path

        if not path.exists():
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            raw_cache = data["cache"]
            raw_embeddings = data["embeddings"]
            access_order = data.get("access_order", list(raw_cache.keys()))

            # Rebuild OrderedDict in access order
            self._cache = OrderedDict()
            for key in access_order:
                if key in raw_cache:
                    self._cache[key] = raw_cache[key]

            self._embeddings = {k: np.array(v) for k, v in raw_embeddings.items()}
            self._matrix_dirty = True

            # Prune expired entries
            self._prune_expired()

            logger.info(f"Loaded {len(self._cache)} cache entries from {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return False

    def _rebuild_matrix(self) -> None:
        """Stack all cached embeddings into a single numpy matrix for vectorized lookup."""
        if not self._embeddings:
            self._embedding_matrix = None
            self._embedding_keys = []
        else:
            self._embedding_keys = list(self._embeddings.keys())
            self._embedding_matrix = np.stack(
                [self._embeddings[k] for k in self._embedding_keys]
            )
        self._matrix_dirty = False

    def _generate_key(self, query: str) -> str:
        """Generate a cache key from query."""
        import hashlib

        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    def _remove(self, cache_key: str) -> None:
        """Remove an entry from cache."""
        self._cache.pop(cache_key, None)
        self._embeddings.pop(cache_key, None)
        self._matrix_dirty = True

    def _evict_oldest(self) -> None:
        """Evict the least recently used entry - O(1) with OrderedDict."""
        if self._cache:
            oldest_key, _ = self._cache.popitem(last=False)
            self._embeddings.pop(oldest_key, None)
            self._matrix_dirty = True

    def _prune_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        to_remove = []

        for cache_key, cached in self._cache.items():
            if now - cached.created_at > self.ttl_seconds:
                to_remove.append(cache_key)

        for cache_key in to_remove:
            self._remove(cache_key)

    @property
    def size(self) -> int:
        """Get number of cached entries."""
        return len(self._cache)


# Global instance
semantic_cache = SemanticCache()
