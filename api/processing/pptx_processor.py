"""PPTX presentation processing for text extraction."""

import logging
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

logger = logging.getLogger(__name__)


class PptxProcessor:
    """Process PPTX files and extract text as markdown."""

    def extract(self, file_path: Path) -> str:
        """Extract text from a PPTX file and convert to markdown.

        Args:
            file_path: Path to the PPTX file

        Returns:
            Markdown-formatted text content
        """
        logger.info(f"Extracting text from PPTX: {file_path}")

        prs = Presentation(str(file_path))
        markdown_parts = []
        markdown_parts.append(f"# {file_path.name}\n")

        for slide_num, slide in enumerate(prs.slides, 1):
            slide_parts = []
            slide_parts.append(f"\n---\n## Slide {slide_num}")

            # Get slide title if available
            title = self._get_slide_title(slide)
            if title:
                slide_parts.append(f"### {title}")

            # Process all shapes
            for shape in slide.shapes:
                text = self._extract_shape_text(shape)
                if text and text != title:  # Skip if it's the title we already added
                    slide_parts.append(text)

            # Get speaker notes if available
            notes = self._get_notes(slide)
            if notes:
                slide_parts.append(f"\n*Speaker Notes:*\n{notes}")

            if len(slide_parts) > 1:  # More than just the slide header
                markdown_parts.append("\n\n".join(slide_parts))

        markdown = "\n\n".join(markdown_parts)
        logger.info(f"Extracted {len(markdown)} characters from PPTX ({slide_num} slides)")
        return markdown

    def _get_slide_title(self, slide) -> str | None:
        """Extract the title from a slide."""
        if slide.shapes.title:
            return slide.shapes.title.text.strip()

        # Look for a shape that might be a title
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.paragraphs:
                text = shape.text.strip()
                # If it's short and at the top, it might be a title
                if text and len(text) < 200:
                    return text

        return None

    def _extract_shape_text(self, shape) -> str | None:
        """Extract text from a shape.

        Args:
            shape: Shape object from python-pptx

        Returns:
            Extracted text or None
        """
        # Handle text frames
        if shape.has_text_frame:
            paragraphs = []
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if text:
                    # Check if it's a bullet/list item
                    if para.level > 0 or self._is_bullet(para):
                        indent = "  " * para.level
                        paragraphs.append(f"{indent}- {text}")
                    else:
                        paragraphs.append(text)
            if paragraphs:
                return "\n".join(paragraphs)

        # Handle tables
        if shape.has_table:
            return self._format_table(shape.table)

        # Handle grouped shapes
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            group_texts = []
            for sub_shape in shape.shapes:
                text = self._extract_shape_text(sub_shape)
                if text:
                    group_texts.append(text)
            if group_texts:
                return "\n".join(group_texts)

        return None

    def _is_bullet(self, paragraph) -> bool:
        """Check if a paragraph is a bullet point."""
        try:
            if paragraph.bullet:
                return paragraph.bullet.type is not None
        except AttributeError:
            pass
        return False

    def _format_table(self, table) -> str | None:
        """Format a table as markdown.

        Args:
            table: Table object from python-pptx

        Returns:
            Markdown-formatted table string
        """
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")

        if len(rows) < 1:
            return None

        # Add separator after header row
        num_cols = len(table.rows[0].cells)
        separator = "| " + " | ".join(["---"] * num_cols) + " |"

        result = [rows[0], separator] + rows[1:]
        return "\n".join(result)

    def _get_notes(self, slide) -> str | None:
        """Get speaker notes from a slide."""
        try:
            if slide.has_notes_slide:
                notes_slide = slide.notes_slide
                notes_text = notes_slide.notes_text_frame.text.strip()
                if notes_text:
                    return notes_text
        except AttributeError:
            pass
        return None


# Global instance
pptx_processor = PptxProcessor()
