"""File-browser related schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FolderItem(BaseModel):
    """Item in a folder (file or subfolder)."""

    name: str
    type: Literal["file", "folder"]
    path: str  # Relative path from documents root
    size: int | None = None
    file_type: str | None = None
    is_supported: bool = False
    is_indexed: bool = False
    modified_at: datetime
    # Processing workflow fields
    doc_id: str | None = None
    processing_status: str | None = None


class FolderContents(BaseModel):
    """Contents of a folder."""

    current_path: str
    parent_path: str | None
    items: list[FolderItem]


class CreateFolderRequest(BaseModel):
    """Request to create a new folder."""

    parent_path: str = Field(default="", description="Parent folder path (empty for root)")
    name: str = Field(..., min_length=1, max_length=255, description="New folder name")


class CreateFolderResponse(BaseModel):
    """Response after creating a folder."""

    path: str
    message: str


class UploadResponse(BaseModel):
    """Response after uploading files."""

    uploaded: list[str]
    failed: list[str]
    message: str


class FilePreview(BaseModel):
    """File preview content."""

    name: str
    path: str
    file_type: str
    size: int
    content_type: Literal["text", "table", "binary"]
    content: str | None = None
    is_indexed: bool = False
    indexed_summary: str | None = None
    # Processing workflow fields
    doc_id: str | None = None
    processing_status: str | None = None
    page_count: int | None = None


class DeleteResponse(BaseModel):
    """Response after deleting a file."""

    path: str
    was_indexed: bool
    message: str

