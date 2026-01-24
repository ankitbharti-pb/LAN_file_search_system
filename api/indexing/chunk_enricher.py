"""LLM-based chunk enrichment for metadata extraction."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable

from models.chunk import Chunk, ChunkMetadata, ChunkQuestion
from enrichment.llm_client import LLMClient, get_llm_client
from config.settings import settings

logger = logging.getLogger(__name__)


ENRICHMENT_SYSTEM_PROMPT = """You are an expert document analyzer. Your task is to analyze text chunks and extract structured metadata to improve search and retrieval.

You must return valid JSON only, no additional text or explanation."""

ENRICHMENT_PROMPT_TEMPLATE = """Analyze the following text chunk from a document and return a JSON object with the following structure:

Document context:
- File: {file_name}
- Type: {doc_type}
- Section: {heading_path}

Text chunk:
\"\"\"
{chunk_text}
\"\"\"

Return a JSON object with these exact fields:
{{
  "title": "Brief 3-8 word title describing this chunk's main topic",
  "summary": "1-2 sentence summary of the key information in this chunk",
  "keywords": ["keyword1", "keyword2", ...],  // 5-10 relevant keywords/phrases
  "entities": {{
    "people": [],        // Names of people mentioned
    "organizations": [], // Company/org names
    "dates": [],         // Dates mentioned
    "amounts": [],       // Monetary amounts or numbers
    "locations": []      // Places mentioned
  }},
  "category": "definition|procedure|data|narrative|example|reference",  // Choose one
  "questions": [         // 3-5 hypothetical questions this chunk answers
    "What is...?",
    "How does...?",
    ...
  ],
  "contextual_description": "2-3 sentences explaining what role this chunk plays in the document and what someone searching for this content might be looking for"
}}

Important:
- Extract only information actually present in the text
- For keywords, include both specific terms and broader concepts
- Questions should be natural queries a user might search for
- Category definitions:
  - definition: Explains concepts, terms, or meanings
  - procedure: Describes steps, processes, or how-to information
  - data: Contains numbers, statistics, tables, or factual data
  - narrative: Tells a story, provides background, or describes events
  - example: Provides examples, case studies, or illustrations
  - reference: Contains citations, links, or references to other sources
