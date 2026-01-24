"""Dynamic entity extraction using LLM."""

import logging
from dataclasses import dataclass, field
from typing import Any

from enrichment.llm_client import LLMClient, get_llm_client
from enrichment.prompts import (
    DOCUMENT_ENRICHMENT_SYSTEM_PROMPT,
    DOCUMENT_ENRICHMENT_PROMPT,
    TABULAR_ENRICHMENT_PROMPT,
)
from parsers.base import ParseResult

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of LLM enrichment."""

    document_type: str = "unknown"
    summary: str = ""
    entities: dict[str, Any] = field(default_factory=dict)
    key_topics: list[str] = field(default_factory=list)
    table_descriptions: list[str] = field(default_factory=list)
    success: bool = True
    error: str | None = None


class EntityExtractor:
    """Extracts entities and metadata from documents using LLM."""

    MAX_CONTENT_LENGTH = 6000  # Chars to send to LLM

    def __init__(self, llm_client: LLMClient | None = None):
        self._llm_client = llm_client

    @property
    def llm_client(self) -> LLMClient:
        """Lazy load the LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    async def enrich(
        self,
        parse_result: ParseResult,
        file_name: str,
        file_type: str,
    ) -> EnrichmentResult:
        """Enrich a parsed document with LLM-extracted metadata."""
        # Determine if tabular or document
        is_tabular = file_type in ["csv", "xlsx", "xls"]

        try:
            if is_tabular:
                return await self._enrich_tabular(parse_result, file_name, file_type)
            else:
                return await self._enrich_document(parse_result, file_name, file_type)
        except Exception as e:
            logger.error(f"Enrichment failed for {file_name}: {e}")
            return EnrichmentResult(
                document_type="unknown",
                summary=f"Document: {file_name}",
                success=False,
                error=str(e),
            )

    async def _enrich_document(
        self,
        parse_result: ParseResult,
        file_name: str,
        file_type: str,
    ) -> EnrichmentResult:
        """Enrich a document (PDF, Word, PowerPoint)."""
        # Prepare content (truncate if needed)
        content = parse_result.text[:self.MAX_CONTENT_LENGTH]
        if len(parse_result.text) > self.MAX_CONTENT_LENGTH:
            content += "\n[... content truncated ...]"

        # Add table descriptions if present
        if parse_result.tables:
            content += "\n\nTABLES IN DOCUMENT:"
            for i, table in enumerate(parse_result.tables[:3], 1):
                content += f"\nTable {i}: {table.title or 'Untitled'}"
                content += f"\nHeaders: {', '.join(table.headers)}"
                if table.rows:
                    content += f"\nSample row: {table.rows[0]}"

        # Create prompt
        prompt = DOCUMENT_ENRICHMENT_PROMPT.format(
            file_name=file_name,
            file_type=file_type,
            content=content,
        )

        # Call LLM
        result = await self.llm_client.complete_json(
            prompt=prompt,
            system_prompt=DOCUMENT_ENRICHMENT_SYSTEM_PROMPT,
        )

        return self._parse_enrichment_result(result)

    async def _enrich_tabular(
        self,
        parse_result: ParseResult,
        file_name: str,
        file_type: str,
    ) -> EnrichmentResult:
        """Enrich a tabular file (CSV, Excel)."""
        # Format column types
        column_types_str = ""
        if parse_result.column_types:
            for col, dtype in list(parse_result.column_types.items())[:20]:
                column_types_str += f"  - {col}: {dtype}\n"

        # Format sample data
        sample_data_str = ""
        if parse_result.sample_rows and parse_result.column_headers:
            headers = parse_result.column_headers[:10]
            sample_data_str += f"Headers: {', '.join(headers)}\n"
            for i, row in enumerate(parse_result.sample_rows[:5], 1):
                row_str = ", ".join(str(v)[:50] for v in row[:10])
                sample_data_str += f"Row {i}: {row_str}\n"

        # Format numeric stats
        numeric_stats_str = ""
        if parse_result.numeric_stats:
            for col, stats in list(parse_result.numeric_stats.items())[:10]:
                numeric_stats_str += (
                    f"  - {col}: sum={stats.get('sum', 0):,.2f}, "
                    f"mean={stats.get('mean', 0):,.2f}, "
                    f"range=[{stats.get('min', 0):,.2f} to {stats.get('max', 0):,.2f}]\n"
                )

        # Create prompt
        prompt = TABULAR_ENRICHMENT_PROMPT.format(
            file_name=file_name,
            file_type=file_type,
            row_count=parse_result.row_count or "Unknown",
            columns=", ".join(parse_result.column_headers or [])[:500],
            column_types=column_types_str or "Not available",
            sample_data=sample_data_str or "Not available",
            numeric_stats=numeric_stats_str or "Not available",
        )

        # Call LLM
        result = await self.llm_client.complete_json(
            prompt=prompt,
            system_prompt=DOCUMENT_ENRICHMENT_SYSTEM_PROMPT,
        )

        return self._parse_enrichment_result(result)

    def _parse_enrichment_result(self, result: dict[str, Any]) -> EnrichmentResult:
        """Parse LLM response into EnrichmentResult."""
        if not result:
            return EnrichmentResult(
                success=False,
                error="Empty response from LLM",
            )

        return EnrichmentResult(
            document_type=result.get("document_type", "unknown"),
            summary=result.get("summary", ""),
            entities=result.get("entities", {}),
            key_topics=result.get("key_topics", []),
            table_descriptions=result.get("table_descriptions", []),
            success=True,
        )


# Global instance
entity_extractor = EntityExtractor()
