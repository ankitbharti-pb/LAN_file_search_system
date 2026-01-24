"""Structure-aware text chunking with context prepending."""

import hashlib
import logging
from typing import Any

from models.chunk import Chunk
from parsers.base import ParseResult, HeadingInfo
from enrichment.entity_extractor import EnrichmentResult
from config.settings import settings

logger = logging.getLogger(__name__)


class Chunker:
    """Creates contextual chunks from parsed documents."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_document(
        self,
        parse_result: ParseResult,
        enrichment: EnrichmentResult,
        document_id: str,
        file_name: str,
    ) -> list[Chunk]:
        """Create chunks from a document (PDF, Word, PowerPoint)."""
        chunks = []
        chunk_index = 0

        # Track current heading path
        current_heading_path = ""
        heading_stack: list[tuple[int, str]] = []

        # Process paragraphs with heading context
        text_chunks = self._split_text(parse_result.text)

        for text in text_chunks:
            if not text.strip():
                continue

            # Update heading path if this looks like a heading
            heading_match = self._detect_heading(text, parse_result.headings)
            if heading_match:
                self._update_heading_stack(heading_stack, heading_match)
                current_heading_path = self._build_heading_path(heading_stack)

            # Create contextualized text
            context = self._build_context(
                file_name=file_name,
                doc_type=enrichment.document_type,
                heading_path=current_heading_path,
                entities=enrichment.entities,
            )
            contextualized = f"{context}\n\n{text}"

            # Create chunk
            chunk_id = self._generate_chunk_id(document_id, chunk_index)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    text=text,
                    contextualized_text=contextualized,
                    content_type="paragraph",
                    heading_path=current_heading_path if current_heading_path else None,
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        # Add table chunks
        for i, table in enumerate(parse_result.tables):
            table_text = self._table_to_text(table)
            table_desc = (
                enrichment.table_descriptions[i]
                if i < len(enrichment.table_descriptions)
                else f"Table: {table.title or 'Data Table'}"
            )

            context = self._build_context(
                file_name=file_name,
                doc_type=enrichment.document_type,
                heading_path=current_heading_path,
                entities=enrichment.entities,
            )
            contextualized = f"{context}\n\nTable Description: {table_desc}\n\n{table_text}"

            chunk_id = self._generate_chunk_id(document_id, chunk_index)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    text=table_text,
                    contextualized_text=contextualized,
                    content_type="table",
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        # Add summary chunk
        if enrichment.summary:
            context = self._build_context(
                file_name=file_name,
                doc_type=enrichment.document_type,
                heading_path="Document Summary",
                entities=enrichment.entities,
            )
            summary_text = f"Summary: {enrichment.summary}"
            contextualized = f"{context}\n\n{summary_text}"

            chunk_id = self._generate_chunk_id(document_id, chunk_index)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    text=summary_text,
                    contextualized_text=contextualized,
                    content_type="summary",
                    chunk_index=chunk_index,
                )
            )

        return chunks

    def chunk_tabular(
        self,
        parse_result: ParseResult,
        enrichment: EnrichmentResult,
        document_id: str,
        file_name: str,
    ) -> list[Chunk]:
        """Create chunks from tabular data (CSV, Excel)."""
        chunks = []
        chunk_index = 0

        # File-level summary chunk
        summary_text = enrichment.summary or f"Tabular data file: {file_name}"
        context = self._build_context(
            file_name=file_name,
            doc_type=enrichment.document_type,
            heading_path="File Summary",
            entities=enrichment.entities,
        )
        contextualized = f"{context}\n\n{summary_text}"

        chunk_id = self._generate_chunk_id(document_id, chunk_index)
        chunks.append(
            Chunk(
                id=chunk_id,
                document_id=document_id,
                text=summary_text,
                contextualized_text=contextualized,
                content_type="summary",
                chunk_index=chunk_index,
            )
        )
        chunk_index += 1

        # Schema description chunk
        if parse_result.column_headers:
            schema_parts = [f"Columns in {file_name}:"]
            for col in parse_result.column_headers[:30]:
                dtype = (
                    parse_result.column_types.get(col, "text")
                    if parse_result.column_types
                    else "text"
                )
                schema_parts.append(f"  - {col}: {dtype}")

            schema_text = "\n".join(schema_parts)
            context = self._build_context(
                file_name=file_name,
                doc_type=enrichment.document_type,
                heading_path="Data Schema",
                entities=enrichment.entities,
            )
            contextualized = f"{context}\n\n{schema_text}"

            chunk_id = self._generate_chunk_id(document_id, chunk_index)
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    text=schema_text,
                    contextualized_text=contextualized,
                    content_type="schema",
                    chunk_index=chunk_index,
                )
            )
            chunk_index += 1

        # Per-sheet chunks for Excel
        for table in parse_result.tables:
            if table.sheet_name:
                sheet_text = f"Sheet: {table.sheet_name}\n"
                sheet_text += f"Columns: {', '.join(table.headers)}\n"
                if table.rows:
                    sheet_text += f"Sample data: {len(table.rows)} rows shown"

                context = self._build_context(
                    file_name=file_name,
                    doc_type=enrichment.document_type,
                    heading_path=f"Sheet: {table.sheet_name}",
                    entities=enrichment.entities,
                )
                contextualized = f"{context}\n\n{sheet_text}"

                chunk_id = self._generate_chunk_id(document_id, chunk_index)
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        text=sheet_text,
                        contextualized_text=contextualized,
                        content_type="table",
                        sheet_name=table.sheet_name,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

        # Add full text representation as chunks
        if parse_result.text:
            text_chunks = self._split_text(parse_result.text)
            for text in text_chunks:
                if not text.strip():
                    continue

                context = self._build_context(
                    file_name=file_name,
                    doc_type=enrichment.document_type,
                    heading_path="Data Content",
                    entities=enrichment.entities,
                )
                contextualized = f"{context}\n\n{text}"

                chunk_id = self._generate_chunk_id(document_id, chunk_index)
                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document_id,
                        text=text,
                        contextualized_text=contextualized,
                        content_type="paragraph",
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

        return chunks

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks respecting sentence boundaries."""
        chunks = []
        current_chunk = ""

        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                if len(para) > self.chunk_size:
                    # Split long paragraphs by sentences
                    chunks.extend(self._split_long_paragraph(para))
                    current_chunk = ""
                else:
                    current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_long_paragraph(self, text: str) -> list[str]:
        """Split a long paragraph by sentences."""
        chunks = []
        current_chunk = ""

        # Simple sentence splitting
        sentences = text.replace(". ", ".|").replace("? ", "?|").replace("! ", "!|").split("|")

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _build_context(
        self,
        file_name: str,
        doc_type: str,
        heading_path: str,
        entities: dict[str, Any],
    ) -> str:
        """Build context prefix for a chunk."""
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

        return "\n".join(lines)

    def _detect_heading(
        self, text: str, headings: list[HeadingInfo]
    ) -> HeadingInfo | None:
        """Check if text matches a known heading."""
        text_clean = text.strip().lower()[:100]
        for heading in headings:
            if heading.text.strip().lower() in text_clean:
                return heading
        return None

    def _update_heading_stack(
        self, stack: list[tuple[int, str]], heading: HeadingInfo
    ) -> None:
        """Update the heading stack with a new heading."""
        # Remove headings at same or lower level
        while stack and stack[-1][0] >= heading.level:
            stack.pop()
        stack.append((heading.level, heading.text))

    def _build_heading_path(self, stack: list[tuple[int, str]]) -> str:
        """Build heading path from stack."""
        return " > ".join(text for _, text in stack)

    def _table_to_text(self, table) -> str:
        """Convert a table to text representation."""
        lines = []
        if table.title:
            lines.append(f"Table: {table.title}")
        lines.append(f"Headers: {', '.join(table.headers)}")
        for i, row in enumerate(table.rows[:5], 1):
            row_str = ", ".join(str(v)[:50] for v in row)
            lines.append(f"Row {i}: {row_str}")
        if len(table.rows) > 5:
            lines.append(f"... and {len(table.rows) - 5} more rows")
        return "\n".join(lines)

    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        content = f"{document_id}:{chunk_index}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# Global instance
chunker = Chunker()
