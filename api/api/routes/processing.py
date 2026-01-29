"""Processing routes for manual document workflow."""

import json
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

import httpx

from config.settings import settings
from core.utils import generate_document_id, compute_file_hash
from indexing.metadata_store import metadata_store
from processing.layout_detector import layout_detector
from processing.page_renderer import page_renderer
from processing.text_extractor import text_extractor
from processing.docx_processor import docx_processor
from processing.pptx_processor import pptx_processor
from processing.tabular_processor import tabular_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/processing", tags=["processing"])


# ============== Response Models ==============


class ProcessingStatus(BaseModel):
    """Document processing status response."""
    document_id: str
    file_name: str
    file_type: str
    processing_status: str
    page_count: int | None = None
    has_layout: bool = False
    has_markdown: bool = False


class LayoutDetectionResponse(BaseModel):
    """Layout detection result response."""
    document_id: str
    pages: int
    status: str


class PageInfo(BaseModel):
    """Information about a single page."""
    page_number: int
    has_image: bool
    has_annotated_image: bool
    has_unfiltered_annotated_image: bool = False
    has_layout: bool
    detection_count: int = 0
    unfiltered_detection_count: int = 0
    boxes_removed_by_filter: int = 0


class PagesListResponse(BaseModel):
    """List of pages for a document."""
    document_id: str
    total_pages: int
    pages: list[PageInfo]


class DetectionInfo(BaseModel):
    """Single detection info."""
    bbox: list[float]
    label: str
    confidence: float


class PageLayoutResponse(BaseModel):
    """Layout detection results for a page."""
    page_number: int
    detections: list[DetectionInfo]


class MarkdownResponse(BaseModel):
    """Markdown content response."""
    document_id: str
    extracted_markdown: str | None
    reviewed_markdown: str | None
    processing_status: str


class MarkdownUpdateRequest(BaseModel):
    """Request to update reviewed markdown."""
    markdown: str


# ============== Helper Functions ==============


def get_processing_dir(doc_id: str) -> Path:
    """Get the processing directory for a document."""
    return settings.data_folder / "processing" / doc_id


# ============== Endpoints ==============


# VLM Status endpoint - must be before {doc_id} routes to avoid path matching conflict
class VLMStatusResponse(BaseModel):
    """VLM availability status response."""
    status: str
    provider: str = ""
    model_loaded: bool = False
    configured_model: str = ""
    available_models: list[str] = []
    error: str | None = None


@router.get("/vlm/status", response_model=VLMStatusResponse)
async def get_vlm_status() -> VLMStatusResponse:
    """Check if VLM is available for the configured provider.

    Supports multiple providers: ollama (local) and huggingface (cloud).
    Returns the status and whether the configured model is available.
    """
    provider = settings.vlm_provider

    if provider == "huggingface":
        # HuggingFace provider
        configured = settings.huggingface_vlm_model
        has_key = bool(settings.huggingface_api_key)

        if not has_key:
            return VLMStatusResponse(
                status="unavailable",
                provider=provider,
                configured_model=configured,
                error="HuggingFace API key not configured. Set HUGGINGFACE_API_KEY in .env",
            )

        return VLMStatusResponse(
            status="available",
            provider=provider,
            model_loaded=True,
            configured_model=configured,
            available_models=[configured],
        )

    else:
        # Ollama provider (default)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_base_url}/api/tags")

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    model_names = [m.get("name", "") for m in models]

                    configured = settings.ollama_model
                    has_model = any(configured in name for name in model_names)

                    return VLMStatusResponse(
                        status="available",
                        provider=provider,
                        model_loaded=has_model,
                        configured_model=configured,
                        available_models=model_names,
                    )

                return VLMStatusResponse(
                    status="unavailable",
                    provider=provider,
                    configured_model=settings.ollama_model,
                    error=f"Ollama returned status {response.status_code}",
                )

        except httpx.ConnectError:
            return VLMStatusResponse(
                status="unavailable",
                provider=provider,
                configured_model=settings.ollama_model,
                error="Cannot connect to Ollama server. Is it running?",
            )
        except Exception as e:
            return VLMStatusResponse(
                status="unavailable",
                provider=provider,
                configured_model=settings.ollama_model,
                error=str(e),
            )


@router.get("/images/{doc_id}/{filename:path}")
async def get_extracted_image(doc_id: str, filename: str) -> FileResponse:
    """Serve extracted figure/table images.

    Images are stored at: data/processing/{doc_id}/images/{filename}
    These are cropped regions from document pages used in markdown output.
    """
    image_path = settings.data_folder / "processing" / doc_id / "images" / filename

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    # Security: ensure path is within expected directory
    try:
        image_path.resolve().relative_to(
            (settings.data_folder / "processing").resolve()
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=image_path.name,
    )


