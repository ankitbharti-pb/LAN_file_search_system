"""Query understanding and processing."""

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from enrichment.llm_client import get_llm_client
from enrichment.prompts import QUERY_UNDERSTANDING_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class QueryIntent:
    """Parsed query intent."""

    search_terms: str
    doc_type_filter: str | None = None
    entity_filters: dict[str, Any] = field(default_factory=dict)
    needs_synthesis: bool = False
    query_type: Literal["factual", "exploratory", "comparative", "aggregation"] = "factual"


class QueryProcessor:
    """Processes and understands search queries."""

    # Keywords that suggest specific document types (insurance domain)
    DOC_TYPE_KEYWORDS = {
        "policy_wording": ["policy wording", "policy document", "terms and conditions", "coverage terms", "policy terms", "wording"],
        "endorsement": ["endorsement", "amendment", "rider", "addendum", "policy change", "modification"],
        "certificate": ["certificate", "coi", "certificate of insurance", "proof of insurance", "cert"],
        "claim": ["claim", "claim form", "loss notice", "incident report", "claim submission", "fnol"],
        "underwriting": ["underwriting", "risk assessment", "underwriting guide", "risk evaluation", "uw guide"],
        "premium": ["premium", "rate", "pricing", "premium schedule", "rate sheet", "quote"],
        "process": ["process", "procedure", "workflow", "how to", "step by step", "sop", "guide"],
        "announcement": ["announcement", "update", "news", "bulletin", "notice", "memo"],
        "compliance": ["compliance", "regulatory", "audit", "regulation", "requirement", "filing"],
        "renewal": ["renewal", "renew", "expiration", "policy renewal", "renewal notice"],
        "cancellation": ["cancel", "cancellation", "termination", "policy cancellation", "non-renewal"],
        "coverage": ["coverage", "coverage summary", "declarations", "dec page", "limits"],
        "training": ["training", "onboarding", "education", "learning", "course"],
    }

    # Keywords that suggest need for synthesis
    SYNTHESIS_KEYWORDS = [
        "summarize",
        "explain",
        "compare",
        "difference",
        "relationship",
        "how does",
        "why",
        "what is the",
        "overview",
        "total",
        "average",
        "trend",
    ]

    def __init__(self, use_llm: bool = False):
        """
        Initialize query processor.

        Args:
            use_llm: Whether to use LLM for complex query understanding
        """
        self.use_llm = use_llm
        self._llm_client = None

    async def process(self, query: str) -> QueryIntent:
        """
        Process a query to extract intent and filters.

        Args:
            query: Raw search query

        Returns:
            QueryIntent with extracted information
        """
        query_lower = query.lower().strip()

        # Quick heuristic analysis
        doc_type = self._detect_doc_type(query_lower)
        needs_synthesis = self._detect_synthesis_need(query_lower)
        query_type = self._detect_query_type(query_lower)

        # For complex queries, optionally use LLM
        if self.use_llm and needs_synthesis:
            try:
                return await self._llm_understand(query)
            except Exception as e:
                logger.warning(f"LLM query understanding failed: {e}")

        return QueryIntent(
            search_terms=query,
            doc_type_filter=doc_type,
            entity_filters={},
            needs_synthesis=needs_synthesis,
            query_type=query_type,
        )

    def _detect_doc_type(self, query: str) -> str | None:
        """Detect if query is looking for specific document type."""
        for doc_type, keywords in self.DOC_TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return doc_type
        return None

    def _detect_synthesis_need(self, query: str) -> bool:
        """Detect if query needs LLM synthesis."""
        for keyword in self.SYNTHESIS_KEYWORDS:
            if keyword in query:
                return True

        # Questions usually need synthesis
        if query.endswith("?"):
            return True

        # Long queries often need synthesis
        if len(query.split()) > 10:
            return True

        return False

    def _detect_query_type(
        self, query: str
    ) -> Literal["factual", "exploratory", "comparative", "aggregation"]:
        """Detect the type of query."""
        if any(word in query for word in ["compare", "difference", "versus", "vs"]):
            return "comparative"

        if any(word in query for word in ["total", "sum", "average", "count", "how many"]):
            return "aggregation"

        if any(word in query for word in ["what", "how", "why", "explain"]):
            return "exploratory"

        return "factual"

    async def _llm_understand(self, query: str) -> QueryIntent:
        """Use LLM to understand complex queries."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()

        prompt = QUERY_UNDERSTANDING_PROMPT.format(query=query)
        result = await self._llm_client.complete_json(prompt)

        if not result:
            return QueryIntent(search_terms=query)

        return QueryIntent(
            search_terms=result.get("search_terms", query),
            doc_type_filter=result.get("doc_type_filter"),
            entity_filters=result.get("entity_filters", {}),
            needs_synthesis=result.get("needs_synthesis", False),
            query_type=result.get("query_type", "factual"),
        )


# Global instance
query_processor = QueryProcessor()
