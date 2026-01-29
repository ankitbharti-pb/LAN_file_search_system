"""Query preprocessing for improved search accuracy.

Handles insurance-specific acronym expansion, term normalization, and
optional spell correction.
"""

import logging
import re
from typing import List, Tuple

from config.settings import settings

logger = logging.getLogger(__name__)


# Insurance acronyms and their expansions
INSURANCE_ACRONYMS = {
    # Certificate and documentation
    "coi": "certificate of insurance",
    "acord": "association for cooperative operations research and development",

    # Liability types
    "gl": "general liability",
    "cgl": "commercial general liability",
    "pl": "professional liability",
    "pol": "professional liability",
    "el": "employers liability",

    # Workers compensation
    "wc": "workers compensation",
    "wci": "workers compensation insurance",

    # Directors and officers
    "d&o": "directors and officers",
    "dno": "directors and officers",
    "do": "directors officers",

    # Errors and omissions
    "e&o": "errors and omissions",
    "eno": "errors and omissions",

    # Property and casualty
    "p&c": "property and casualty",
    "pc": "property casualty",

    # Employment practices
    "epli": "employment practices liability insurance",
    "epl": "employment practices liability",

    # Business types
    "bop": "business owners policy",
    "cpp": "commercial package policy",

    # Auto coverage
    "um": "uninsured motorist",
    "uim": "underinsured motorist",
    "pip": "personal injury protection",
    "bi": "bodily injury",
    "pd": "property damage",
    "comp": "comprehensive",
    "coll": "collision",

    # Other coverage types
    "cyb": "cyber liability",
    "cyber": "cyber liability",
    "aop": "all other perils",
    "bpp": "business personal property",
    "bii": "business income insurance",
    "ee": "extra expense",

    # Limits and deductibles
    "occ": "occurrence",
    "agg": "aggregate",
    "ded": "deductible",
    "sir": "self insured retention",

    # Process and documentation
    "fnol": "first notice of loss",
    "siu": "special investigations unit",
    "tpa": "third party administrator",
    "mga": "managing general agent",
    "mga": "managing general agency",

    # Reinsurance
    "ri": "reinsurance",
    "xs": "excess",
    "qsr": "quota share reinsurance",
}

# Common insurance term variations/misspellings
TERM_NORMALIZATIONS = {
    "policyholder": "policy holder",
    "coinsurance": "co insurance",
    "selfinsured": "self insured",
    "sublimit": "sub limit",
    "deductable": "deductible",  # Common misspelling
    "liabilty": "liability",  # Common misspelling
    "insurence": "insurance",  # Common misspelling
    "cliam": "claim",  # Common misspelling
    "prmeium": "premium",  # Common misspelling
    "renewel": "renewal",  # Common misspelling
}


class QueryPreprocessor:
    """Preprocess search queries for improved retrieval.

    Handles:
    - Insurance acronym expansion
    - Term normalization
    - Query cleaning
    """

    def __init__(self, expand_acronyms: bool = True, normalize_terms: bool = True):
        """Initialize query preprocessor.

        Args:
            expand_acronyms: Whether to expand insurance acronyms
            normalize_terms: Whether to normalize/correct terms
        """
        self.expand_acronyms = expand_acronyms
        self.normalize_terms = normalize_terms

    def preprocess(self, query: str) -> Tuple[str, List[str]]:
        """Preprocess a search query.

        Args:
            query: Raw search query

        Returns:
            Tuple of (processed_query, list_of_expansions_applied)
        """
        expansions = []
        processed = query.lower().strip()

        # Expand acronyms
        if self.expand_acronyms:
            processed, acr_expansions = self._expand_acronyms(processed)
            expansions.extend(acr_expansions)

        # Normalize terms
        if self.normalize_terms:
            processed, norm_expansions = self._normalize_terms(processed)
            expansions.extend(norm_expansions)

        # Clean up whitespace
        processed = re.sub(r"\s+", " ", processed).strip()

        return processed, expansions

    def _expand_acronyms(self, text: str) -> Tuple[str, List[str]]:
        """Expand insurance acronyms in text.

        Args:
            text: Input text

        Returns:
            Tuple of (expanded_text, list_of_expansions)
        """
        expansions = []
        words = text.split()
        result_words = []

        for word in words:
            # Remove punctuation for matching
            clean_word = re.sub(r"[^\w&]", "", word)

            if clean_word in INSURANCE_ACRONYMS:
                expansion = INSURANCE_ACRONYMS[clean_word]
                # Keep both the acronym and expansion for better matching
                result_words.append(f"{word} {expansion}")
                expansions.append(f"{clean_word} -> {expansion}")
            else:
                result_words.append(word)

        return " ".join(result_words), expansions

    def _normalize_terms(self, text: str) -> Tuple[str, List[str]]:
        """Normalize/correct terms in text.

        Args:
            text: Input text

        Returns:
            Tuple of (normalized_text, list_of_normalizations)
        """
        normalizations = []

        for term, normalized in TERM_NORMALIZATIONS.items():
            if term in text:
                # Keep both the original and normalized form
                text = text.replace(term, f"{term} {normalized}")
                normalizations.append(f"{term} -> {normalized}")

        return text, normalizations

    def expand_query_terms(self, query: str) -> str:
        """Simple expansion without tracking changes.

        Args:
            query: Search query

        Returns:
            Expanded query string
        """
        processed, _ = self.preprocess(query)
        return processed


def preprocess_query(query: str) -> str:
    """Convenience function for query preprocessing.

    Args:
        query: Raw search query

    Returns:
        Preprocessed query string
    """
    if not settings.query_expand_synonyms:
        return query

    preprocessor = QueryPreprocessor()
    processed, expansions = preprocessor.preprocess(query)

    if expansions:
        logger.debug(f"Query expansions: {expansions}")

    return processed


# Global instance
query_preprocessor = QueryPreprocessor()
