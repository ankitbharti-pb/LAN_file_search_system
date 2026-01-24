"""Document processing module for manual multi-stage workflow.

This module handles:
- Layout detection using DocLayout-YOLO
- PDF page rendering
- Text extraction from detected regions
- Markdown generation
- DOCX/PPTX/CSV/Excel processing
"""

from processing.layout_detector import layout_detector, LayoutDetector
from processing.page_renderer import page_renderer, PageRenderer
from processing.text_extractor import text_extractor, TextExtractor
from processing.docx_processor import docx_processor, DocxProcessor
from processing.pptx_processor import pptx_processor, PptxProcessor
from processing.tabular_processor import tabular_processor, TabularProcessor
from processing.box_filtering import box_filter, BoxFilter, BoxFilterConfig

__all__ = [
    "layout_detector",
    "LayoutDetector",
    "page_renderer",
    "PageRenderer",
    "text_extractor",
    "TextExtractor",
    "docx_processor",
    "DocxProcessor",
    "pptx_processor",
    "PptxProcessor",
    "tabular_processor",
    "TabularProcessor",
    "box_filter",
    "BoxFilter",
    "BoxFilterConfig",
]
