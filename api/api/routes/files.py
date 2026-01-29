"""File management endpoints for browsing, uploading, and managing files."""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse

from config.settings import settings
from core.utils import generate_document_id, compute_file_hash
from parsers import parser_registry
from indexing.metadata_store import metadata_store
from indexing.keyword_index import keyword_index
from indexing.multi_vector_index import multi_vector_index
from api.schemas import (
    FolderItem,
    FolderContents,
    CreateFolderRequest,
    CreateFolderResponse,
    UploadResponse,
    FilePreview,
    DeleteResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])

# Supported file extensions for upload
SUPPORTED_EXTENSIONS = {"pdf", "docx", "xlsx", "xls", "csv", "pptx"}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB


def _validate_path(path: str) -> Path:
    """Validate and resolve a path, ensuring it's within the watch folder."""
    # Normalize the path
    if path in ("", ".", "/"):
        return settings.watch_folder

    # Remove leading slashes and normalize separators
    path = path.lstrip("/\\")
    # Replace forward slashes with OS separator for Windows compatibility
    path = path.replace("/", os.sep)

    # Resolve the full path
    full_path = (settings.watch_folder / path).resolve()

    # Security check: ensure path is within watch folder
    try:
        full_path.relative_to(settings.watch_folder.resolve())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid path: path must be within documents folder"
        )

    return full_path


def _get_relative_path(full_path: Path) -> str:
    """Get the relative path from watch folder (always uses forward slashes)."""
    try:
        rel = full_path.resolve().relative_to(settings.watch_folder.resolve())
        # Use forward slashes for cross-platform compatibility in URLs
        return rel.as_posix()
    except ValueError:
        return ""


def _get_file_type(file_path: Path) -> str:
    """Get the file type from extension."""
    return file_path.suffix.lower().lstrip(".")


