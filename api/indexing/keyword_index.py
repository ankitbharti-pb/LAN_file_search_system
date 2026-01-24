"""BM25-based keyword index for text search."""

import logging
import pickle
import re
from pathlib import Path
from typing import List, Tuple, Set

from config.settings import settings

logger = logging.getLogger(__name__)

# Common English stopwords (avoiding nltk dependency)
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "what", "which", "who", "whom", "when", "where",
    "why", "how", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own", "same",
    "so", "than", "too", "very", "just", "also", "now", "here", "there",
    "then", "once", "if", "because", "until", "while", "about", "into",
    "through", "during", "before", "after", "above", "below", "between",
    "under", "again", "further", "any", "being", "having", "doing",
}


class KeywordIndex:
    """BM25 keyword index using rank_bm25."""

    def __init__(self):
        self._bm25 = None
        self._chunk_ids: List[str] = []
        self._corpus: List[List[str]] = []

    def add(self, chunk_id: str, text: str) -> None:
        """Add a document to the index."""
        tokens = self._tokenize(text)

        # Check if chunk already exists
        if chunk_id in self._chunk_ids:
            idx = self._chunk_ids.index(chunk_id)
            self._corpus[idx] = tokens
        else:
            self._chunk_ids.append(chunk_id)
            self._corpus.append(tokens)

        # Mark BM25 as needing rebuild
        self._bm25 = None

    def add_batch(self, chunk_ids: List[str], texts: List[str]) -> None:
        """Add multiple documents to the index."""
        for chunk_id, text in zip(chunk_ids, texts):
            tokens = self._tokenize(text)

            if chunk_id in self._chunk_ids:
                idx = self._chunk_ids.index(chunk_id)
                self._corpus[idx] = tokens
            else:
                self._chunk_ids.append(chunk_id)
                self._corpus.append(tokens)

        # Mark BM25 as needing rebuild
        self._bm25 = None

    def search(self, query: str, k: int = 10) -> List[Tuple[str, float]]:
        """Search for documents matching the query."""
        if not self._corpus:
            return []

        # Build BM25 if needed
        self._ensure_bm25()

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores
        scores = self._bm25.get_scores(query_tokens)

        # Get top-k results
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:k]:
            if score > 0:
                results.append((self._chunk_ids[idx], float(score)))

        return results

    def search_with_keywords(
        self, query: str, k: int = 10
    ) -> List[Tuple[str, float, List[str]]]:
        """Search for documents matching the query, returning matched keywords.

        Returns:
            List of (chunk_id, score, matched_keywords) tuples
        """
        if not self._corpus:
            return []

        # Build BM25 if needed
        self._ensure_bm25()

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Get BM25 scores
        scores = self._bm25.get_scores(query_tokens)

        # Get top-k results
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:k]:
            if score > 0:
                # Find which query tokens match this document
                doc_tokens = set(self._corpus[idx])
                matched = [t for t in query_tokens if t in doc_tokens]
                results.append((self._chunk_ids[idx], float(score), matched))

        return results

    def remove(self, chunk_ids: List[str]) -> int:
        """Remove documents from the index."""
        removed = 0
        for chunk_id in chunk_ids:
            if chunk_id in self._chunk_ids:
                idx = self._chunk_ids.index(chunk_id)
                self._chunk_ids.pop(idx)
                self._corpus.pop(idx)
                removed += 1

        if removed > 0:
            self._bm25 = None  # Need to rebuild

        return removed

    def save(self, path: Path | None = None) -> None:
        """Save the index to disk."""
        path = path or settings.bm25_index_path
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "chunk_ids": self._chunk_ids,
            "corpus": self._corpus,
        }

        with open(path, "wb") as f:
            pickle.dump(data, f)

        logger.info(f"Saved BM25 index to {path} ({len(self._chunk_ids)} documents)")

    def load(self, path: Path | None = None) -> bool:
        """Load the index from disk."""
        path = path or settings.bm25_index_path

        if not path.exists():
            logger.info("No existing BM25 index found")
            return False

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            self._chunk_ids = data["chunk_ids"]
            self._corpus = data["corpus"]
            self._bm25 = None  # Will be built on first search

            logger.info(f"Loaded BM25 index from {path} ({len(self._chunk_ids)} documents)")
            return True

        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            self._chunk_ids = []
            self._corpus = []
            self._bm25 = None
            return False

    def clear(self) -> None:
        """Clear the entire index."""
        self._chunk_ids = []
        self._corpus = []
        self._bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 with stopword removal and simple stemming."""
        # Convert to lowercase
        text = text.lower()

        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r"[^\w\s]", " ", text)

        # Split on whitespace
        tokens = text.split()

        # Filter: remove stopwords, short tokens, and apply simple suffix stripping
        processed = []
        for token in tokens:
            # Skip short tokens and stopwords
            if len(token) <= 2 or token in STOPWORDS:
                continue

            # Simple suffix stripping (basic stemming without nltk)
            stemmed = self._simple_stem(token)
            processed.append(stemmed)

        return processed

    def _simple_stem(self, word: str) -> str:
        """Apply simple suffix stripping for basic stemming.

        This is a lightweight alternative to Porter/Snowball stemmer.
        Handles common English suffixes without external dependencies.
        """
        # Common suffix patterns (order matters - longer suffixes first)
        suffixes = [
            ("ational", "ate"),
            ("tional", "tion"),
            ("encies", "ence"),
            ("ancies", "ance"),
            ("iveness", "ive"),
            ("fulness", "ful"),
            ("ousness", "ous"),
            ("ization", "ize"),
            ("isation", "ise"),
            ("ating", "ate"),
            ("izing", "ize"),
            ("ising", "ise"),
            ("ities", "ity"),
            ("ments", "ment"),
            ("ness", ""),
            ("ings", ""),
            ("tion", "t"),
            ("sion", "s"),
            ("ious", ""),
            ("eous", ""),
            ("ment", ""),
            ("able", ""),
            ("ible", ""),
            ("ally", ""),
            ("ful", ""),
            ("ous", ""),
            ("ive", ""),
            ("ing", ""),
            ("ion", ""),
            ("ies", "y"),
            ("es", ""),
            ("ed", ""),
            ("ly", ""),
            ("er", ""),
            ("s", ""),
        ]

        for suffix, replacement in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return word[:-len(suffix)] + replacement

        return word

    def _ensure_bm25(self) -> None:
        """Ensure BM25 index is built."""
        if self._bm25 is None and self._corpus:
            try:
                from rank_bm25 import BM25Okapi

                self._bm25 = BM25Okapi(self._corpus)
                logger.debug(f"Built BM25 index with {len(self._corpus)} documents")
            except ImportError:
                raise ImportError(
                    "rank_bm25 not installed. Install with: pip install rank-bm25"
                )

    @property
    def size(self) -> int:
        """Get number of documents in the index."""
        return len(self._chunk_ids)


# Global instance
keyword_index = KeywordIndex()
