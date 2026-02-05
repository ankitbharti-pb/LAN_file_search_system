"""Structure-aware text chunking with context prepending."""

import hashlib
import logging
from typing import Any

import pandas as pd

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
        """Split text into chunks with overlap, respecting sentence boundaries."""
        chunks = []
        current_chunk = ""
        overlap_text = ""  # Text to prepend from previous chunk

        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If starting a new chunk, prepend overlap from previous chunk
            if not current_chunk and overlap_text and self.chunk_overlap > 0:
                current_chunk = overlap_text + "\n\n"

            if len(current_chunk) + len(para) <= self.chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Extract overlap for next chunk
                    overlap_text = self._extract_overlap(current_chunk.strip())

                if len(para) > self.chunk_size:
                    # Split long paragraphs by sentences
                    long_para_chunks = self._split_long_paragraph(para)
                    for i, lpc in enumerate(long_para_chunks):
                        if i == 0 and overlap_text and self.chunk_overlap > 0:
                            # Prepend overlap to first chunk of split paragraph
                            chunks.append((overlap_text + "\n\n" + lpc).strip())
                        else:
                            chunks.append(lpc)
                        # Update overlap for next chunk
                        overlap_text = self._extract_overlap(lpc)
                    current_chunk = ""
                else:
                    # Start new chunk with overlap + current paragraph
                    if overlap_text and self.chunk_overlap > 0:
                        current_chunk = overlap_text + "\n\n" + para + "\n\n"
                    else:
                        current_chunk = para + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _extract_overlap(self, text: str) -> str:
        """Extract overlap text from end of chunk, respecting sentence boundaries.

        Args:
            text: The chunk text to extract overlap from

        Returns:
            Overlap text (up to chunk_overlap chars, at sentence boundary)
        """
        if not text or self.chunk_overlap <= 0:
            return ""

        if len(text) <= self.chunk_overlap:
            return text

        # Get last N characters
        overlap_region = text[-self.chunk_overlap:]

        # Try to find a sentence boundary (. ! ? followed by space)
        for i, char in enumerate(overlap_region):
            if char in '.!?' and i < len(overlap_region) - 1:
                if i + 1 < len(overlap_region) and overlap_region[i + 1] in ' \n':
                    # Start from after this sentence boundary
                    return overlap_region[i + 2:].strip()

        # Fallback: find word boundary (first space)
        space_idx = overlap_region.find(' ')
        if space_idx > 0 and space_idx < len(overlap_region) - 10:
            return overlap_region[space_idx + 1:].strip()

        # Last resort: return the whole overlap region
        return overlap_region.strip()

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
        prev_summary: str | None = None,
        next_summary: str | None = None,
    ) -> str:
        """Build context prefix for a chunk including cross-chunk context.

        Args:
            file_name: Name of the document file
            doc_type: Detected document type
            heading_path: Section hierarchy path
            entities: Document-level entities
            prev_summary: Summary of previous chunk for context
            next_summary: Summary of next chunk for context

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

        return "\n".join(lines)

    def _establish_chunk_links(self, chunks: list[Chunk]) -> None:
        """Establish cross-chunk links and context summaries.

        Args:
            chunks: List of chunks to link together
        """
        if not settings.enable_chunk_links or len(chunks) < 2:
            return

        for i, chunk in enumerate(chunks):
            # Set previous chunk reference
            if i > 0:
                chunk.prev_chunk_id = chunks[i - 1].id
                # Extract first ~100 chars as summary
                prev_text = chunks[i - 1].text
                chunk.prev_chunk_summary = prev_text[:100] + "..." if len(prev_text) > 100 else prev_text

            # Set next chunk reference
            if i < len(chunks) - 1:
                chunk.next_chunk_id = chunks[i + 1].id
                # Extract first ~100 chars as summary
                next_text = chunks[i + 1].text
                chunk.next_chunk_summary = next_text[:100] + "..." if len(next_text) > 100 else next_text

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
