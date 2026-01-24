"""Text extraction from PDF using detected layout regions with VLM support."""

import json
import logging
from pathlib import Path

import fitz  # PyMuPDF

from config.settings import settings
from indexing.metadata_store import metadata_store
from processing.vlm_client import vlm_client
from processing.region_cropper import region_cropper

logger = logging.getLogger(__name__)


# DocLayout-YOLO label to extraction method mapping
LABEL_EXTRACTION = {
    # Direct text extraction (PyMuPDF)
    "title": "text",
    "plain text": "text",
    "text": "text",
    "section-header": "text",

    # VLM extraction
    "table": "vlm_table",
    "figure": "vlm_figure",
    "isolate_formula": "vlm_formula",

    # Caption handling (text extraction)
    "table_caption": "text",
    "table_footnote": "text",
    "figure_caption": "text",
    "formula_caption": "text",

    # Skip these
    "abandon": "skip",
    "page-header": "skip",
    "page-footer": "skip",
}


# Label to markdown format mapping
LABEL_FORMAT = {
    "title": "h1",
    "section-header": "h2",
    "plain text": "paragraph",
    "text": "paragraph",
    "table": "table",
    "table_caption": "caption",
    "table_footnote": "footnote",
    "figure": "figure",
    "figure_caption": "caption",
    "isolate_formula": "formula",
    "formula_caption": "caption",
}


