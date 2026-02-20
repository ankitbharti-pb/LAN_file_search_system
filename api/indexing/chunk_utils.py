"""Shared utilities for chunk creation, linking, and text splitting.

Extracted from ``Chunker`` and ``HierarchicalChunker`` to eliminate
duplication of context building, chunk ID generation, cross-chunk
linking, and paragraph/sentence splitting.
"""

import hashlib
from typing import Any

from models.chunk import Chunk
from config.settings import settings


# ------------------------------------------------------------------ #
#  Context building                                                    #
# ------------------------------------------------------------------ #

def build_chunk_context(
    file_name: str,
    doc_type: str,
    heading_path: str,
    entities: dict[str, Any],
    prev_summary: str | None = None,
    next_summary: str | None = None,
    contextual_description: str | None = None,
) -> str:
    """Build a context prefix for a chunk including cross-chunk context.

    Args:
        file_name: Name of the document file
        doc_type: Detected document type
        heading_path: Section hierarchy path
        entities: Document-level entities
        prev_summary: Summary of the previous chunk for context
        next_summary: Summary of the next chunk for context
        contextual_description: LLM-generated description of this chunk's role

    Returns:
        Context string to prepend to chunk text
    """
    lines = [
        f"Document: {file_name}",
        f"Type: {doc_type}",
    ]
    if heading_path:
        lines.append(f"Section: {heading_path}")

    # Add key entities (limit to top 5)
    if entities:
        entity_strs = [f"{k}={v}" for k, v in list(entities.items())[:5]]
        if entity_strs:
            lines.append(f"Key info: {', '.join(entity_strs)}")

    # Add cross-chunk context if enabled
    if settings.enable_chunk_links:
        if prev_summary:
            lines.append(f"Previous context: {prev_summary}")
        if next_summary:
            lines.append(f"Following context: {next_summary}")

    # Add LLM-generated contextual description
    if contextual_description:
        lines.append(f"Context: {contextual_description}")

    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Chunk ID generation                                                 #
# ------------------------------------------------------------------ #

def generate_chunk_id(document_id: str, chunk_index: int) -> str:
    """Generate a unique, deterministic chunk ID.

    Args:
        document_id: Parent document identifier
        chunk_index: Zero-based index of the chunk within the document

    Returns:
        16-character hex digest
    """
    content = f"{document_id}:{chunk_index}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ #
#  Cross-chunk linking                                                 #
# ------------------------------------------------------------------ #

def establish_chunk_links(chunks: list[Chunk]) -> None:
    """Establish cross-chunk navigation links.

    Sets ``prev_chunk_id`` / ``next_chunk_id`` for navigation.
    Summaries are populated later by ``rebuild_contextualized_text()``
    using LLM enrichment results.

    Args:
        chunks: List of chunks to link together (mutated in-place)
    """
    if not settings.enable_chunk_links or len(chunks) < 2:
        return

    for i, chunk in enumerate(chunks):
        if i > 0:
            chunk.prev_chunk_id = chunks[i - 1].id
        if i < len(chunks) - 1:
            chunk.next_chunk_id = chunks[i + 1].id


# ------------------------------------------------------------------ #
#  Text splitting                                                      #
# ------------------------------------------------------------------ #

def split_text(text: str, chunk_size: int) -> list[str]:
    """Split text into chunks, respecting paragraph and sentence boundaries.

    Args:
        text: Input text to split
        chunk_size: Maximum chunk size in characters

    Returns:
        List of text chunks
    """
    chunks: list[str] = []
    current_chunk = ""

    # Split by paragraphs first
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) <= chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())

            if len(para) > chunk_size:
                # Split long paragraphs by sentences
                long_para_chunks = _split_long_paragraph(para, chunk_size)
                chunks.extend(long_para_chunks)
                current_chunk = ""
            else:
                current_chunk = para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def _split_long_paragraph(text: str, chunk_size: int) -> list[str]:
    """Split a long paragraph by sentence boundaries.

    Args:
        text: Paragraph text exceeding *chunk_size*
        chunk_size: Maximum chunk size in characters

    Returns:
        List of sub-paragraph text chunks
    """
    chunks: list[str] = []
    current_chunk = ""

    # Simple sentence splitting
    sentences = (
        text.replace(". ", ".|")
        .replace("? ", "?|")
        .replace("! ", "!|")
        .split("|")
    )

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(current_chunk) + len(sentence) <= chunk_size:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