"""


class ChunkEnricher:
    """LLM-based metadata extraction for chunks."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        batch_size: int | None = None,
        questions_per_chunk: int | None = None,
    ):
        """
        Initialize the chunk enricher.

        Args:
            llm_client: LLM client instance (uses default if not provided)
            batch_size: Number of chunks to process concurrently
            questions_per_chunk: Number of hypothetical questions to generate
        """
        self._llm_client = llm_client
        self.batch_size = batch_size or settings.enrichment_batch_size
        self.questions_per_chunk = questions_per_chunk or settings.questions_per_chunk

    @property
    def llm_client(self) -> LLMClient:
        """Lazy load the LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    async def enrich_chunk(
        self,
        chunk: Chunk,
        doc_context: dict[str, Any] | None = None,
    ) -> tuple[ChunkMetadata, list[ChunkQuestion]]:
        """
        Enrich a single chunk with LLM-extracted metadata.

        Args:
            chunk: The chunk to enrich
            doc_context: Optional document-level context

        Returns:
            Tuple of (ChunkMetadata, list of ChunkQuestion)
        """
        doc_context = doc_context or {}

        # Build prompt
        prompt = ENRICHMENT_PROMPT_TEMPLATE.format(
            file_name=doc_context.get("file_name", "Unknown"),
            doc_type=doc_context.get("detected_doc_type", "unknown"),
            heading_path=chunk.heading_path or "N/A",
            chunk_text=chunk.text[:3000],  # Limit text length
        )

        try:
            # Call LLM
            result = await self.llm_client.complete_json(
                prompt=prompt,
                system_prompt=ENRICHMENT_SYSTEM_PROMPT,
                max_tokens=1500,
            )

            # Parse response into metadata
            metadata = self._parse_metadata(chunk.id, result)
            questions = self._parse_questions(chunk.id, result)

            return metadata, questions

        except Exception as e:
            logger.error(f"Failed to enrich chunk {chunk.id}: {e}")
            # Return empty metadata on failure
            return self._empty_metadata(chunk.id), []

    async def enrich_batch(
        self,
        chunks: list[Chunk],
        doc_context: dict[str, Any] | None = None,
        progress_callback: Callable | None = None,
    ) -> list[tuple[ChunkMetadata, list[ChunkQuestion]]]:
        """
        Enrich multiple chunks with rate limiting.

        Args:
            chunks: List of chunks to enrich
            doc_context: Optional document-level context
            progress_callback: Optional callback for progress updates

        Returns:
            List of (ChunkMetadata, list of ChunkQuestion) tuples
        """
        results = []
        total = len(chunks)

        # Process in batches
        for i in range(0, total, self.batch_size):
            batch = chunks[i:i + self.batch_size]

            # Process batch concurrently
            batch_tasks = [
                self.enrich_chunk(chunk, doc_context)
                for chunk in batch
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Handle results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch enrichment error for chunk {batch[j].id}: {result}")
                    results.append((self._empty_metadata(batch[j].id), []))
                else:
                    results.append(result)

            # Progress callback
            if progress_callback:
                completed = min(i + self.batch_size, total)
                progress_callback(completed, total)

            # Rate limiting delay between batches
            if i + self.batch_size < total:
                await asyncio.sleep(0.5)

        return results

    def _parse_metadata(self, chunk_id: str, result: dict) -> ChunkMetadata:
        """Parse LLM response into ChunkMetadata."""
        return ChunkMetadata(
            chunk_id=chunk_id,
            title=result.get("title"),
            summary=result.get("summary"),
            keywords=result.get("keywords", [])[:10],  # Limit keywords
            entities=self._normalize_entities(result.get("entities", {})),
            category=self._validate_category(result.get("category")),
            contextual_description=result.get("contextual_description"),
            enriched_at=datetime.utcnow(),
        )

    def _parse_questions(self, chunk_id: str, result: dict) -> list[ChunkQuestion]:
        """Parse LLM response into ChunkQuestion list."""
        questions_raw = result.get("questions", [])
        questions = []

        for q in questions_raw[:self.questions_per_chunk]:
            if isinstance(q, str) and q.strip():
                questions.append(ChunkQuestion(
                    chunk_id=chunk_id,
                    question=q.strip(),
                ))

        return questions

    def _normalize_entities(self, entities: dict | None) -> dict[str, list[str]]:
        """Normalize entities dictionary."""
        if not entities:
            return {}

        normalized = {}
        valid_keys = ["people", "organizations", "dates", "amounts", "locations"]

        for key in valid_keys:
            if key in entities and isinstance(entities[key], list):
                # Filter out empty strings and duplicates
                values = [str(v).strip() for v in entities[key] if v]
                normalized[key] = list(set(values))

        return normalized

    def _validate_category(self, category: str | None) -> str | None:
        """Validate category value."""
        valid_categories = {"definition", "procedure", "data", "narrative", "example", "reference"}
        if category and category.lower() in valid_categories:
            return category.lower()
        return None

    def _empty_metadata(self, chunk_id: str) -> ChunkMetadata:
        """Create empty metadata for failed enrichment."""
        return ChunkMetadata(
            chunk_id=chunk_id,
            title=None,
            summary=None,
            keywords=[],
            entities={},
            category=None,
            contextual_description=None,
            enriched_at=datetime.utcnow(),
        )


async def enrich_document_chunks(
    chunks: list[Chunk],
    doc_context: dict[str, Any] | None = None,
    llm_client: LLMClient | None = None,
) -> list[tuple[ChunkMetadata, list[ChunkQuestion]]]:
    """
    Convenience function to enrich all chunks for a document.

    Args:
        chunks: List of chunks to enrich
        doc_context: Optional document-level context
        llm_client: Optional LLM client instance

    Returns:
        List of (ChunkMetadata, list of ChunkQuestion) tuples
    """
    enricher = ChunkEnricher(llm_client=llm_client)
    return await enricher.enrich_batch(chunks, doc_context)


# Global enricher instance
chunk_enricher = ChunkEnricher()
