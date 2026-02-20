"""Structure-aware text chunking with context prepending."""

import logging
from typing import Any

import pandas as pd

from models.chunk import Chunk, ChunkMetadata
from parsers.base import ParseResult, HeadingInfo
from models.enrichment import EnrichmentResult
from config.settings import settings
from indexing.chunk_utils import (
    build_chunk_context,
    generate_chunk_id,
    establish_chunk_links,
    split_text,
)

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

        # Establish cross-chunk links
        self._establish_chunk_links(chunks)

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

        # Row-batch chunks for full CSV/Excel data
        if parse_result.dataframe is not None:
            row_batch_chunks = self._create_row_batch_chunks(
                df=parse_result.dataframe,
                column_headers=parse_result.column_headers or [],
                document_id=document_id,
                file_name=file_name,
                enrichment=enrichment,
                start_chunk_index=chunk_index,
            )
            chunks.extend(row_batch_chunks)
            chunk_index += len(row_batch_chunks)

        # Establish cross-chunk links
        self._establish_chunk_links(chunks)

        return chunks

    def _create_row_batch_chunks(
        self,
        df: pd.DataFrame,
        column_headers: list[str],
        document_id: str,
        file_name: str,
        enrichment: EnrichmentResult,
        start_chunk_index: int,
    ) -> list[Chunk]:
        """Create row-batch chunks from a DataFrame.

        Groups rows into batches of csv_rows_per_chunk, each self-contained
        with column headers for searchability.
        """
        rows_per_chunk = settings.csv_rows_per_chunk
        max_rows = settings.csv_max_rows_to_index
        total_rows = len(df)

        if max_rows > 0 and total_rows > max_rows:
            logger.warning(
                f"CSV has {total_rows} rows, capping at {max_rows} "
                f"(csv_max_rows_to_index={max_rows})"
            )
            df = df.head(max_rows)
            total_rows = max_rows

        header_line = f"Columns: {', '.join(column_headers)}"
        chunks = []
        chunk_index = start_chunk_index

        for batch_start in range(0, total_rows, rows_per_chunk):
            batch_end = min(batch_start + rows_per_chunk, total_rows)
            batch_df = df.iloc[batch_start:batch_end]

            # Format each row as "Row N: col1=val1, col2=val2, ..."
            row_lines = []
            for i, (_, row) in enumerate(batch_df.iterrows()):
                row_num = batch_start + i + 1  # 1-based
                parts = []
                for col in column_headers:
                    val = row.get(col, "")
                    if pd.notna(val):
                        parts.append(f"{col}={val}")
                row_lines.append(f"Row {row_num}: {', '.join(parts)}")

            batch_text = f"{header_line}\n" + "\n".join(row_lines)

            # If batch is too large, split on row boundaries
            if len(batch_text) > self.chunk_size * 2:
                sub_texts = self._split_row_batch_text(
                    header_line, row_lines
                )
            else:
                sub_texts = [batch_text]

            for text in sub_texts:
                context = self._build_context(
                    file_name=file_name,
                    doc_type=enrichment.document_type,
                    heading_path="Row Data",
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
                        content_type="row_batch",
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

        logger.info(
            f"Created {len(chunks)} row batch chunks from {total_rows} rows "
            f"for {file_name}"
        )
        return chunks

    def _split_row_batch_text(
        self, header_line: str, row_lines: list[str]
    ) -> list[str]:
        """Split an oversized row batch into smaller texts on row boundaries."""
        texts = []
        current_lines = [header_line]
        current_len = len(header_line)

        for line in row_lines:
            line_len = len(line) + 1  # +1 for newline
            if current_len + line_len > self.chunk_size * 2 and len(current_lines) > 1:
                texts.append("\n".join(current_lines))
                current_lines = [header_line]
                current_len = len(header_line)
            current_lines.append(line)
            current_len += line_len

        if len(current_lines) > 1:  # More than just the header
            texts.append("\n".join(current_lines))

        return texts

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks, respecting paragraph and sentence boundaries."""
        return split_text(text, self.chunk_size)

    def _build_context(self, **kwargs) -> str:
        """Build context prefix for a chunk (delegates to chunk_utils)."""
        return build_chunk_context(**kwargs)

    def _establish_chunk_links(self, chunks: list[Chunk]) -> None:
        """Establish cross-chunk navigation links (delegates to chunk_utils)."""
        establish_chunk_links(chunks)

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
        """Generate a unique chunk ID (delegates to chunk_utils)."""
        return generate_chunk_id(document_id, chunk_index)


def rebuild_contextualized_text(
    chunks: list[Chunk],
    enrichment_results: list[tuple[ChunkMetadata | None, list]],
    file_name: str,
    doc_type: str,
    entities: dict,
) -> list[Chunk]:
    """Rebuild each chunk's contextualized_text using LLM enrichment results.

    Replaces raw text overlap with enrichment-derived context:
    - Previous chunk's LLM-generated summary
    - Next chunk's LLM-generated summary
    - This chunk's contextual_description from enrichment

    Args:
        chunks: List of chunks to update
        enrichment_results: Parallel list of (ChunkMetadata | None, questions) tuples
        file_name: Document file name
        doc_type: Detected document type
        entities: Document-level entities dict

    Returns:
        The same chunks list, mutated with rebuilt contextualized_text
    """
    for i, chunk in enumerate(chunks):
        # Get enrichment data for prev/next/self
        prev_summary = None
        next_summary = None
        contextual_desc = None

        if i > 0 and i - 1 < len(enrichment_results):
            prev_meta = enrichment_results[i - 1][0]
            if prev_meta and prev_meta.summary:
                prev_summary = prev_meta.summary

        if i + 1 < len(enrichment_results):
            next_meta = enrichment_results[i + 1][0]
            if next_meta and next_meta.summary:
                next_summary = next_meta.summary

        if i < len(enrichment_results):
            self_meta = enrichment_results[i][0]
            if self_meta and self_meta.contextual_description:
                contextual_desc = self_meta.contextual_description

        # Rebuild context using shared utility
        context = build_chunk_context(
            file_name=file_name,
            doc_type=doc_type,
            heading_path=chunk.heading_path or "",
            entities=entities,
            prev_summary=prev_summary,
            next_summary=next_summary,
            contextual_description=contextual_desc,
        )

        chunk.contextualized_text = f"{context}\n\n{chunk.text}"

        # Update chunk summary fields with LLM-generated summaries
        chunk.prev_chunk_summary = prev_summary
        chunk.next_chunk_summary = next_summary

    return chunks


# Global instance
chunker = Chunker()