@router.get("/{doc_id}/status", response_model=ProcessingStatus)
async def get_processing_status(doc_id: str) -> ProcessingStatus:
    """Get the processing status of a document."""
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return ProcessingStatus(
        document_id=doc.id,
        file_name=doc.file_name,
        file_type=doc.file_type,
        processing_status=doc.processing_status,
        page_count=doc.page_count,
        has_layout=doc.layout_data is not None,
        has_markdown=doc.extracted_markdown is not None,
    )


@router.post("/{doc_id}/detect-layout", response_model=LayoutDetectionResponse)
async def detect_layout(
    doc_id: str,
    conf: float = Query(default=0.2, ge=0.0, le=1.0, description="Confidence threshold"),
) -> LayoutDetectionResponse:
    """Run layout detection on a PDF document.

    This converts each PDF page to an image, runs DocLayout-YOLO detection,
    and generates annotated images showing detected regions.
    """
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.file_type != "pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Layout detection only supported for PDF files, got: {doc.file_type}"
        )

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    logger.info(f"Starting layout detection for: {doc.file_name}")

    # Set up processing directory
    processing_dir = get_processing_dir(doc_id)
    pages_dir = processing_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Render PDF pages to images
    logger.info("Rendering PDF pages...")
    page_images = page_renderer.render_pdf_pages(file_path, pages_dir)

    # Step 2: Run detection on each page
    all_detections = []
    for i, page_path in enumerate(page_images):
        page_num = i + 1
        logger.info(f"Detecting layout on page {page_num}/{len(page_images)}")

        # Run detection with filter info to get both filtered and unfiltered
        result = layout_detector.detect_with_filter_info(page_path, conf=conf)
        filtered_dict = layout_detector.detections_to_dict(result.filtered_detections)
        unfiltered_dict = layout_detector.detections_to_dict(result.unfiltered_detections)

        # Generate filtered annotated image (default view)
        annotated_path = pages_dir / f"page_{page_num:03d}_annotated.png"
        layout_detector.annotate(page_path, annotated_path, result.filtered_detections)

        # Generate unfiltered annotated image (for comparison)
        unfiltered_annotated_path = pages_dir / f"page_{page_num:03d}_annotated_unfiltered.png"
        layout_detector.annotate(page_path, unfiltered_annotated_path, result.unfiltered_detections)

        # Serialize filter stats if available
        filter_stats_json = None
        if result.filter_stats:
            from dataclasses import asdict
            filter_stats_json = json.dumps(asdict(result.filter_stats))

        # Store page in database with both filtered and unfiltered data
        await metadata_store.add_page(
            document_id=doc_id,
            page_number=page_num,
            image_path=str(page_path),
            annotated_image_path=str(annotated_path),
            layout_json=json.dumps(filtered_dict),
            unfiltered_annotated_image_path=str(unfiltered_annotated_path),
            unfiltered_layout_json=json.dumps(unfiltered_dict),
            filter_stats_json=filter_stats_json,
        )

        all_detections.append(filtered_dict)

    # Step 3: Update document with layout data
    await metadata_store.update_document_layout(
        document_id=doc_id,
        layout_data=json.dumps(all_detections),
        page_count=len(page_images),
    )

    logger.info(f"Layout detection complete: {len(page_images)} pages processed")

    return LayoutDetectionResponse(
        document_id=doc_id,
        pages=len(page_images),
        status="layout_detected",
    )


@router.get("/{doc_id}/pages", response_model=PagesListResponse)
async def get_pages(doc_id: str) -> PagesListResponse:
    """Get list of pages for a document."""
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = await metadata_store.get_pages(doc_id)

    page_infos = []
    for page in pages:
        layout = json.loads(page["layout_json"]) if page["layout_json"] else []
        unfiltered_layout = json.loads(page["unfiltered_layout_json"]) if page.get("unfiltered_layout_json") else []

        # Calculate boxes removed by filter
        boxes_removed = len(unfiltered_layout) - len(layout) if unfiltered_layout else 0

        page_infos.append(PageInfo(
            page_number=page["page_number"],
            has_image=page["image_path"] is not None,
            has_annotated_image=page["annotated_image_path"] is not None,
            has_unfiltered_annotated_image=page.get("unfiltered_annotated_image_path") is not None,
            has_layout=len(layout) > 0,
            detection_count=len(layout),
            unfiltered_detection_count=len(unfiltered_layout),
            boxes_removed_by_filter=max(0, boxes_removed),
        ))

    return PagesListResponse(
        document_id=doc_id,
        total_pages=len(pages),
        pages=page_infos,
    )


