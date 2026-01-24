"""Semantic cache for query responses."""

import logging
import pickle
import time
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
    """LRU cache with semantic similarity matching."""

    def __init__(
        self,
        similarity_threshold: float | None = None,
        ttl_seconds: int | None = None,
        max_entries: int | None = None,
    ):
        self.similarity_threshold = similarity_threshold or settings.cache_similarity_threshold
        self.ttl_seconds = ttl_seconds or settings.cache_ttl_seconds
        self.max_entries = max_entries or settings.cache_max_entries

        self._cache: dict[str, CachedResponse] = {}
        self._embeddings: dict[str, np.ndarray] = {}
        self._access_order: list[str] = []  # For LRU eviction

    async def get(self, query: str) -> CachedResponse | None:
        """Get a cached response for a semantically similar query."""
        if not self._cache:
            return None

        # Embed query
        query_embedding = embedder.embed(query)

        # Find similar cached queries
        best_match = None
        best_score = 0.0

        for cache_key, cached_embedding in self._embeddings.items():
            score = float(np.dot(query_embedding, cached_embedding))
            if score > best_score and score >= self.similarity_threshold:
                best_score = score
                best_match = cache_key

        if best_match is None:
            return None

        cached = self._cache.get(best_match)
        if cached is None:
            return None

        # Check TTL
        if time.time() - cached.created_at > self.ttl_seconds:
            self._remove(best_match)
            return None

        # Update access order
        self._touch(best_match)

        logger.debug(f"Cache hit: '{query}' matched '{cached.query}' (score={best_score:.3f})")
        return cached

    async def set(
        self,
        query: str,
        response: dict[str, Any],
        document_ids: list[str],
    ) -> None:
        """Cache a response."""
        # Generate cache key
        cache_key = self._generate_key(query)

        # Embed query
        query_embedding = embedder.embed(query)

        # Create cached response
        cached = CachedResponse(
            query=query,
            response=response,
            document_ids=document_ids,
        )

        # Evict if at capacity
        while len(self._cache) >= self.max_entries:
            self._evict_oldest()

        # Store
        self._cache[cache_key] = cached
        self._embeddings[cache_key] = query_embedding
        self._access_order.append(cache_key)

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
        self._access_order.clear()
        logger.info(f"Cleared {count} cache entries")

    def save(self, path: Path | None = None) -> None:
        """Save cache to disk."""
        path = path or settings.cache_path
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "cache": self._cache,
            "embeddings": {k: v.tolist() for k, v in self._embeddings.items()},
            "access_order": self._access_order,
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

            self._cache = data["cache"]
            self._embeddings = {k: np.array(v) for k, v in data["embeddings"].items()}
            self._access_order = data["access_order"]

            # Prune expired entries
            self._prune_expired()

            logger.info(f"Loaded {len(self._cache)} cache entries from {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return False

    def _generate_key(self, query: str) -> str:
        """Generate a cache key from query."""
        import hashlib

        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:16]

    def _remove(self, cache_key: str) -> None:
        """Remove an entry from cache."""
        self._cache.pop(cache_key, None)
        self._embeddings.pop(cache_key, None)
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)

    def _touch(self, cache_key: str) -> None:
        """Update access order for LRU."""
        if cache_key in self._access_order:
            self._access_order.remove(cache_key)
        self._access_order.append(cache_key)

    def _evict_oldest(self) -> None:
        """Evict the least recently used entry."""
        if self._access_order:
            oldest = self._access_order[0]
            self._remove(oldest)

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
