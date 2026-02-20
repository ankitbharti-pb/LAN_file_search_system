"""Semantic chunker that detects topic changes using embedding similarity."""

import re
from typing import TYPE_CHECKING

from models.chunk import Chunk
from config.settings import settings

if TYPE_CHECKING:
    from indexing.embedder import Embedder


class SemanticChunker:
    """Detects semantic boundaries and refines chunks based on topic similarity."""

    def __init__(
        self,
        embedder: "Embedder",
        similarity_threshold: float | None = None,
    ):
        """
        Initialize the semantic chunker.

        Args:
            embedder: Embedder instance for generating sentence embeddings
            similarity_threshold: Threshold below which we detect a topic shift
        """
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold or settings.semantic_similarity_threshold

    def detect_breakpoints(self, text: str) -> list[int]:
        """
        Detect semantic breakpoints in text using embedding similarity.

        Args:
            text: Text to analyze

        Returns:
            List of character positions where topic shifts occur
        """
        # Split into sentences
        sentences = self._split_sentences(text)
        if len(sentences) < 3:
            return []

        # Embed sentences
        sentence_texts = [s["text"] for s in sentences]
        embeddings = self.embedder.embed_batch(sentence_texts)

        # Calculate similarities between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self.embedder.similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        # Find breakpoints where similarity drops below threshold
        breakpoints = []
        for i, sim in enumerate(similarities):
            if sim < self.similarity_threshold:
                # Breakpoint is at the start of the next sentence
                breakpoints.append(sentences[i + 1]["start"])

        return breakpoints

    def refine_chunks(
        self,
        hierarchical_chunks: list[Chunk],
        max_chunk_size: int | None = None,
    ) -> list[Chunk]:
        """
        Refine chunks by splitting large ones at semantic boundaries.

        Args:
            hierarchical_chunks: Chunks from hierarchical chunker
            max_chunk_size: Maximum chunk size (uses settings default if not provided)

        Returns:
            Refined list of chunks with semantic boundary information
        """
        max_size = max_chunk_size or settings.max_chunk_size
        refined_chunks = []

        for chunk in hierarchical_chunks:
            if len(chunk.text) <= max_size:
                # Chunk is already small enough
                refined_chunks.append(chunk)
                continue

            # Try to split at semantic boundaries
            breakpoints = self.detect_breakpoints(chunk.text)

            if not breakpoints:
                # No semantic breakpoints found, use hierarchical chunk as-is
                refined_chunks.append(chunk)
                continue

            # Split chunk at breakpoints
            splits = self._split_at_breakpoints(chunk, breakpoints, max_size)
            refined_chunks.extend(splits)

        # Add semantic similarity info to chunks
        self._add_semantic_similarity(refined_chunks)

        return refined_chunks

    def _split_sentences(self, text: str) -> list[dict]:
        """Split text into sentences with position tracking."""
        # Simple sentence splitting - handles common cases
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\s*\n+'

        sentences = []
        last_end = 0

        for match in re.finditer(sentence_pattern, text):
            sentence_text = text[last_end:match.start() + 1].strip()
            if sentence_text and len(sentence_text) > 10:  # Filter very short sentences
                sentences.append({
                    "text": sentence_text,
                    "start": last_end,
                    "end": match.start() + 1,
                })
            last_end = match.end()

        # Add final sentence
        if last_end < len(text):
            final = text[last_end:].strip()
            if final and len(final) > 10:
                sentences.append({
                    "text": final,
                    "start": last_end,
                    "end": len(text),
                })

        return sentences

    def _split_at_breakpoints(
        self,
        chunk: Chunk,
        breakpoints: list[int],
        max_size: int,
    ) -> list[Chunk]:
        """Split a chunk at the given breakpoints."""
        splits = []
        text = chunk.text
        last_pos = 0
        chunk_index = chunk.chunk_index

        for bp in breakpoints:
            segment = text[last_pos:bp].strip()
            if segment:
                # Only create a split if it's meaningful
                if len(segment) >= 50:  # Minimum meaningful size
                    new_chunk = Chunk(
                        id=f"{chunk.id}_{len(splits)}",
                        document_id=chunk.document_id,
                        text=segment,
                        contextualized_text=self._rebuild_context(chunk, segment),
                        content_type=chunk.content_type,
                        page=chunk.page,
                        sheet_name=chunk.sheet_name,
                        heading_path=chunk.heading_path,
                        entities=chunk.entities,
                        chunk_index=chunk_index,
                        parent_chunk_id=chunk.parent_chunk_id,
                        hierarchy_level=chunk.hierarchy_level,
                        bbox=chunk.bbox,
                        layout_label=chunk.layout_label,
                        is_semantic_boundary=len(splits) > 0,  # First split is not a boundary
                    )
                    splits.append(new_chunk)
                    chunk_index += 1

            last_pos = bp

        # Add remaining text
        remaining = text[last_pos:].strip()
        if remaining and len(remaining) >= 50:
            new_chunk = Chunk(
                id=f"{chunk.id}_{len(splits)}",
                document_id=chunk.document_id,
                text=remaining,
                contextualized_text=self._rebuild_context(chunk, remaining),
                content_type=chunk.content_type,
                page=chunk.page,
                sheet_name=chunk.sheet_name,
                heading_path=chunk.heading_path,
                entities=chunk.entities,
                chunk_index=chunk_index,
                parent_chunk_id=chunk.parent_chunk_id,
                hierarchy_level=chunk.hierarchy_level,
                bbox=chunk.bbox,
                layout_label=chunk.layout_label,
                is_semantic_boundary=len(splits) > 0,
            )
            splits.append(new_chunk)

        # If no valid splits were made, return original chunk
        if not splits:
            return [chunk]

        return splits

    def _rebuild_context(self, original_chunk: Chunk, new_text: str) -> str:
        """Rebuild contextualized text for a split chunk."""
        # Extract context prefix from original
        original_ctx = original_chunk.contextualized_text
        original_text = original_chunk.text

        if original_text in original_ctx:
            # Find where the original text starts
            text_start = original_ctx.find(original_text)
            context_prefix = original_ctx[:text_start] if text_start > 0 else ""
            return f"{context_prefix}{new_text}" if context_prefix else new_text

        return new_text

    def _add_semantic_similarity(self, chunks: list[Chunk]) -> None:
        """Add semantic similarity scores between consecutive chunks."""
        if len(chunks) < 2:
            return

        # Group chunks by document
        doc_chunks: dict[str, list[Chunk]] = {}
        for chunk in chunks:
            if chunk.document_id not in doc_chunks:
                doc_chunks[chunk.document_id] = []
            doc_chunks[chunk.document_id].append(chunk)

        # Calculate similarities within each document
        for doc_id, doc_chunk_list in doc_chunks.items():
            if len(doc_chunk_list) < 2:
                continue

            # Sort by chunk index
            sorted_chunks = sorted(doc_chunk_list, key=lambda c: c.chunk_index)

            # Embed all chunks
            texts = [c.text for c in sorted_chunks]
            embeddings = self.embedder.embed_batch(texts)

            # Calculate similarities
            for i in range(1, len(sorted_chunks)):
                sim = self.embedder.similarity(embeddings[i - 1], embeddings[i])
                sorted_chunks[i].semantic_similarity_prev = sim

                # Mark as semantic boundary if similarity is low
                if sim < self.similarity_threshold:
                    sorted_chunks[i].is_semantic_boundary = True


def create_semantic_chunker(embedder: "Embedder") -> SemanticChunker:
    """Factory function to create a semantic chunker."""
    return SemanticChunker(embedder)
