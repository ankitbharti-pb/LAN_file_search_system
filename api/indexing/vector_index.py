"""FAISS-based vector index for semantic search."""

import json
import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)


class VectorIndex:
    """FAISS vector index with ID mapping."""

    def __init__(self, dimension: int | None = None):
        self.dimension = dimension or settings.embedding_dimension
        self._index = None
        self._id_to_idx: dict[str, int] = {}  # chunk_id -> faiss index
        self._idx_to_id: dict[int, str] = {}  # faiss index -> chunk_id
        self._next_idx = 0

    @property
    def index(self):
        """Lazy load or create FAISS index."""
        if self._index is None:
            try:
                import faiss

                # Use IndexFlatIP for cosine similarity (normalized vectors)
                self._index = faiss.IndexFlatIP(self.dimension)
                logger.info(f"Created FAISS index with dimension {self.dimension}")
            except ImportError:
                raise ImportError(
                    "faiss-cpu not installed. Install with: pip install faiss-cpu"
                )
        return self._index

    def add(self, chunk_id: str, embedding: np.ndarray) -> None:
        """Add a single embedding to the index."""
        if chunk_id in self._id_to_idx:
            # Remove existing and re-add (FAISS doesn't support update)
            self.remove([chunk_id])

        # Ensure embedding is normalized and 2D
        embedding = embedding.astype(np.float32).reshape(1, -1)

        # Add to FAISS
        self.index.add(embedding)

        # Update mappings
        self._id_to_idx[chunk_id] = self._next_idx
        self._idx_to_id[self._next_idx] = chunk_id
        self._next_idx += 1

    def add_batch(self, chunk_ids: List[str], embeddings: np.ndarray) -> None:
        """Add multiple embeddings to the index."""
        if len(chunk_ids) != len(embeddings):
            raise ValueError("Number of IDs must match number of embeddings")

        # Remove any existing entries
        existing = [cid for cid in chunk_ids if cid in self._id_to_idx]
        if existing:
            self.remove(existing)

        # Ensure embeddings are float32 and 2D
        embeddings = embeddings.astype(np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Add to FAISS
        start_idx = self._next_idx
        self.index.add(embeddings)

        # Update mappings
        for i, chunk_id in enumerate(chunk_ids):
            idx = start_idx + i
            self._id_to_idx[chunk_id] = idx
            self._idx_to_id[idx] = chunk_id

        self._next_idx = start_idx + len(chunk_ids)

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter_ids: List[str] | None = None,
    ) -> List[Tuple[str, float]]:
        """Search for similar embeddings."""
        if self.index.ntotal == 0:
            return []

        # Ensure query is float32 and 2D
        query = query_embedding.astype(np.float32).reshape(1, -1)

        # If filtering, we need to search more and filter
        search_k = k
        if filter_ids:
            filter_set = set(filter_ids)
            search_k = min(self.index.ntotal, k * 10)  # Search more to ensure enough results

        # Search FAISS
        scores, indices = self.index.search(query, search_k)
        scores = scores[0]
        indices = indices[0]

        # Convert to chunk IDs and filter
        results = []
        for idx, score in zip(indices, scores):
            if idx < 0:  # FAISS returns -1 for no result
                continue

            chunk_id = self._idx_to_id.get(idx)
            if chunk_id is None:
                continue

            if filter_ids and chunk_id not in filter_set:
                continue

            results.append((chunk_id, float(score)))

            if len(results) >= k:
                break

        return results

    def remove(self, chunk_ids: List[str]) -> int:
        """Remove embeddings by chunk ID.

        Note: FAISS IndexFlatIP doesn't support removal.
        This method just removes from mappings. The index should be
        rebuilt periodically to reclaim space.
        """
        removed = 0
        for chunk_id in chunk_ids:
            if chunk_id in self._id_to_idx:
                idx = self._id_to_idx[chunk_id]
                del self._id_to_idx[chunk_id]
                if idx in self._idx_to_id:
                    del self._idx_to_id[idx]
                removed += 1
        return removed

    def save(self, index_path: Path, id_map_path: Path) -> None:
        """Save the index and ID mappings to disk."""

        # Create directories
        index_path.parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        try:
            import faiss

            faiss.write_index(self.index, str(index_path))
            logger.info(f"Saved FAISS index to {index_path}")
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")
            raise

        # Save ID mappings
        mappings = {
            "id_to_idx": self._id_to_idx,
            "idx_to_id": {str(k): v for k, v in self._idx_to_id.items()},
            "next_idx": self._next_idx,
        }
        with open(id_map_path, "w") as f:
            json.dump(mappings, f)
        logger.info(f"Saved ID mappings to {id_map_path}")

    def load(self, index_path: Path, id_map_path: Path) -> bool:
        """Load the index and ID mappings from disk."""

        if not index_path.exists() or not id_map_path.exists():
            logger.info("No existing index found")
            return False

        try:
            import faiss

            # Load FAISS index
            self._index = faiss.read_index(str(index_path))
            logger.info(f"Loaded FAISS index from {index_path} ({self._index.ntotal} vectors)")

            # Load ID mappings
            with open(id_map_path, "r") as f:
                mappings = json.load(f)

            self._id_to_idx = mappings["id_to_idx"]
            self._idx_to_id = {int(k): v for k, v in mappings["idx_to_id"].items()}
            self._next_idx = mappings["next_idx"]

            logger.info(f"Loaded {len(self._id_to_idx)} ID mappings")
            return True

        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            self._index = None
            self._id_to_idx = {}
            self._idx_to_id = {}
            self._next_idx = 0
            return False

    def clear(self) -> None:
        """Clear the entire index."""
        self._index = None
        self._id_to_idx = {}
        self._idx_to_id = {}
        self._next_idx = 0

    @property
    def size(self) -> int:
        """Get number of vectors in index."""
        return self.index.ntotal if self._index else 0

    @property
    def num_chunks(self) -> int:
        """Get number of chunk IDs (may differ from size if removals occurred)."""
        return len(self._id_to_idx)