@router.get("/{doc_id}/pages/{page_num}/image")
async def get_page_image(doc_id: str, page_num: int) -> FileResponse:
    """Get the original page image."""
    page = await metadata_store.get_page(doc_id, page_num)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    image_path = page["image_path"]
    if not image_path or not Path(image_path).exists():
        raise HTTPException(status_code=404, detail="Page image not found")

    return FileResponse(
        image_path,
        media_type="image/png",
        filename=f"page_{page_num}.png",
    )


@router.get("/{doc_id}/pages/{page_num}/annotated")
async def get_annotated_image(doc_id: str, page_num: int) -> FileResponse:
    """Get the annotated page image with detection boxes (filtered)."""
    page = await metadata_store.get_page(doc_id, page_num)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    image_path = page["annotated_image_path"]
    if not image_path or not Path(image_path).exists():
        raise HTTPException(status_code=404, detail="Annotated image not found")

    return FileResponse(
        image_path,
        media_type="image/png",
        filename=f"page_{page_num}_annotated.png",
    )


@router.get("/{doc_id}/pages/{page_num}/annotated-unfiltered")
async def get_unfiltered_annotated_image(doc_id: str, page_num: int) -> FileResponse:
    """Get the unfiltered annotated page image (before box filtering)."""
    page = await metadata_store.get_page(doc_id, page_num)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    image_path = page.get("unfiltered_annotated_image_path")
    if not image_path or not Path(image_path).exists():
        raise HTTPException(status_code=404, detail="Unfiltered annotated image not found")

    return FileResponse(
        image_path,
        media_type="image/png",
        filename=f"page_{page_num}_annotated_unfiltered.png",
    )


@router.get("/{doc_id}/pages/{page_num}/layout", response_model=PageLayoutResponse)
async def get_page_layout(doc_id: str, page_num: int) -> PageLayoutResponse:
    """Get the layout detection results for a page."""
    page = await metadata_store.get_page(doc_id, page_num)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    layout_json = page["layout_json"]
    detections = json.loads(layout_json) if layout_json else []

    return PageLayoutResponse(
        page_number=page_num,
        detections=[
            DetectionInfo(
                bbox=d["bbox"],
                label=d["label"],
                confidence=d["confidence"],
            )
            for d in detections
        ],
    )


@router.get("/{doc_id}/markdown", response_model=MarkdownResponse)
async def get_markdown(doc_id: str) -> MarkdownResponse:
    """Get the markdown content for a document."""
    result = await metadata_store.get_document_markdown(doc_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")

    return MarkdownResponse(
        document_id=doc_id,
        extracted_markdown=result["extracted_markdown"],
        reviewed_markdown=result["reviewed_markdown"],
        processing_status=result["processing_status"],
    )


@router.put("/{doc_id}/markdown")
async def update_markdown(doc_id: str, request: MarkdownUpdateRequest) -> dict:
    """Save reviewed/edited markdown for a document."""
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    success = await metadata_store.update_reviewed_markdown(doc_id, request.markdown)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update markdown")

    # Update status to reviewed if it was text_extracted
    if doc.processing_status == "text_extracted":
        await metadata_store.update_document_status(doc_id, "reviewed")

    return {"status": "success", "message": "Markdown saved"}


@router.post("/{doc_id}/register")
async def register_document(doc_id: str, file_path: str) -> dict:
    """Register a new document for processing (creates pending entry).

    This is called when a file is uploaded to create an initial
    database entry with pending status.
    """
    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_hash = compute_file_hash(path)

    await metadata_store.create_pending_document(
        document_id=doc_id,
        file_path=str(path.absolute()),
        file_name=path.name,
        file_type=path.suffix.lower().lstrip("."),
        file_hash=file_hash,
    )

    return {
        "status": "success",
        "document_id": doc_id,
        "processing_status": "pending",
    }


class TextExtractionResponse(BaseModel):
    """Text extraction result response."""
    document_id: str
    markdown: str
    status: str


@router.post("/{doc_id}/extract-text", response_model=TextExtractionResponse)
async def extract_text(doc_id: str) -> TextExtractionResponse:
    """Extract text from a document and generate markdown.

    For PDFs: Uses layout detection results to extract text from regions.
    For DOCX: Extracts paragraphs, headings, and tables.
    For PPTX: Extracts slides, text, and tables.
    For CSV/Excel: Generates description with sample data.
    """
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    file_type = doc.file_type.lower()
    logger.info(f"Extracting text from {doc.file_name} (type: {file_type})")

    try:
        if file_type == "pdf":
            # PDF requires layout detection first
            if doc.processing_status != "layout_detected":
                raise HTTPException(
                    status_code=400,
                    detail="PDF requires layout detection before text extraction"
                )
            markdown = await text_extractor.extract_pdf(doc_id)

        elif file_type == "docx":
            markdown = docx_processor.extract(file_path)

        elif file_type == "pptx":
            markdown = pptx_processor.extract(file_path)

        elif file_type in ("csv", "xlsx", "xls"):
            markdown = tabular_processor.extract(file_path)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_type}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(e)}"
        )

    # Store extracted markdown
    await metadata_store.update_document_markdown(doc_id, markdown)
    await metadata_store.update_document_status(doc_id, "text_extracted")

    logger.info(f"Text extraction complete: {len(markdown)} characters")

    return TextExtractionResponse(
        document_id=doc_id,
        markdown=markdown,
        status="text_extracted",
    )


