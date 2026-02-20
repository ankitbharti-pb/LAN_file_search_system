"""Search request / response schemas.

Re-exports from ``models.search_result`` for convenience so that other
modules can import from ``api.schemas.search`` consistently.
"""

from models.search_result import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SourceInfo,
)

__all__ = [
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "SourceInfo",
]