class TextExtractor:
    """Extract text from PDF using layout detection results with VLM support."""

    def __init__(self, use_vlm: bool = True, vlm_fallback_ocr: bool = True):
        """Initialize text extractor.

        Args:
            use_vlm: Whether to use VLM for tables/figures/formulas
            vlm_fallback_ocr: Whether to use VLM OCR when no text found
        """
        self.use_vlm = use_vlm
        self.vlm_fallback_ocr = vlm_fallback_ocr

    async def extract_pdf(self, doc_id: str) -> str:
        """Extract text from a PDF document using layout detection regions.

        Uses XY-Cut++ reading order and VLM for tables/figures/formulas.

        Args:
            doc_id: Document ID to extract text from

        Returns:
            Markdown-formatted text content
        """
        # Get document info
        doc = await metadata_store.get_document(doc_id)
        if not doc:
            raise ValueError(f"Document not found: {doc_id}")

        pdf_path = Path(doc.file_path)
        if not pdf_path.exists():
            raise ValueError(f"PDF file not found: {pdf_path}")

        # Get page layout data
        pages = await metadata_store.get_pages(doc_id)
        if not pages:
            raise ValueError(f"No layout data found for document: {doc_id}")

        logger.info(f"Extracting text from {len(pages)} pages")

        # Check VLM availability if enabled
        vlm_available = False
        if self.use_vlm:
            try:
                vlm_available = await vlm_client.is_available()
                if vlm_available:
                    logger.info("VLM is available for enhanced extraction")
                else:
                    logger.warning("VLM not available, using fallback extraction")
            except Exception as e:
                logger.warning(f"VLM check failed: {e}, using fallback extraction")

        # Open PDF
        pdf_doc = fitz.open(str(pdf_path))

        markdown_parts = []
        markdown_parts.append(f"# {doc.file_name}\n")

        for page_data in pages:
            page_num = page_data["page_number"]
            layout_json = page_data["layout_json"]
            image_path = page_data.get("image_path")

            if not layout_json:
                continue

            detections = json.loads(layout_json)
            if not detections:
                continue

            # Get PDF page (0-indexed)
            pdf_page = pdf_doc[page_num - 1]

            # Get page dimensions for coordinate scaling
            page_rect = pdf_page.rect
            page_width = page_rect.width
            page_height = page_rect.height

            # Get image dimensions from the rendered page
            # The layout detection was done on rendered images at 150 DPI
            dpi = 150
            zoom = dpi / 72
            img_width = page_width * zoom
            img_height = page_height * zoom

            # Scale factors from image coordinates to PDF coordinates
            scale_x = page_width / img_width
            scale_y = page_height / img_height

            # Sort detections by reading_order (already computed by XY-Cut++)
            sorted_detections = sorted(
                detections,
                key=lambda d: d.get("reading_order", 0)
            )

            page_text_parts = []
            crops_dir = Path(image_path).parent / "crops" if image_path else None

            for det in sorted_detections:
                label = det["label"].lower()
                bbox = det["bbox"]  # [x1, y1, x2, y2] in image coordinates
                reading_order = det.get("reading_order", 0)

                extraction_type = LABEL_EXTRACTION.get(label, "text")

                if extraction_type == "skip":
                    continue

                content = await self._extract_region(
                    extraction_type=extraction_type,
                    label=label,
                    bbox=bbox,
                    pdf_page=pdf_page,
                    scale_x=scale_x,
                    scale_y=scale_y,
                    image_path=Path(image_path) if image_path else None,
                    crops_dir=crops_dir,
                    reading_order=reading_order,
                    vlm_available=vlm_available,
                    doc_id=doc_id,
                    page_num=page_num,
                )

                if content:
                    formatted = self._format_content(label, content, doc_id=doc_id)
                    if formatted:
                        page_text_parts.append(formatted)

            if page_text_parts:
                if page_num > 1:
                    markdown_parts.append(f"\n---\n*Page {page_num}*\n")
                markdown_parts.extend(page_text_parts)

            # Store extracted text for this page
            page_text = "\n".join(page_text_parts)
            await metadata_store.update_page_text(doc_id, page_num, page_text)

            # Cleanup cropped images after processing each page
            if crops_dir:
                region_cropper.cleanup_crops(crops_dir)

        pdf_doc.close()

        markdown = "\n\n".join(markdown_parts)
        logger.info(f"Extracted {len(markdown)} characters of markdown")

        return markdown

    async def _extract_region(
        self,
        extraction_type: str,
        label: str,
        bbox: list[float],
        pdf_page,
        scale_x: float,
        scale_y: float,
        image_path: Path | None,
        crops_dir: Path | None,
        reading_order: int,
        vlm_available: bool,
        doc_id: str = "",
        page_num: int = 1,
    ) -> str | tuple[str, Path | None] | None:
        """Extract content from a single region.

        Args:
            extraction_type: Type of extraction (text, vlm_table, vlm_figure, vlm_formula)
            label: Layout label
            bbox: Bounding box in image coordinates
            pdf_page: PyMuPDF page object
            scale_x: X scale factor from image to PDF
            scale_y: Y scale factor from image to PDF
            image_path: Path to page image (for VLM)
            crops_dir: Directory for cropped images
            reading_order: Reading order index
            vlm_available: Whether VLM is available
            doc_id: Document ID (for permanent image storage)
            page_num: Page number (1-indexed)

        Returns:
            Extracted text content, or tuple of (description, image_path) for figures
        """
        if extraction_type == "text":
            # Use PyMuPDF for text extraction
            pdf_rect = fitz.Rect(
                bbox[0] * scale_x,
                bbox[1] * scale_y,
                bbox[2] * scale_x,
                bbox[3] * scale_y,
            )
            text = pdf_page.get_text("text", clip=pdf_rect).strip()

            # Fallback to VLM OCR if no text found
            if not text and vlm_available and self.vlm_fallback_ocr and image_path and crops_dir:
                crop_path = crops_dir / f"region_{reading_order:03d}.png"
                try:
                    region_cropper.crop_region(image_path, bbox, crop_path)
                    text = await vlm_client.ocr_text(crop_path)
                except Exception as e:
                    logger.warning(f"VLM OCR failed for region {reading_order}: {e}")

            return text

        elif extraction_type == "vlm_table":
            if vlm_available and image_path and crops_dir:
                crop_path = crops_dir / f"table_{reading_order:03d}.png"
                try:
                    region_cropper.crop_region(image_path, bbox, crop_path)
                    return await vlm_client.extract_table(crop_path)
                except Exception as e:
                    logger.warning(f"VLM table extraction failed: {e}")

            # Fallback to PyMuPDF
            return self._fallback_text_extract(bbox, pdf_page, scale_x, scale_y)

        elif extraction_type == "vlm_figure":
            if vlm_available and image_path and doc_id:
                # Save to permanent location for embedding in markdown
                permanent_path = region_cropper.get_permanent_path(
                    doc_id=doc_id,
                    page_num=page_num,
                    region_type="figure",
                    reading_order=reading_order,
                )
                try:
                    region_cropper.crop_region(image_path, bbox, permanent_path)
                    description = await vlm_client.describe_figure(permanent_path)
                    # Return tuple of (description, image_path)
                    return (description, permanent_path)
                except Exception as e:
                    logger.warning(f"VLM figure description failed: {e}")

            return ("[Unable to describe]", None)

        elif extraction_type == "vlm_formula":
            if vlm_available and image_path and crops_dir:
                crop_path = crops_dir / f"formula_{reading_order:03d}.png"
                try:
                    region_cropper.crop_region(image_path, bbox, crop_path)
                    return await vlm_client.extract_formula(crop_path)
                except Exception as e:
                    logger.warning(f"VLM formula extraction failed: {e}")

            # Fallback to PyMuPDF
            return self._fallback_text_extract(bbox, pdf_page, scale_x, scale_y)

        return None

    def _fallback_text_extract(
        self,
        bbox: list[float],
        pdf_page,
        scale_x: float,
        scale_y: float,
    ) -> str:
        """Fallback to PyMuPDF text extraction.

        Args:
            bbox: Bounding box in image coordinates
            pdf_page: PyMuPDF page object
            scale_x: X scale factor
            scale_y: Y scale factor

        Returns:
            Extracted text
        """
        pdf_rect = fitz.Rect(
            bbox[0] * scale_x,
            bbox[1] * scale_y,
            bbox[2] * scale_x,
            bbox[3] * scale_y,
        )
        return pdf_page.get_text("text", clip=pdf_rect).strip()

    def _format_content(
        self,
        label: str,
        content: str | tuple[str, Path | None],
        doc_id: str = "",
    ) -> str | None:
        """Format extracted content as markdown.

        Args:
            label: Layout element label
            content: Extracted text content, or tuple of (description, image_path) for figures
            doc_id: Document ID (for image URL generation)

        Returns:
            Formatted markdown string or None
        """
        # Handle figure with image path tuple
        if isinstance(content, tuple):
            description, image_path = content
            if image_path and doc_id:
                # Generate relative URL for the image
                try:
                    rel_path = image_path.relative_to(
                        settings.data_folder / "processing" / doc_id / "images"
                    )
                    image_url = f"/processing/images/{doc_id}/{rel_path.as_posix()}"
                    desc_text = description.strip() if description else ""
                    if desc_text:
                        return f"![Figure]({image_url})\n\n*{desc_text}*"
                    return f"![Figure]({image_url})"
                except ValueError:
                    pass
            # Fallback if no image path
            desc_text = description.strip() if description else "[Unable to describe]"
            return f"**[Figure]** {desc_text}"

        if not content:
            return None

        content = content.strip()
        if not content:
            return None

        fmt = LABEL_FORMAT.get(label.lower(), "paragraph")

        if fmt == "h1":
            # Normalize whitespace for headers
            return f"# {' '.join(content.split())}"

        elif fmt == "h2":
            return f"## {' '.join(content.split())}"

        elif fmt == "paragraph":
            return content

        elif fmt == "table":
            # VLM returns markdown table directly
            return content

        elif fmt == "figure":
            return f"**[Figure]** {content}"

        elif fmt == "formula":
            # VLM returns LaTeX with $$ delimiters
            if not content.startswith("$$"):
                content = f"$$\n{content}\n$$"
            return content

        elif fmt == "caption":
            return f"*{content}*"

        elif fmt == "footnote":
            return f"[^]: {content}"

        return content


# Global instance using application settings
text_extractor = TextExtractor(
    use_vlm=settings.use_vlm_extraction,
    vlm_fallback_ocr=settings.vlm_fallback_ocr,
)
