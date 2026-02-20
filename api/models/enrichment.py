"""Enrichment result model.

Defines the ``EnrichmentResult`` dataclass used by the document-level
enrichment pipeline and consumed by the chunking layer.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EnrichmentResult:
    """Result of LLM document-level enrichment."""

    document_type: str = "unknown"
    summary: str = ""
    entities: dict[str, Any] = field(default_factory=dict)
    key_topics: list[str] = field(default_factory=list)
    table_descriptions: list[str] = field(default_factory=list)
    success: bool = True
    error: str | None = None

