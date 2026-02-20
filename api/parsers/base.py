"""Base parser interface and common data structures."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.file_utils import get_file_type as _get_file_type


@dataclass
class TableData:
    """Represents a table extracted from a document."""

    headers: list[str]
    rows: list[list[Any]]
    title: str | None = None
    sheet_name: str | None = None  # For Excel files


@dataclass
class HeadingInfo:
    """Represents a heading/section in a document."""

    text: str
    level: int  # 1 = H1, 2 = H2, etc.
    page: int | None = None


@dataclass
class ParseResult:
    """Result of parsing a document."""

    text: str = ""
    headings: list[HeadingInfo] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # For tabular data
    column_headers: list[str] | None = None
    column_types: dict[str, str] | None = None
    sample_rows: list[list[Any]] | None = None
    row_count: int | None = None
    sheet_names: list[str] | None = None

    # Statistics for tabular
    numeric_stats: dict[str, dict[str, float]] | None = None

    # Full DataFrame for row-batch chunking (CSV/Excel)
    dataframe: Any | None = None


class BaseParser(ABC):
    """Abstract base class for file parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (without dot)."""
        pass

    def supports(self, file_path: Path) -> bool:
        """Check if this parser supports the given file."""
        return _get_file_type(file_path) in self.supported_extensions

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse the file and return structured content."""
        pass

    def get_file_type(self, file_path: Path) -> str:
        """Get the file type from the path."""
        return _get_file_type(file_path)


# Document types processed via manual pipeline (DocLayout-YOLO)
DOCUMENT_EXTENSIONS = ["pdf", "docx", "pptx"]


class ParserRegistry:
    """Registry for managing parsers."""

    def __init__(self):
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        """Register a parser."""
        self._parsers.append(parser)

    def get_parser(self, file_path: Path) -> BaseParser | None:
        """Get the appropriate parser for a file."""
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser
        return None

    def is_supported(self, file_path: Path) -> bool:
        """Check if any parser supports this file type."""
        ext = _get_file_type(file_path)
        # Check document extensions (manual processing)
        if ext in DOCUMENT_EXTENSIONS:
            return True
        # Check registered parsers (tabular data)
        return any(parser.supports(file_path) for parser in self._parsers)

    def is_document(self, file_path: Path) -> bool:
        """Check if file is a document type (manual processing)."""
        ext = _get_file_type(file_path)
        return ext in DOCUMENT_EXTENSIONS

    def is_tabular(self, file_path: Path) -> bool:
        """Check if file is a tabular type (CSV/Excel)."""
        return any(parser.supports(file_path) for parser in self._parsers)

    @property
    def supported_extensions(self) -> list[str]:
        """Get all supported file extensions."""
        extensions = list(DOCUMENT_EXTENSIONS)
        for parser in self._parsers:
            extensions.extend(parser.supported_extensions)
        return list(set(extensions))


# Global registry
parser_registry = ParserRegistry()
