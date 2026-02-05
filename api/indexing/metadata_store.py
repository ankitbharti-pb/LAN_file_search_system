"""SQLite-based metadata store for documents, entities, and chunks."""

import json
import aiosqlite
from pathlib import Path
from typing import Any
from datetime import datetime

from models.document import Document, DocumentSummary
from models.chunk import Chunk, ChunkMetadata, ChunkQuestion, VectorEmbedding
from config.settings import settings


class MetadataStore:
    """Async SQLite store for document metadata, entities, and chunks."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.database_path
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        """Get or create a persistent database connection for reads."""
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
        return self._db

    async def close(self) -> None:
        """Close the persistent database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def initialize(self) -> None:
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")

            # Documents table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    detected_doc_type TEXT DEFAULT 'unknown',
                    summary TEXT DEFAULT '',
                    entities TEXT DEFAULT '{}',
                    key_topics TEXT DEFAULT '[]',
                    table_descriptions TEXT DEFAULT '[]',
                    indexed_at TEXT NOT NULL,
                    sheet_names TEXT,
                    column_schema TEXT,
                    row_count INTEGER,
                    date_range TEXT,
                    processing_status TEXT DEFAULT 'pending',
                    layout_data TEXT,
                    extracted_markdown TEXT,
                    reviewed_markdown TEXT,
                    page_count INTEGER
                )
            """)

            # Document entities table (for efficient filtering)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS document_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    entity_value TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)

            # Chunks table (with hierarchical and semantic chunking support)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    contextualized_text TEXT NOT NULL,
                    content_type TEXT DEFAULT 'paragraph',
                    page INTEGER,
                    sheet_name TEXT,
                    heading_path TEXT,
                    entities TEXT DEFAULT '{}',
                    chunk_index INTEGER DEFAULT 0,
                    parent_chunk_id TEXT,
                    hierarchy_level INTEGER DEFAULT 0,
                    bbox TEXT,
                    layout_label TEXT,
                    is_semantic_boundary INTEGER DEFAULT 0,
                    semantic_similarity_prev REAL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(id) ON DELETE SET NULL
                )
            """)

            # Chunk metadata table (LLM-enriched metadata)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chunk_metadata (
                    chunk_id TEXT PRIMARY KEY,
                    title TEXT,
                    summary TEXT,
                    keywords TEXT,
                    entities TEXT,
                    category TEXT,
                    contextual_description TEXT,
                    temporal_context TEXT,
                    enriched_at TEXT,
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                )
            """)

            # Chunk questions table (hypothetical questions for multi-vector retrieval)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS chunk_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    vector_id TEXT,
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                )
            """)

            # Vector embeddings table (tracks multi-vector embeddings)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vector_embeddings (
                    id TEXT PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    vector_type TEXT NOT NULL,
                    source_text TEXT,
                    question_id INTEGER,
                    FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
                )
            """)

            # Document pages table (for PDF layout detection)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS document_pages (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    image_path TEXT,
                    annotated_image_path TEXT,
                    unfiltered_annotated_image_path TEXT,
                    layout_json TEXT,
                    unfiltered_layout_json TEXT,
                    filter_stats_json TEXT,
                    extracted_text TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    UNIQUE(document_id, page_number)
                )
            """)

            # Migrate existing database: add new columns if they don't exist
            # SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we check first
            cursor = await db.execute("PRAGMA table_info(documents)")
            existing_columns = {row[1] for row in await cursor.fetchall()}

            new_columns = [
                ("processing_status", "TEXT DEFAULT 'pending'"),
                ("layout_data", "TEXT"),
                ("extracted_markdown", "TEXT"),
                ("reviewed_markdown", "TEXT"),
                ("page_count", "INTEGER"),
            ]

            for col_name, col_def in new_columns:
                if col_name not in existing_columns:
                    await db.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_def}")

            # Migrate chunks table: add new columns for hierarchical chunking
            cursor = await db.execute("PRAGMA table_info(chunks)")
            existing_chunk_columns = {row[1] for row in await cursor.fetchall()}

            new_chunk_columns = [
                ("parent_chunk_id", "TEXT"),
                ("hierarchy_level", "INTEGER DEFAULT 0"),
                ("bbox", "TEXT"),
                ("layout_label", "TEXT"),
                ("is_semantic_boundary", "INTEGER DEFAULT 0"),
                ("semantic_similarity_prev", "REAL"),
            ]

            for col_name, col_def in new_chunk_columns:
                if col_name not in existing_chunk_columns:
                    await db.execute(f"ALTER TABLE chunks ADD COLUMN {col_name} {col_def}")

            # Migrate chunk_metadata table: add temporal_context column
            cursor = await db.execute("PRAGMA table_info(chunk_metadata)")
            existing_meta_columns = {row[1] for row in await cursor.fetchall()}

            if "temporal_context" not in existing_meta_columns:
                await db.execute("ALTER TABLE chunk_metadata ADD COLUMN temporal_context TEXT")

            # Migrate document_pages table: add new columns for filter comparison
            cursor = await db.execute("PRAGMA table_info(document_pages)")
            existing_page_columns = {row[1] for row in await cursor.fetchall()}

            new_page_columns = [
                ("unfiltered_annotated_image_path", "TEXT"),
                ("unfiltered_layout_json", "TEXT"),
                ("filter_stats_json", "TEXT"),
            ]

            for col_name, col_def in new_page_columns:
                if col_name not in existing_page_columns:
                    await db.execute(f"ALTER TABLE document_pages ADD COLUMN {col_name} {col_def}")

            # Create indexes
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_doc_file_path ON documents(file_path)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_doc_type ON documents(detected_doc_type)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_entity_key ON document_entities(entity_key)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(document_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(processing_status)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_pages_doc_id ON document_pages(document_id)"
            )

            # New indexes for hierarchical chunking and multi-vector retrieval
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_parent ON chunks(parent_chunk_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunks_hierarchy ON chunks(document_id, hierarchy_level)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_meta_id ON chunk_metadata(chunk_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_questions_chunk ON chunk_questions(chunk_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_vectors_chunk ON vector_embeddings(chunk_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_vectors_type ON vector_embeddings(vector_type)"
            )

            await db.commit()

    async def add_document(self, document: Document) -> None:
        """Insert or update a document."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO documents
                (id, file_path, file_name, file_type, file_hash, detected_doc_type,
                 summary, entities, key_topics, table_descriptions, indexed_at,
                 sheet_names, column_schema, row_count, date_range)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.file_path,
                    document.file_name,
                    document.file_type,
                    document.file_hash,
                    document.detected_doc_type,
                    document.summary,
                    json.dumps(document.entities),
                    json.dumps(document.key_topics),
                    json.dumps(document.table_descriptions),
                    document.indexed_at.isoformat(),
                    json.dumps(document.sheet_names) if document.sheet_names else None,
                    json.dumps(document.column_schema) if document.column_schema else None,
                    document.row_count,
                    document.date_range,
                ),
            )

            # Update entities table
            await db.execute(
                "DELETE FROM document_entities WHERE document_id = ?", (document.id,)
            )
            for key, value in document.entities.items():
                await db.execute(
                    """
                    INSERT INTO document_entities (document_id, entity_key, entity_value)
                    VALUES (?, ?, ?)
                    """,
                    (document.id, key, str(value)),
                )

            await db.commit()

    async def get_document(self, document_id: str) -> Document | None:
        """Get a document by ID."""
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM documents WHERE id = ?", (document_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_document(row)

    async def get_document_by_path(self, file_path: str) -> Document | None:
        """Get a document by file path."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM documents WHERE file_path = ?", (file_path,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_document(row)

    async def get_all_documents(
        self, skip: int = 0, limit: int = 100
    ) -> list[DocumentSummary]:
        """Get all documents with pagination."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, file_name, file_type, detected_doc_type, summary, indexed_at
                FROM documents
                ORDER BY indexed_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, skip),
            )
            rows = await cursor.fetchall()

            return [
                DocumentSummary(
                    id=row["id"],
                    file_name=row["file_name"],
                    file_type=row["file_type"],
                    detected_doc_type=row["detected_doc_type"],
                    summary=row["summary"],
                    indexed_at=datetime.fromisoformat(row["indexed_at"]),
                )
                for row in rows
            ]

    async def get_documents_by_ids(self, document_ids: list[str]) -> list[Document]:
        """Batch fetch documents by IDs."""
        if not document_ids:
            return []

        placeholders = ",".join("?" * len(document_ids))
        db = await self._get_db()
        cursor = await db.execute(
            f"SELECT * FROM documents WHERE id IN ({placeholders})",
            document_ids,
        )
        rows = await cursor.fetchall()

        return [self._row_to_document(row) for row in rows]

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM documents WHERE id = ?", (document_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_document_by_path(self, file_path: str) -> bool:
        """Delete a document by file path."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM documents WHERE file_path = ?", (file_path,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def clear_all(self) -> None:
        """Clear all data from the database (for full reindex)."""
        async with aiosqlite.connect(self.db_path) as db:
            # Delete in order to respect foreign key constraints
            await db.execute("DELETE FROM vector_embeddings")
            await db.execute("DELETE FROM chunk_questions")
            await db.execute("DELETE FROM chunk_metadata")
            await db.execute("DELETE FROM chunks")
            await db.execute("DELETE FROM document_entities")
            await db.execute("DELETE FROM document_pages")
            await db.execute("DELETE FROM documents")
            await db.commit()

    async def add_chunks(self, chunks: list[Chunk]) -> None:
        """Insert chunks for a document."""
        if not chunks:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT OR REPLACE INTO chunks
                (id, document_id, text, contextualized_text, content_type,
                 page, sheet_name, heading_path, entities, chunk_index,
                 parent_chunk_id, hierarchy_level, bbox, layout_label,
                 is_semantic_boundary, semantic_similarity_prev)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.text,
                        chunk.contextualized_text,
                        chunk.content_type,
                        chunk.page,
                        chunk.sheet_name,
                        chunk.heading_path,
                        json.dumps(chunk.entities),
                        chunk.chunk_index,
                        chunk.parent_chunk_id,
                        chunk.hierarchy_level,
                        json.dumps(chunk.bbox) if chunk.bbox else None,
                        chunk.layout_label,
                        1 if chunk.is_semantic_boundary else 0,
                        chunk.semantic_similarity_prev,
                    )
                    for chunk in chunks
                ],
            )
            await db.commit()

    async def get_chunks_by_document(self, document_id: str) -> list[Chunk]:
        """Get all chunks for a document."""
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        )
        rows = await cursor.fetchall()

        return [self._row_to_chunk(row) for row in rows]

    async def get_chunk(self, chunk_id: str) -> Chunk | None:
        """Get a chunk by ID."""
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_chunk(row)

    async def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[Chunk]:
        """Get multiple chunks by their IDs."""
        if not chunk_ids:
            return []

        placeholders = ",".join("?" * len(chunk_ids))
        db = await self._get_db()
        cursor = await db.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})", chunk_ids
        )
        rows = await cursor.fetchall()

        return [self._row_to_chunk(row) for row in rows]

    async def delete_chunks_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM chunks WHERE document_id = ?", (document_id,)
            )
            await db.commit()
            return cursor.rowcount

    async def filter_documents_by_type(self, doc_type: str) -> list[str]:
        """Get document IDs filtered by detected type."""
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT id FROM documents WHERE detected_doc_type LIKE ?",
            (f"%{doc_type}%",),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def filter_documents_by_entity(
        self, entity_key: str, entity_value: str | None = None
    ) -> list[str]:
        """Get document IDs filtered by entity key/value."""
        db = await self._get_db()
        if entity_value:
            cursor = await db.execute(
                """
                SELECT DISTINCT document_id FROM document_entities
                WHERE entity_key = ? AND entity_value LIKE ?
                """,
                (entity_key, f"%{entity_value}%"),
            )
        else:
            cursor = await db.execute(
                "SELECT DISTINCT document_id FROM document_entities WHERE entity_key = ?",
                (entity_key,),
            )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_statistics(self) -> dict[str, Any]:
        """Get index statistics."""
        async with aiosqlite.connect(self.db_path) as db:
            # Total documents
            cursor = await db.execute("SELECT COUNT(*) FROM documents")
            total_docs = (await cursor.fetchone())[0]

            # Total chunks
            cursor = await db.execute("SELECT COUNT(*) FROM chunks")
            total_chunks = (await cursor.fetchone())[0]

            # Documents by type
            cursor = await db.execute(
                "SELECT detected_doc_type, COUNT(*) FROM documents GROUP BY detected_doc_type"
            )
            by_type = {row[0]: row[1] for row in await cursor.fetchall()}

            # Documents by file type
            cursor = await db.execute(
                "SELECT file_type, COUNT(*) FROM documents GROUP BY file_type"
            )
            by_file_type = {row[0]: row[1] for row in await cursor.fetchall()}

            return {
                "total_documents": total_docs,
                "total_chunks": total_chunks,
                "documents_by_detected_type": by_type,
                "documents_by_file_type": by_file_type,
            }

    # ============== Document Processing Methods ==============

    async def update_document_status(self, document_id: str, status: str) -> bool:
        """Update the processing status of a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE documents SET processing_status = ? WHERE id = ?",
                (status, document_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_document_markdown(
        self, document_id: str, extracted_markdown: str
    ) -> bool:
        """Update the extracted markdown for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE documents SET extracted_markdown = ? WHERE id = ?",
                (extracted_markdown, document_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_reviewed_markdown(
        self, document_id: str, reviewed_markdown: str
    ) -> bool:
        """Update the reviewed markdown for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE documents SET reviewed_markdown = ? WHERE id = ?",
                (reviewed_markdown, document_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def update_document_layout(
        self, document_id: str, layout_data: str, page_count: int
    ) -> bool:
        """Update the layout data and page count for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """UPDATE documents
                   SET layout_data = ?, page_count = ?, processing_status = 'layout_detected'
                   WHERE id = ?""",
                (layout_data, page_count, document_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_document_markdown(self, document_id: str) -> dict | None:
        """Get the markdown content for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT extracted_markdown, reviewed_markdown, processing_status FROM documents WHERE id = ?",
                (document_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "extracted_markdown": row[0],
                "reviewed_markdown": row[1],
                "processing_status": row[2],
            }

    async def update_document_enrichment(
        self,
        document_id: str,
        detected_doc_type: str,
        summary: str,
        entities: dict,
        key_topics: list[str],
        table_descriptions: list[str],
    ) -> bool:
        """Update a document with LLM enrichment data after indexing."""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """UPDATE documents
                   SET detected_doc_type = ?,
                       summary = ?,
                       entities = ?,
                       key_topics = ?,
                       table_descriptions = ?,
                       indexed_at = CURRENT_TIMESTAMP,
                       processing_status = 'indexed'
                   WHERE id = ?""",
                (
                    detected_doc_type,
                    summary,
                    json.dumps(entities),
                    json.dumps(key_topics),
                    json.dumps(table_descriptions),
                    document_id,
                ),
            )
            await db.commit()
            return cursor.rowcount > 0

    # ============== Document Pages Methods ==============

    async def add_page(
        self,
        document_id: str,
        page_number: int,
        image_path: str,
        annotated_image_path: str | None,
        layout_json: str,
        unfiltered_annotated_image_path: str | None = None,
        unfiltered_layout_json: str | None = None,
        filter_stats_json: str | None = None,
    ) -> None:
        """Add or update a page for a document."""
        page_id = f"{document_id}_page_{page_number}"
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO document_pages
                   (id, document_id, page_number, image_path, annotated_image_path,
                    unfiltered_annotated_image_path, layout_json, unfiltered_layout_json,
                    filter_stats_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (page_id, document_id, page_number, image_path, annotated_image_path,
                 unfiltered_annotated_image_path, layout_json, unfiltered_layout_json,
                 filter_stats_json),
            )
            await db.commit()

    async def update_page_text(
        self, document_id: str, page_number: int, extracted_text: str
    ) -> bool:
        """Update the extracted text for a page."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """UPDATE document_pages
                   SET extracted_text = ?
                   WHERE document_id = ? AND page_number = ?""",
                (extracted_text, document_id, page_number),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_pages(self, document_id: str) -> list[dict]:
        """Get all pages for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM document_pages
                   WHERE document_id = ?
                   ORDER BY page_number""",
                (document_id,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "page_number": row["page_number"],
                    "image_path": row["image_path"],
                    "annotated_image_path": row["annotated_image_path"],
                    "unfiltered_annotated_image_path": row["unfiltered_annotated_image_path"],
                    "layout_json": row["layout_json"],
                    "unfiltered_layout_json": row["unfiltered_layout_json"],
                    "filter_stats_json": row["filter_stats_json"],
                    "extracted_text": row["extracted_text"],
                }
                for row in rows
            ]

    async def get_page(self, document_id: str, page_number: int) -> dict | None:
        """Get a specific page for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """SELECT * FROM document_pages
                   WHERE document_id = ? AND page_number = ?""",
                (document_id, page_number),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "document_id": row["document_id"],
                "page_number": row["page_number"],
                "image_path": row["image_path"],
                "annotated_image_path": row["annotated_image_path"],
                "unfiltered_annotated_image_path": row["unfiltered_annotated_image_path"],
                "layout_json": row["layout_json"],
                "unfiltered_layout_json": row["unfiltered_layout_json"],
                "filter_stats_json": row["filter_stats_json"],
                "extracted_text": row["extracted_text"],
            }

    async def delete_pages(self, document_id: str) -> int:
        """Delete all pages for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM document_pages WHERE document_id = ?",
                (document_id,),
            )
            await db.commit()
            return cursor.rowcount

    async def create_pending_document(
        self,
        document_id: str,
        file_path: str,
        file_name: str,
        file_type: str,
        file_hash: str,
    ) -> None:
        """Create a document in pending status (for manual processing workflow)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR REPLACE INTO documents
                   (id, file_path, file_name, file_type, file_hash, processing_status, indexed_at)
                   VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
                (
                    document_id,
                    file_path,
                    file_name,
                    file_type,
                    file_hash,
                    datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()

    def _row_to_document(self, row: aiosqlite.Row) -> Document:
        """Convert a database row to a Document model."""
        return Document(
            id=row["id"],
            file_path=row["file_path"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            file_hash=row["file_hash"],
            detected_doc_type=row["detected_doc_type"] or "unknown",
            summary=row["summary"] or "",
            entities=json.loads(row["entities"]) if row["entities"] else {},
            key_topics=json.loads(row["key_topics"]) if row["key_topics"] else [],
            table_descriptions=json.loads(row["table_descriptions"]) if row["table_descriptions"] else [],
            indexed_at=datetime.fromisoformat(row["indexed_at"]),
            sheet_names=json.loads(row["sheet_names"]) if row["sheet_names"] else None,
            column_schema=json.loads(row["column_schema"]) if row["column_schema"] else None,
            row_count=row["row_count"],
            date_range=row["date_range"],
            processing_status=row["processing_status"] if "processing_status" in row.keys() else "pending",
            layout_data=row["layout_data"] if "layout_data" in row.keys() else None,
            extracted_markdown=row["extracted_markdown"] if "extracted_markdown" in row.keys() else None,
            reviewed_markdown=row["reviewed_markdown"] if "reviewed_markdown" in row.keys() else None,
            page_count=row["page_count"] if "page_count" in row.keys() else None,
        )

    def _row_to_chunk(self, row: aiosqlite.Row) -> Chunk:
        """Convert a database row to a Chunk model."""
        row_keys = row.keys()
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            text=row["text"],
            contextualized_text=row["contextualized_text"],
            content_type=row["content_type"],
            page=row["page"],
            sheet_name=row["sheet_name"],
            heading_path=row["heading_path"],
            entities=json.loads(row["entities"]),
            chunk_index=row["chunk_index"],
            parent_chunk_id=row["parent_chunk_id"] if "parent_chunk_id" in row_keys else None,
            hierarchy_level=row["hierarchy_level"] if "hierarchy_level" in row_keys else 0,
            bbox=json.loads(row["bbox"]) if "bbox" in row_keys and row["bbox"] else None,
            layout_label=row["layout_label"] if "layout_label" in row_keys else None,
            is_semantic_boundary=bool(row["is_semantic_boundary"]) if "is_semantic_boundary" in row_keys else False,
            semantic_similarity_prev=row["semantic_similarity_prev"] if "semantic_similarity_prev" in row_keys else None,
        )

    def _row_to_chunk_metadata(self, row: aiosqlite.Row) -> ChunkMetadata:
        """Convert a database row to a ChunkMetadata model."""
        row_keys = row.keys()
        return ChunkMetadata(
            chunk_id=row["chunk_id"],
            title=row["title"],
            summary=row["summary"],
            keywords=json.loads(row["keywords"]) if row["keywords"] else [],
            entities=json.loads(row["entities"]) if row["entities"] else {},
            category=row["category"],
            contextual_description=row["contextual_description"],
            temporal_context=row["temporal_context"] if "temporal_context" in row_keys else None,
            enriched_at=datetime.fromisoformat(row["enriched_at"]) if row["enriched_at"] else None,
        )

    # ============== Chunk Metadata Methods ==============

    async def add_chunk_metadata(self, metadata: ChunkMetadata) -> None:
        """Insert or update chunk metadata."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO chunk_metadata
                (chunk_id, title, summary, keywords, entities, category, contextual_description, temporal_context, enriched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.chunk_id,
                    metadata.title,
                    metadata.summary,
                    json.dumps(metadata.keywords),
                    json.dumps(metadata.entities),
                    metadata.category,
                    metadata.contextual_description,
                    metadata.temporal_context,
                    metadata.enriched_at.isoformat() if metadata.enriched_at else datetime.utcnow().isoformat(),
                ),
            )
            await db.commit()

    async def add_chunk_metadata_batch(self, metadata_list: list[ChunkMetadata]) -> None:
        """Insert multiple chunk metadata records."""
        if not metadata_list:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT OR REPLACE INTO chunk_metadata
                (chunk_id, title, summary, keywords, entities, category, contextual_description, temporal_context, enriched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        m.chunk_id,
                        m.title,
                        m.summary,
                        json.dumps(m.keywords),
                        json.dumps(m.entities),
                        m.category,
                        m.contextual_description,
                        m.temporal_context,
                        m.enriched_at.isoformat() if m.enriched_at else datetime.utcnow().isoformat(),
                    )
                    for m in metadata_list
                ],
            )
            await db.commit()

    async def get_chunk_metadata(self, chunk_id: str) -> ChunkMetadata | None:
        """Get metadata for a chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM chunk_metadata WHERE chunk_id = ?", (chunk_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return self._row_to_chunk_metadata(row)

    async def get_chunk_metadata_batch(self, chunk_ids: list[str]) -> dict[str, ChunkMetadata]:
        """Batch fetch chunk metadata by chunk IDs. Returns dict mapping chunk_id -> ChunkMetadata."""
        if not chunk_ids:
            return {}

        placeholders = ",".join("?" * len(chunk_ids))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"SELECT * FROM chunk_metadata WHERE chunk_id IN ({placeholders})",
                chunk_ids,
            )
            rows = await cursor.fetchall()
            return {row["chunk_id"]: self._row_to_chunk_metadata(row) for row in rows}

    async def get_chunk_with_metadata(self, chunk_id: str) -> dict | None:
        """Get chunk with its enriched metadata."""
        chunk = await self.get_chunk(chunk_id)
        if not chunk:
            return None

        metadata = await self.get_chunk_metadata(chunk_id)
        questions = await self.get_chunk_questions(chunk_id)

        return {
            "chunk": chunk,
            "metadata": metadata,
            "questions": questions,
        }

    async def delete_chunk_metadata(self, chunk_id: str) -> bool:
        """Delete metadata for a chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM chunk_metadata WHERE chunk_id = ?", (chunk_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    # ============== Chunk Questions Methods ==============

    async def add_chunk_questions(self, chunk_id: str, questions: list[ChunkQuestion]) -> None:
        """Insert questions for a chunk."""
        if not questions:
            return

        async with aiosqlite.connect(self.db_path) as db:
            # Delete existing questions for this chunk
            await db.execute("DELETE FROM chunk_questions WHERE chunk_id = ?", (chunk_id,))

            await db.executemany(
                """
                INSERT INTO chunk_questions (chunk_id, question, vector_id)
                VALUES (?, ?, ?)
                """,
                [(chunk_id, q.question, q.vector_id) for q in questions],
            )
            await db.commit()

    async def get_chunk_questions(self, chunk_id: str) -> list[ChunkQuestion]:
        """Get questions for a chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM chunk_questions WHERE chunk_id = ?", (chunk_id,)
            )
            rows = await cursor.fetchall()
            return [
                ChunkQuestion(
                    id=row["id"],
                    chunk_id=row["chunk_id"],
                    question=row["question"],
                    vector_id=row["vector_id"],
                )
                for row in rows
            ]

    async def get_all_chunk_questions(self) -> list[ChunkQuestion]:
        """Get all chunk questions (for building question index)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM chunk_questions")
            rows = await cursor.fetchall()
            return [
                ChunkQuestion(
                    id=row["id"],
                    chunk_id=row["chunk_id"],
                    question=row["question"],
                    vector_id=row["vector_id"],
                )
                for row in rows
            ]

    async def update_question_vector_id(self, question_id: int, vector_id: str) -> bool:
        """Update the vector ID for a question."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE chunk_questions SET vector_id = ? WHERE id = ?",
                (vector_id, question_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    # ============== Vector Embeddings Methods ==============

    async def add_vector_embedding(self, embedding: VectorEmbedding) -> None:
        """Insert or update a vector embedding record."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO vector_embeddings
                (id, chunk_id, vector_type, source_text, question_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    embedding.id,
                    embedding.chunk_id,
                    embedding.vector_type,
                    embedding.source_text,
                    embedding.question_id,
                ),
            )
            await db.commit()

    async def add_vector_embeddings_batch(self, embeddings: list[VectorEmbedding]) -> None:
        """Insert multiple vector embedding records."""
        if not embeddings:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany(
                """
                INSERT OR REPLACE INTO vector_embeddings
                (id, chunk_id, vector_type, source_text, question_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (e.id, e.chunk_id, e.vector_type, e.source_text, e.question_id)
                    for e in embeddings
                ],
            )
            await db.commit()

    async def get_vector_embeddings_by_chunk(self, chunk_id: str) -> list[VectorEmbedding]:
        """Get all vector embeddings for a chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM vector_embeddings WHERE chunk_id = ?", (chunk_id,)
            )
            rows = await cursor.fetchall()
            return [
                VectorEmbedding(
                    id=row["id"],
                    chunk_id=row["chunk_id"],
                    vector_type=row["vector_type"],
                    source_text=row["source_text"],
                    question_id=row["question_id"],
                )
                for row in rows
            ]

    async def get_vector_embedding(self, vector_id: str) -> VectorEmbedding | None:
        """Get a vector embedding by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM vector_embeddings WHERE id = ?", (vector_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return VectorEmbedding(
                id=row["id"],
                chunk_id=row["chunk_id"],
                vector_type=row["vector_type"],
                source_text=row["source_text"],
                question_id=row["question_id"],
            )

    async def delete_vector_embeddings_by_chunk(self, chunk_id: str) -> int:
        """Delete all vector embeddings for a chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM vector_embeddings WHERE chunk_id = ?", (chunk_id,)
            )
            await db.commit()
            return cursor.rowcount

    # ============== Hierarchical Chunk Methods ==============

    async def get_chunk_tree(self, document_id: str) -> list[dict]:
        """Get hierarchical chunk tree for a document."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT c.*, cm.title, cm.summary, cm.category
                FROM chunks c
                LEFT JOIN chunk_metadata cm ON c.id = cm.chunk_id
                WHERE c.document_id = ?
                ORDER BY c.chunk_index
                """,
                (document_id,),
            )
            rows = await cursor.fetchall()

            # Build tree structure
            chunks_by_id = {}
            root_chunks = []

            for row in rows:
                chunk_data = {
                    "id": row["id"],
                    "text": row["text"][:100] + "..." if len(row["text"]) > 100 else row["text"],
                    "content_type": row["content_type"],
                    "hierarchy_level": row["hierarchy_level"] if "hierarchy_level" in row.keys() else 0,
                    "parent_chunk_id": row["parent_chunk_id"] if "parent_chunk_id" in row.keys() else None,
                    "chunk_index": row["chunk_index"],
                    "title": row["title"] if "title" in row.keys() else None,
                    "summary": row["summary"] if "summary" in row.keys() else None,
                    "category": row["category"] if "category" in row.keys() else None,
                    "children": [],
                }
                chunks_by_id[row["id"]] = chunk_data

                if chunk_data["parent_chunk_id"] is None:
                    root_chunks.append(chunk_data)

            # Build hierarchy
            for chunk_id, chunk_data in chunks_by_id.items():
                parent_id = chunk_data["parent_chunk_id"]
                if parent_id and parent_id in chunks_by_id:
                    chunks_by_id[parent_id]["children"].append(chunk_data)

            return root_chunks

    async def get_child_chunks(self, parent_chunk_id: str) -> list[Chunk]:
        """Get all direct children of a chunk."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM chunks WHERE parent_chunk_id = ? ORDER BY chunk_index",
                (parent_chunk_id,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_chunk(row) for row in rows]

    async def get_chunks_by_hierarchy_level(
        self, document_id: str, hierarchy_level: int
    ) -> list[Chunk]:
        """Get all chunks at a specific hierarchy level."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM chunks
                WHERE document_id = ? AND hierarchy_level = ?
                ORDER BY chunk_index
                """,
                (document_id, hierarchy_level),
            )
            rows = await cursor.fetchall()
            return [self._row_to_chunk(row) for row in rows]


# Global instance
metadata_store = MetadataStore()
