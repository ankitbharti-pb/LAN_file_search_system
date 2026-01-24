"""LLM enrichment layer for the LAN File Search System."""

from enrichment.llm_client import (
    LLMClient,
    OpenAIClient,
    GeminiClient,
    get_llm_client,
    llm_client,
)
from enrichment.entity_extractor import (
    EnrichmentResult,
    EntityExtractor,
    entity_extractor,
)
from enrichment.prompts import (
    DOCUMENT_ENRICHMENT_SYSTEM_PROMPT,
    DOCUMENT_ENRICHMENT_PROMPT,
    TABULAR_ENRICHMENT_PROMPT,
    QUERY_UNDERSTANDING_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT,
)

__all__ = [
    "LLMClient",
    "OpenAIClient",
    "GeminiClient",
    "get_llm_client",
    "llm_client",
    "EnrichmentResult",
    "EntityExtractor",
    "entity_extractor",
    "DOCUMENT_ENRICHMENT_SYSTEM_PROMPT",
    "DOCUMENT_ENRICHMENT_PROMPT",
    "TABULAR_ENRICHMENT_PROMPT",
    "QUERY_UNDERSTANDING_PROMPT",
    "RESPONSE_SYNTHESIS_PROMPT",
]
