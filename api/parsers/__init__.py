"""File parsers for the LAN File Search System.

Note: DocumentParser (Docling) has been removed.
PDF/DOCX/PPTX files are now processed via the manual processing pipeline
using DocLayout-YOLO for layout detection and PyMuPDF for text extraction.
"""

from parsers.base import (
    BaseParser,
    ParseResult,
    TableData,
    HeadingInfo,
    ParserRegistry,
    parser_registry,
)
from parsers.csv_parser import CSVParser, csv_parser
from parsers.excel_parser import ExcelParser, excel_parser


# Register tabular parsers only (document parsing moved to processing module)
parser_registry.register(csv_parser)
parser_registry.register(excel_parser)


__all__ = [
    "BaseParser",
    "ParseResult",
    "TableData",
    "HeadingInfo",
    "ParserRegistry",
    "parser_registry",
    "CSVParser",
    "csv_parser",
    "ExcelParser",
    "excel_parser",
]