class IndexResponse(BaseModel):
    """Indexing result response."""
    document_id: str
    status: str
    message: str
    chunk_count: int | None = None


@router.post("/{doc_id}/index", response_model=IndexResponse)
async def index_document(doc_id: str) -> IndexResponse:
    """Index the document for search.

    Uses the reviewed markdown if available, otherwise the extracted markdown.
    Runs through the indexing pipeline: chunking, embedding, and indexing.
    """
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get markdown content (prefer reviewed over extracted)
    markdown_data = await metadata_store.get_document_markdown(doc_id)
    if not markdown_data:
        raise HTTPException(status_code=404, detail="Document markdown not found")

    markdown = markdown_data.get("reviewed_markdown") or markdown_data.get("extracted_markdown")
    if not markdown:
        raise HTTPException(
            status_code=400,
            detail="No markdown content to index. Run text extraction first."
        )

    logger.info(f"Indexing document: {doc.file_name}")

    try:
        # Import here to avoid circular imports
        from core.document_processor import document_processor

        # Index using the markdown content
        await document_processor.index_from_markdown(doc_id, markdown)

        # Update status to indexed
        await metadata_store.update_document_status(doc_id, "indexed")

        logger.info(f"Document indexed successfully: {doc.file_name}")

        return IndexResponse(
            document_id=doc_id,
            status="indexed",
            message="Document indexed and searchable",
        )

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Indexing failed: {str(e)}"
        )


class ChunkTabularResponse(BaseModel):
    """Response for tabular file chunking."""
    document_id: str
    chunk_count: int
    status: str
    message: str


@router.post("/{doc_id}/chunk-tabular", response_model=ChunkTabularResponse)
async def chunk_tabular(doc_id: str) -> ChunkTabularResponse:
    """Create chunks for tabular files (CSV, Excel) without markdown.

    This endpoint parses the tabular file and creates chunks directly,
    skipping the layout detection and markdown extraction steps.
    """
    doc = await metadata_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_type = doc.file_type.lower()
    if file_type not in ("csv", "xlsx", "xls"):
        raise HTTPException(
            status_code=400,
            detail=f"This endpoint is only for tabular files (CSV, Excel), got: {file_type}"
        )

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    logger.info(f"Chunking tabular file: {doc.file_name}")

    try:
        # Import here to avoid circular imports
        from parsers import parser_registry
        from indexing.chunker import chunker
        from enrichment.entity_extractor import EnrichmentResult

        # Parse the tabular file
        parser = parser_registry.get_parser(file_path)
        parse_result = parser.parse(file_path)

        # Create basic enrichment placeholder (LLM enrichment comes in next step)
        basic_enrichment = EnrichmentResult(
            document_type="tabular data",
            summary=f"Tabular file: {file_path.name}",
            entities={},
            key_topics=[],
            table_descriptions=[],
        )

        # Create chunks using tabular chunker
        chunks = chunker.chunk_tabular(
            parse_result=parse_result,
            enrichment=basic_enrichment,
            document_id=doc_id,
            file_name=file_path.name,
        )

        # Delete existing chunks for this document
        await metadata_store.delete_chunks_by_document(doc_id)

        # Store chunks in database
        await metadata_store.add_chunks(chunks)

        # Update status to "chunked"
        await metadata_store.update_document_status(doc_id, "chunked")

        logger.info(f"Tabular chunking complete: {len(chunks)} chunks created")

        return ChunkTabularResponse(
            document_id=doc_id,
            chunk_count=len(chunks),
            status="chunked",
            message=f"Created {len(chunks)} chunks from tabular data",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tabular chunking failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Tabular chunking failed: {str(e)}"
        )