@router.get("/browse", response_model=FolderContents)
@router.get("/browse/{path:path}", response_model=FolderContents)
async def browse_folder(path: str = "") -> FolderContents:
    """
    Browse folder contents.

    Returns a list of files and subfolders in the specified path.
    """
    folder_path = _validate_path(path)

    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Folder not found")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a folder")

    items: List[FolderItem] = []

    try:
        for entry in sorted(folder_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = entry.stat()
                rel_path = _get_relative_path(entry)

                if entry.is_dir():
                    items.append(FolderItem(
                        name=entry.name,
                        type="folder",
                        path=rel_path,
                        size=None,
                        file_type=None,
                        is_supported=False,
                        is_indexed=False,
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                    ))
                else:
                    file_type = _get_file_type(entry)
                    is_supported = parser_registry.is_supported(entry)

                    # Get document record if exists
                    doc_id = generate_document_id(entry)
                    doc = await metadata_store.get_document(doc_id)
                    is_indexed = doc is not None and doc.processing_status == "indexed"
                    processing_status = doc.processing_status if doc else None

                    items.append(FolderItem(
                        name=entry.name,
                        type="file",
                        path=rel_path,
                        size=stat.st_size,
                        file_type=file_type,
                        is_supported=is_supported,
                        is_indexed=is_indexed,
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                        doc_id=doc_id if is_supported else None,
                        processing_status=processing_status,
                    ))
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot access {entry}: {e}")
                continue
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Calculate parent path
    current_rel = _get_relative_path(folder_path)
    if current_rel and current_rel != ".":
        parent_path = str(Path(current_rel).parent)
        if parent_path == ".":
            parent_path = ""
    else:
        parent_path = None

    return FolderContents(
        current_path=current_rel if current_rel != "." else "",
        parent_path=parent_path,
        items=items,
    )


@router.post("/folder", response_model=CreateFolderResponse)
async def create_folder(request: CreateFolderRequest) -> CreateFolderResponse:
    """
    Create a new folder.

    Creates a new subfolder within the documents directory.
    """
    # Validate folder name
    invalid_chars = '<>:"/\\|?*'
    if any(c in request.name for c in invalid_chars):
        raise HTTPException(
            status_code=400,
            detail=f"Folder name cannot contain: {invalid_chars}"
        )

    # Get parent path
    parent_path = _validate_path(request.parent_path)

    if not parent_path.exists():
        raise HTTPException(status_code=404, detail="Parent folder not found")

    if not parent_path.is_dir():
        raise HTTPException(status_code=400, detail="Parent path is not a folder")

    # Create new folder path
    new_folder = parent_path / request.name

    if new_folder.exists():
        raise HTTPException(status_code=409, detail="Folder already exists")

    try:
        new_folder.mkdir(parents=False, exist_ok=False)
        rel_path = _get_relative_path(new_folder)
        logger.info(f"Created folder: {rel_path}")

        return CreateFolderResponse(
            path=rel_path,
            message=f"Folder '{request.name}' created successfully"
        )
    except OSError as e:
        logger.error(f"Failed to create folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    target_path: str = Form(default=""),
) -> UploadResponse:
    """
    Upload files to the documents folder.

    Files will be automatically indexed by the file watcher.
    """
    # Validate target path
    target_folder = _validate_path(target_path)

    if not target_folder.exists():
        raise HTTPException(status_code=404, detail="Target folder not found")

    if not target_folder.is_dir():
        raise HTTPException(status_code=400, detail="Target path is not a folder")

    uploaded = []
    failed = []

    for file in files:
        try:
            # Validate file extension
            file_ext = Path(file.filename).suffix.lower().lstrip(".")
            if file_ext not in SUPPORTED_EXTENSIONS:
                failed.append(f"{file.filename}: Unsupported file type")
                continue

            # Validate file name
            if not file.filename or ".." in file.filename:
                failed.append(f"{file.filename}: Invalid filename")
                continue

            # Create safe filename
            safe_name = Path(file.filename).name
            dest_path = target_folder / safe_name

            # Check file size (read in chunks)
            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE:
                failed.append(f"{file.filename}: File too large (max {MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
                continue

            # Write file
            with open(dest_path, "wb") as f:
                f.write(content)

            rel_path = _get_relative_path(dest_path)
            uploaded.append(rel_path)
            logger.info(f"Uploaded file: {rel_path}")

            # Register document in pending status for manual processing
            if parser_registry.is_supported(dest_path):
                doc_id = generate_document_id(dest_path)
                file_hash = compute_file_hash(dest_path)
                await metadata_store.create_pending_document(
                    document_id=doc_id,
                    file_path=str(dest_path.absolute()),
                    file_name=dest_path.name,
                    file_type=_get_file_type(dest_path),
                    file_hash=file_hash,
                )
                logger.info(f"Registered document for processing: {doc_id}")

        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            failed.append(f"{file.filename}: {str(e)}")

    message = f"Uploaded {len(uploaded)} file(s)"
    if failed:
        message += f", {len(failed)} failed"

    return UploadResponse(
        uploaded=uploaded,
        failed=failed,
        message=message,
    )


@router.get("/download/{path:path}")
async def download_file(path: str):
    """
    Download a file.

    Returns the file as a downloadable attachment.
    """
    file_path = _validate_path(path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/preview/{path:path}", response_model=FilePreview)
async def preview_file(path: str) -> FilePreview:
    """
    Get file preview content.

    Returns file content for preview (text for documents, table data for spreadsheets).
    """
    file_path = _validate_path(path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    stat = file_path.stat()
    file_type = _get_file_type(file_path)

    # Get document record if exists
    doc_id = generate_document_id(file_path)
    doc = await metadata_store.get_document(doc_id)
    is_indexed = doc is not None and doc.processing_status == "indexed"
    processing_status = doc.processing_status if doc else None
    page_count = doc.page_count if doc else None

    # Get indexed summary if available
    indexed_summary = None
    if doc and doc.summary:
        indexed_summary = doc.summary

    # Determine content type and extract preview
    content = None
    content_type = "binary"

    if file_type in ("csv", "xlsx", "xls"):
        content_type = "table"
        try:
            import pandas as pd
            if file_type == "csv":
                df = pd.read_csv(file_path, nrows=50)
            else:
                df = pd.read_excel(file_path, nrows=50)
            content = df.to_json(orient="split")
        except Exception as e:
            logger.warning(f"Failed to preview table: {e}")
            content = None

    elif file_type == "pdf":
        content_type = "text"
        try:
            # Try to get text from indexed content
            if is_indexed:
                doc = await metadata_store.get_document_by_path(str(file_path.absolute()))
                if doc:
                    chunks = await metadata_store.get_chunks_by_document(doc.id)
                    if chunks:
                        content = "\n\n".join(c.text[:500] for c in chunks[:5])
        except Exception as e:
            logger.warning(f"Failed to preview PDF: {e}")

    elif file_type in ("docx", "pptx"):
        content_type = "text"
        try:
            if is_indexed:
                doc = await metadata_store.get_document_by_path(str(file_path.absolute()))
                if doc:
                    chunks = await metadata_store.get_chunks_by_document(doc.id)
                    if chunks:
                        content = "\n\n".join(c.text[:500] for c in chunks[:5])
        except Exception as e:
            logger.warning(f"Failed to preview document: {e}")

    return FilePreview(
        name=file_path.name,
        path=_get_relative_path(file_path),
        file_type=file_type,
        size=stat.st_size,
        content_type=content_type,
        content=content,
        is_indexed=is_indexed,
        indexed_summary=indexed_summary,
        doc_id=doc_id if parser_registry.is_supported(file_path) else None,
        processing_status=processing_status,
        page_count=page_count,
    )


@router.delete("/delete/{path:path}", response_model=DeleteResponse)
async def delete_file(path: str) -> DeleteResponse:
    """
    Delete a file.

    Removes the file and its index/processing entries.
    """
    file_path = _validate_path(path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    rel_path = _get_relative_path(file_path)

    # Get document record if exists
    doc_id = generate_document_id(file_path)
    doc = await metadata_store.get_document(doc_id)
    was_indexed = doc is not None and doc.processing_status == "indexed"

    try:
        # Clean up document data if exists
        if doc:
            # Get chunks BEFORE deleting from database
            chunks = await metadata_store.get_chunks_by_document(doc_id)
            chunk_ids = [c.id for c in chunks]

            # Clean up vector indices
            if chunk_ids:
                keyword_index.remove(chunk_ids)
                for chunk_id in chunk_ids:
                    multi_vector_index.remove_chunk(chunk_id)
                logger.info(f"Removed {len(chunk_ids)} chunks from indices")

            # Delete page records
            await metadata_store.delete_pages(doc_id)

            # Delete chunks from database
            await metadata_store.delete_chunks_by_document(doc_id)

            # Delete document record
            await metadata_store.delete_document(doc_id)

            # Clean up processing directory
            processing_dir = settings.data_folder / "processing" / doc_id
            if processing_dir.exists():
                import shutil
                shutil.rmtree(processing_dir)

            logger.info(f"Removed document data: {doc_id}")

        # Delete the file
        file_path.unlink()
        logger.info(f"Deleted file: {rel_path}")

        return DeleteResponse(
            path=rel_path,
            was_indexed=was_indexed,
            message=f"File '{file_path.name}' deleted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.delete("/folder/{path:path}", response_model=DeleteResponse)
async def delete_folder(path: str, force: bool = Query(default=False)) -> DeleteResponse:
    """
    Delete a folder.

    By default, only empty folders can be deleted. Use force=true to delete non-empty folders.
    """
    folder_path = _validate_path(path)

    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Folder not found")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a folder")

    # Prevent deleting root
    if folder_path.resolve() == settings.watch_folder.resolve():
        raise HTTPException(status_code=400, detail="Cannot delete root documents folder")

    rel_path = _get_relative_path(folder_path)

    # Check if folder is empty
    contents = list(folder_path.iterdir())
    if contents and not force:
        raise HTTPException(
            status_code=400,
            detail=f"Folder is not empty ({len(contents)} items). Use force=true to delete."
        )

    try:
        if contents:
            # Clean up document data for all files in folder
            for item in folder_path.rglob("*"):
                if item.is_file() and parser_registry.is_supported(item):
                    doc_id = generate_document_id(item)
                    doc = await metadata_store.get_document(doc_id)
                    if doc:
                        await metadata_store.delete_pages(doc_id)
                        await metadata_store.delete_chunks_by_document(doc_id)
                        await metadata_store.delete_document(doc_id)
                        # Clean up processing directory
                        processing_dir = settings.data_folder / "processing" / doc_id
                        if processing_dir.exists():
                            shutil.rmtree(processing_dir)
            shutil.rmtree(folder_path)
        else:
            folder_path.rmdir()

        logger.info(f"Deleted folder: {rel_path}")

        return DeleteResponse(
            path=rel_path,
            was_indexed=False,
            message=f"Folder '{folder_path.name}' deleted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to delete folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete folder: {str(e)}")
