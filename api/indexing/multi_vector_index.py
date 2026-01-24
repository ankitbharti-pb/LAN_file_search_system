"""Multi-vector FAISS index for advanced RAG retrieval."""

import logging
from pathlib import Path
from typing import Literal

import numpy as np

from indexing.vector_index import VectorIndex
from config.settings import settings

logger = logging.getLogger(__name__)

VectorType = Literal["main", "summary", "question"]


class MultiVectorIndex:
    """Manages 3 separate FAISS indices for multi-vector retrieval."""

    def __init__(self, dimension: int | None = None):
        """
        Initialize multi-vector index.

        Args:
            dimension: Embedding dimension (uses settings default if not provided)
        """
        self.dimension = dimension or settings.embedding_dimension

        # Create separate indices for each vector type
        self.main_index = VectorIndex(self.dimension)
        self.summary_index = VectorIndex(self.dimension)
        self.question_index = VectorIndex(self.dimension)

        # Question ID to chunk ID mapping (for question vectors)
        self._question_to_chunk: dict[str, str] = {}

    def add_chunk(
        self,
        chunk_id: str,
        main_embedding: np.ndarray | None = None,
        summary_embedding: np.ndarray | None = None,
        question_embeddings: list[tuple[str, np.ndarray]] | None = None,
    ) -> None:
        """
        Add embeddings for a chunk to the appropriate indices.

        Args:
            chunk_id: The chunk ID
            main_embedding: Embedding of the contextualized text
            summary_embedding: Embedding of the chunk summary
            question_embeddings: List of (question_id, embedding) tuples
        """
        if main_embedding is not None:
            self.main_index.add(chunk_id, main_embedding)
            logger.debug(f"Added main embedding for chunk {chunk_id}")

        if summary_embedding is not None:
            # Use chunk_id with suffix for summary
            summary_id = f"{chunk_id}_summary"
            self.summary_index.add(summary_id, summary_embedding)
            logger.debug(f"Added summary embedding for chunk {chunk_id}")

        if question_embeddings:
            for question_id, embedding in question_embeddings:
                self.question_index.add(question_id, embedding)
                self._question_to_chunk[question_id] = chunk_id
            logger.debug(f"Added {len(question_embeddings)} question embeddings for chunk {chunk_id}")

    def add_batch(
        self,
        main_data: list[tuple[str, np.ndarray]] | None = None,
        summary_data: list[tuple[str, np.ndarray]] | None = None,
        question_data: list[tuple[str, str, np.ndarray]] | None = None,
    ) -> None:
        """
        Add batch embeddings to indices.

        Args:
            main_data: List of (chunk_id, embedding) tuples for main index
            summary_data: List of (chunk_id, embedding) tuples for summary index
            question_data: List of (question_id, chunk_id, embedding) tuples for question index
        """
        if main_data:
            chunk_ids = [d[0] for d in main_data]
            embeddings = np.array([d[1] for d in main_data])
            self.main_index.add_batch(chunk_ids, embeddings)
            logger.info(f"Added {len(main_data)} main embeddings")

        if summary_data:
            summary_ids = [f"{d[0]}_summary" for d in summary_data]
            embeddings = np.array([d[1] for d in summary_data])
            self.summary_index.add_batch(summary_ids, embeddings)
            logger.info(f"Added {len(summary_data)} summary embeddings")

        if question_data:
            question_ids = [d[0] for d in question_data]
            embeddings = np.array([d[2] for d in question_data])
            self.question_index.add_batch(question_ids, embeddings)

            # Update question to chunk mapping
            for question_id, chunk_id, _ in question_data:
                self._question_to_chunk[question_id] = chunk_id

            logger.info(f"Added {len(question_data)} question embeddings")

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        vector_types: list[VectorType] | None = None,
        filter_ids: list[str] | None = None,
    ) -> dict[VectorType, list[tuple[str, float]]]:
        """
        Search across specified indices.

        Args:
            query_embedding: Query embedding
            k: Number of results per index
            vector_types: Which indices to search (default: all)
            filter_ids: Optional chunk IDs to filter results

        Returns:
            Dict mapping vector type to list of (chunk_id, score) tuples
        """
        vector_types = vector_types or ["main", "summary", "question"]
        results: dict[VectorType, list[tuple[str, float]]] = {}

        if "main" in vector_types:
            main_results = self.main_index.search(query_embedding, k, filter_ids)
            results["main"] = main_results

        if "summary" in vector_types:
            # For summary, filter by chunk ID (without _summary suffix)
            summary_filter = None
            if filter_ids:
                summary_filter = [f"{cid}_summary" for cid in filter_ids]

            summary_results_raw = self.summary_index.search(query_embedding, k, summary_filter)

            # Convert summary IDs back to chunk IDs
            summary_results = []
            for summary_id, score in summary_results_raw:
                chunk_id = summary_id.replace("_summary", "")
                summary_results.append((chunk_id, score))

            results["summary"] = summary_results

        if "question" in vector_types:
            # Search question index and map back to chunks
            question_results_raw = self.question_index.search(query_embedding, k * 2)

            # Map question IDs to chunk IDs and deduplicate
            seen_chunks: set[str] = set()
            question_results = []

            for question_id, score in question_results_raw:
                chunk_id = self._question_to_chunk.get(question_id)
                if chunk_id and chunk_id not in seen_chunks:
                    if filter_ids is None or chunk_id in filter_ids:
                        question_results.append((chunk_id, score))
                        seen_chunks.add(chunk_id)

                        if len(question_results) >= k:
                            break

            results["question"] = question_results

        return results

    def search_all(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        filter_ids: list[str] | None = None,
    ) -> dict[VectorType, list[tuple[str, float]]]:
        """
        Search all indices and return results.

        Args:
            query_embedding: Query embedding
            k: Number of results per index
            filter_ids: Optional chunk IDs to filter results

        Returns:
            Dict with results from all indices
        """
        return self.search(
            query_embedding,
            k=k,
            vector_types=["main", "summary", "question"],
            filter_ids=filter_ids,
        )

    def remove_chunk(self, chunk_id: str) -> None:
        """
        Remove all embeddings for a chunk from all indices.

        Args:
            chunk_id: The chunk ID to remove
        """
        # Remove from main index
        self.main_index.remove([chunk_id])

        # Remove from summary index
        self.summary_index.remove([f"{chunk_id}_summary"])

        # Remove from question index
        questions_to_remove = [
            qid for qid, cid in self._question_to_chunk.items()
            if cid == chunk_id
        ]
        if questions_to_remove:
            self.question_index.remove(questions_to_remove)
            for qid in questions_to_remove:
                del self._question_to_chunk[qid]

        logger.debug(f"Removed chunk {chunk_id} from all indices")

    def save(self, base_path: Path | None = None) -> None:
        """
        Save all indices to disk.

        Args:
            base_path: Base path for index files (uses settings default if not provided)
        """
        if base_path:
            main_index_path = base_path / "main_index.faiss"
            main_id_map_path = base_path / "main_id_map.json"
            summary_index_path = base_path / "summary_index.faiss"
            summary_id_map_path = base_path / "summary_id_map.json"
            question_index_path = base_path / "question_index.faiss"
            question_id_map_path = base_path / "question_id_map.json"
        else:
            main_index_path = settings.main_vector_index_path
            main_id_map_path = settings.main_vector_id_map_path
            summary_index_path = settings.summary_vector_index_path
            summary_id_map_path = settings.summary_vector_id_map_path
            question_index_path = settings.question_vector_index_path
            question_id_map_path = settings.question_vector_id_map_path

        # Save main index
        self.main_index.save(main_index_path, main_id_map_path)

        # Save summary index
        self.summary_index.save(summary_index_path, summary_id_map_path)

        # Save question index
        self.question_index.save(question_index_path, question_id_map_path)

        # Save question-to-chunk mapping
        import json
        mapping_path = (base_path or settings.data_folder / "faiss") / "question_chunk_map.json"
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        with open(mapping_path, "w") as f:
            json.dump(self._question_to_chunk, f)

        logger.info("Saved all multi-vector indices")

    def load(self, base_path: Path | None = None) -> bool:
        """
        Load all indices from disk.

        Args:
            base_path: Base path for index files (uses settings default if not provided)

        Returns:
            True if all indices loaded successfully
        """
        import json

        if base_path:
            main_index_path = base_path / "main_index.faiss"
            main_id_map_path = base_path / "main_id_map.json"
            summary_index_path = base_path / "summary_index.faiss"
            summary_id_map_path = base_path / "summary_id_map.json"
            question_index_path = base_path / "question_index.faiss"
            question_id_map_path = base_path / "question_id_map.json"
            mapping_path = base_path / "question_chunk_map.json"
        else:
            main_index_path = settings.main_vector_index_path
            main_id_map_path = settings.main_vector_id_map_path
            summary_index_path = settings.summary_vector_index_path
            summary_id_map_path = settings.summary_vector_id_map_path
            question_index_path = settings.question_vector_index_path
            question_id_map_path = settings.question_vector_id_map_path
            mapping_path = settings.data_folder / "faiss" / "question_chunk_map.json"

        # Load main index
        main_loaded = self.main_index.load(main_index_path, main_id_map_path)

        # Load summary index
        summary_loaded = self.summary_index.load(summary_index_path, summary_id_map_path)

        # Load question index
        question_loaded = self.question_index.load(question_index_path, question_id_map_path)

        # Load question-to-chunk mapping
        if mapping_path.exists():
            try:
                with open(mapping_path, "r") as f:
                    self._question_to_chunk = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load question-chunk mapping: {e}")
                self._question_to_chunk = {}

        success = main_loaded or summary_loaded or question_loaded
        if success:
            logger.info(
                f"Loaded multi-vector indices: "
                f"main={self.main_index.size}, "
                f"summary={self.summary_index.size}, "
                f"question={self.question_index.size}"
            )

        return success

    def clear(self) -> None:
        """Clear all indices."""
        self.main_index.clear()
        self.summary_index.clear()
        self.question_index.clear()
        self._question_to_chunk = {}
        logger.info("Cleared all multi-vector indices")

    @property
    def stats(self) -> dict:
        """Get statistics for all indices."""
        return {
            "main_vectors": self.main_index.size,
            "main_chunks": self.main_index.num_chunks,
            "summary_vectors": self.summary_index.size,
            "summary_chunks": self.summary_index.num_chunks,
            "question_vectors": self.question_index.size,
            "question_chunks": len(set(self._question_to_chunk.values())),
        }


# Global instance
multi_vector_index = MultiVectorIndex()
