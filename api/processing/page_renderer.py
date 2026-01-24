"""PDF page rendering using PyMuPDF."""

import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PageRenderer:
    """Renders PDF pages as images using PyMuPDF."""

    def __init__(self, dpi: int = 150):
        """Initialize the page renderer.

        Args:
            dpi: Resolution for rendered images (default 150)
        """
        self.dpi = dpi
        self.zoom = dpi / 72  # PDF default is 72 DPI

    def render_pdf_pages(
        self,
        pdf_path: Path,
        output_dir: Path,
    ) -> list[Path]:
        """Convert all PDF pages to PNG images.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save page images

        Returns:
            List of paths to generated page images
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Rendering PDF pages: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        page_paths = []

        for i, page in enumerate(doc):
            # Create transformation matrix for scaling
            mat = fitz.Matrix(self.zoom, self.zoom)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat)

            # Save as PNG
            output_path = output_dir / f"page_{i + 1:03d}.png"
            pix.save(str(output_path))
            page_paths.append(output_path)

            logger.debug(f"Rendered page {i + 1} to: {output_path}")

        doc.close()

        logger.info(f"Rendered {len(page_paths)} pages from PDF")
        return page_paths

    def render_single_page(
        self,
        pdf_path: Path,
        page_number: int,
        output_path: Path,
    ) -> Path:
        """Render a single PDF page to an image.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (1-indexed)
            output_path: Path to save the page image

        Returns:
            Path to the generated image
        """
        doc = fitz.open(str(pdf_path))

        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise ValueError(f"Invalid page number: {page_number}. PDF has {len(doc)} pages.")

        page = doc[page_number - 1]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(output_path))

        doc.close()
        return output_path

    def get_page_count(self, pdf_path: Path) -> int:
        """Get the number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of pages
        """
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count

    def get_page_dimensions(
        self,
        pdf_path: Path,
        page_number: int = 1,
    ) -> tuple[int, int]:
        """Get the dimensions of a PDF page at the render DPI.

        Args:
            pdf_path: Path to the PDF file
            page_number: Page number (1-indexed)

        Returns:
            Tuple of (width, height) in pixels at render DPI
        """
        doc = fitz.open(str(pdf_path))

        if page_number < 1 or page_number > len(doc):
            doc.close()
            raise ValueError(f"Invalid page number: {page_number}")

        page = doc[page_number - 1]
        rect = page.rect

        # Calculate dimensions at render DPI
        width = int(rect.width * self.zoom)
        height = int(rect.height * self.zoom)

        doc.close()
        return (width, height)


# Global instance
page_renderer = PageRenderer()
