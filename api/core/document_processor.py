"""Document processor that orchestrates parsing, enrichment, and indexing."""

import json
import logging
from datetime import datetime
from pathlib import Path

from config.settings import settings
from core.file_utils import get_file_type, get_processing_dir, is_tabular
from core.utils import generate_document_id, compute_file_hash
from models.document import Document
from models.chunk import Chunk, VectorEmbedding
from parsers import parser_registry
from parsers.base import ParseResult
from enrichment import entity_extractor
from models.enrichment import EnrichmentResult
from indexing.chunker import chunker, rebuild_contextualized_text
from indexing.embedder import embedder
from indexing.keyword_index import keyword_index
from indexing.metadata_store import metadata_store
from indexing.multi_vector_index import multi_vector_index
from indexing.hierarchical_chunker import hierarchical_chunker
from indexing.semantic_chunker import create_semantic_chunker
from indexing.chunk_enricher import chunk_enricher

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Orchestrates the complete document processing pipeline.

    Public step methods (the single flow):
        chunk_document()  -> create chunks from markdown/tabular data
        enrich_chunks()   -> LLM-enrich chunks with summaries & questions
        index_vectors()   -> embed and index into multi-vector store

    Reindex:
        reindex_all()     -> chains step methods for every file

    Utilities:
        remove_file(), save_indexes(), load_indexes()
    """

    # ------------------------------------------------------------------ #
    #  Public step methods                                                 #
    # ------------------------------------------------------------------ #

    async def chunk_document(
        self,
        document_id: str,
        markdown: str | None = None,
    ) -> int:
        """Create chunks for a document (unified: tabular, paragraph, hierarchical).

        Args:
            document_id: Document ID to chunk
            markdown: Optional markdown content (if not provided, reads from DB)

        Returns:
            Number of chunks created
        """
        logger.info(f"Chunking document: {document_id}")

        doc = await metadata_store.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        tabular = is_tabular(doc.file_type or "")

        # Resolve markdown from DB if not provided (non-tabular only)
        if not tabular and markdown is None:
            markdown_data = await metadata_store.get_document_markdown(document_id)
            if markdown_data:
                markdown = markdown_data.get("reviewed_markdown") or markdown_data.get("extracted_markdown")

        if not tabular and not markdown:
            raise ValueError(f"No markdown content available for: {document_id}")

        # Delete existing chunks + vectors
        existing = await metadata_store.get_chunks_by_document(document_id)
        if existing:
            chunk_ids = [c.id for c in existing]
            keyword_index.remove(chunk_ids)
            for cid in chunk_ids:
                multi_vector_index.remove_chunk(cid)
            await metadata_store.delete_chunks_by_document(document_id)

        # Dispatch to strategy
        if tabular:
            doc_chunks = self._chunk_tabular(doc)
        elif settings.chunking_strategy == "paragraph":
            doc_chunks = self._chunk_paragraph(doc, markdown)
        else:  # "hierarchical" (default)
            doc_chunks = self._chunk_hierarchical(doc, document_id, markdown)

        if not doc_chunks:
            logger.warning(f"No chunks created for: {document_id}")
            await metadata_store.update_document_status(document_id, "failed")
            return 0

        # Save chunks + update status
        await metadata_store.add_chunks(doc_chunks)
        await metadata_store.update_document_status(document_id, "chunked")

        logger.info(f"Created {len(doc_chunks)} chunks for {document_id}")
        return len(doc_chunks)

    async def enrich_chunks(self, document_id: str) -> tuple[int, int]:
        """Enrich document chunks with LLM-generated metadata.

        Args:
            document_id: Document ID to enrich

        Returns:
            Tuple of (chunks_enriched, questions_generated)
        """
        logger.info(f"Enriching chunks for: {document_id}")

        doc = await metadata_store.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        chunks = await metadata_store.get_chunks_by_document(document_id)
        if not chunks:
            raise ValueError(f"No chunks found for: {document_id}")

        doc_context = {
            "file_name": doc.file_name,
            "detected_doc_type": doc.detected_doc_type,
            "summary": doc.summary,
            "entities": doc.entities,
        }

        results = await chunk_enricher.enrich_batch(chunks, doc_context)

        total_questions = 0
        for (metadata, questions), chunk in zip(results, chunks):
            await metadata_store.add_chunk_metadata(metadata)
            if questions:
                await metadata_store.add_chunk_questions(chunk.id, questions)
                total_questions += len(questions)

        # Rebuild contextualized_text with enrichment context
        chunks = rebuild_contextualized_text(
            chunks, results,
            file_name=doc.file_name,
            doc_type=doc.detected_doc_type,
            entities=doc.entities,
        )
        await metadata_store.update_chunks_contextualized_text(chunks)

        await metadata_store.update_document_status(document_id, "enriched")

        logger.info(f"Enriched {len(chunks)} chunks with {total_questions} questions")
        return len(chunks), total_questions

    async def index_vectors(self, document_id: str, save: bool = True) -> dict:
        """Build multi-vector index for a document.

        Uses batch DB queries and batch embedding for efficiency.

        Args:
            document_id: Document ID to index
            save: Whether to persist indexes to disk (False for batch reindex)

        Returns:
            Dict with counts of vectors created
        """
        logger.info(f"Building multi-vector index for: {document_id}")

        chunks = await metadata_store.get_chunks_by_document(document_id)
        if not chunks:
            raise ValueError(f"No chunks found for: {document_id}")

        # --- Batch DB fetch (replaces N+1 per-chunk queries) ---
        chunk_ids = [c.id for c in chunks]
        meta_map = await metadata_store.get_chunk_metadata_batch(chunk_ids)
        questions_map = await metadata_store.get_chunk_questions_batch(chunk_ids)

        # --- Collect texts for batch embedding ---
        main_texts: list[str] = []
        main_chunk_ids: list[str] = []

        summary_texts: list[str] = []
        summary_chunk_ids: list[str] = []

        question_texts: list[str] = []
        question_meta: list[tuple[str, str, int | None]] = []  # (q_vector_id, chunk_id, q.id)

        vector_embeddings: list[VectorEmbedding] = []

        for chunk in chunks:
            metadata = meta_map.get(chunk.id)
            questions = questions_map.get(chunk.id, [])

            # Main embedding text
            main_texts.append(chunk.contextualized_text)
            main_chunk_ids.append(chunk.id)

            # Build enriched BM25 text
            bm25_text = chunk.text
            if metadata:
                enrichment_parts = []
                if metadata.title:
                    enrichment_parts.append(metadata.title)
                if metadata.summary:
                    enrichment_parts.append(metadata.summary)
                if metadata.keywords:
                    enrichment_parts.append(" ".join(metadata.keywords))
                if enrichment_parts:
                    bm25_text = " ".join(enrichment_parts) + " " + bm25_text
            keyword_index.add(chunk.id, bm25_text)

            vector_embeddings.append(VectorEmbedding(
                id=chunk.id,
                chunk_id=chunk.id,
                vector_type="main",
                source_text=chunk.contextualized_text[:200],
            ))

            # Summary embedding text
            if metadata and metadata.summary:
                summary_texts.append(metadata.summary)
                summary_chunk_ids.append(chunk.id)
                summary_id = f"{chunk.id}_summary"
                vector_embeddings.append(VectorEmbedding(
                    id=summary_id,
                    chunk_id=chunk.id,
                    vector_type="summary",
                    source_text=metadata.summary,
                ))

            # Question embedding texts
            for q in questions:
                q_vector_id = f"q_{chunk.id}_{q.id}"
                question_texts.append(q.question)
                question_meta.append((q_vector_id, chunk.id, q.id))
                vector_embeddings.append(VectorEmbedding(
                    id=q_vector_id,
                    chunk_id=chunk.id,
                    vector_type="question",
                    source_text=q.question,
                    question_id=q.id,
                ))

        # --- Batch embed all texts ---
        import numpy as np

        main_embeddings = embedder.embed_batch(main_texts)
        summary_embeddings = embedder.embed_batch(summary_texts) if summary_texts else np.zeros((0, 0))
        question_embeddings = embedder.embed_batch(question_texts) if question_texts else np.zeros((0, 0))

        # --- Add to multi-vector index via public batch API ---
        main_data = list(zip(main_chunk_ids, main_embeddings))
        summary_data = list(zip(summary_chunk_ids, summary_embeddings)) if summary_texts else None
        question_data = (
            [(qm[0], qm[1], question_embeddings[i]) for i, qm in enumerate(question_meta)]
            if question_texts else None
        )

        multi_vector_index.add_batch(
            main_data=main_data,
            summary_data=summary_data,
            question_data=question_data,
        )

        # --- Update question vector IDs in DB ---
        for q_vector_id, _chunk_id, q_id in question_meta:
            if q_id:
                await metadata_store.update_question_vector_id(q_id, q_vector_id)

        # --- Persist vector embedding records ---
        await metadata_store.add_vector_embeddings_batch(vector_embeddings)

        if save:
            multi_vector_index.save()
            keyword_index.save()

        await metadata_store.update_document_status(document_id, "indexed")

        main_count = len(main_texts)
        summary_count = len(summary_texts)
        question_count = len(question_texts)

        logger.info(
            f"Indexed {document_id}: "
            f"{main_count} main, {summary_count} summary, {question_count} question"
        )

        return {
            "main_vectors": main_count,
            "summary_vectors": summary_count,
            "question_vectors": question_count,
        }

    # ------------------------------------------------------------------ #
    #  Reindex                                                             #
    # ------------------------------------------------------------------ #

    async def reindex_all(self) -> dict:
        """Reindex all files in the watch folder using step methods."""
        logger.info("Starting full reindex")

        # Clear ALL indexes
        keyword_index.clear()
        multi_vector_index.clear()
        await metadata_store.clear_all()

        watch_folder = settings.watch_folder
        if not watch_folder.exists():
            logger.warning(f"Watch folder does not exist: {watch_folder}")
            return {"processed": 0, "failed": 0, "skipped": 0}

        processed = 0
        failed = 0
        skipped = 0

        for ext in parser_registry.supported_extensions:
            for file_path in watch_folder.rglob(f"*.{ext}"):
                try:
                    result = await self._reindex_single_file(file_path)
                    if result:
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error(f"Failed to reindex {file_path}: {e}", exc_info=True)
                    failed += 1

        # Save indexes once at the end
        keyword_index.save()
        multi_vector_index.save()

        logger.info(f"Reindex complete: {processed} processed, {failed} failed, {skipped} skipped")
        return {"processed": processed, "failed": failed, "skipped": skipped}

    # ------------------------------------------------------------------ #
    #  Utilities                                                           #
    # ------------------------------------------------------------------ #

    async def remove_file(self, file_path: Path, save: bool = True) -> bool:
        """Remove a file from all indexes, DB, and processing artifacts.

        Args:
            file_path: Path to the file being removed
            save: Whether to persist indexes to disk (False for batch operations)
        """
        document_id = generate_document_id(file_path)

        logger.info(f"Removing from index: {file_path}")

        try:
            chunks = await metadata_store.get_chunks_by_document(document_id)
            chunk_ids = [c.id for c in chunks]

            if chunk_ids:
                keyword_index.remove(chunk_ids)
                for chunk_id in chunk_ids:
                    multi_vector_index.remove_chunk(chunk_id)
                await metadata_store.delete_chunks_by_document(document_id)

            # Delete page records
            await metadata_store.delete_pages(document_id)

            # Delete document record
            result = await metadata_store.delete_document(document_id)

            # Clean up processing directory
            processing_dir = get_processing_dir(document_id)
            if processing_dir.exists():
                import shutil
                shutil.rmtree(processing_dir)

            if save:
                keyword_index.save()
                multi_vector_index.save()

            logger.info(f"Removed {len(chunk_ids)} chunks for: {file_path}")
            return result

        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")
            return False

    async def save_indexes(self) -> None:
        """Save all indexes to disk."""
        logger.info("Saving indexes to disk")
        keyword_index.save()
        multi_vector_index.save()
        logger.info("Indexes saved")

    async def load_indexes(self) -> None:
        """Load all indexes from disk."""
        logger.info("Loading indexes from disk")
        keyword_index.load()
        multi_vector_index.load()
        logger.info("Indexes loaded")

    # ------------------------------------------------------------------ #
    #  Private helpers — chunking strategies                               #
    # ------------------------------------------------------------------ #

    def _chunk_tabular(self, doc: Document) -> list[Chunk]:
        """Chunk a tabular file (CSV/Excel) by re-parsing to get DataFrame."""
        file_path = Path(doc.file_path)
        parser = parser_registry.get_parser(file_path)
        parse_result = parser.parse(file_path)

        enrichment = EnrichmentResult(
            document_type=doc.detected_doc_type or "tabular data",
            summary=doc.summary or f"Tabular file: {doc.file_name}",
            entities=doc.entities or {},
            key_topics=doc.key_topics or [],
            table_descriptions=doc.table_descriptions or [],
        )

        chunks = chunker.chunk_tabular(
            parse_result=parse_result,
            enrichment=enrichment,
            document_id=doc.id,
            file_name=doc.file_name,
        )
        return chunks

    def _chunk_paragraph(self, doc: Document, markdown: str) -> list[Chunk]:
        """Chunk using the paragraph-based chunker."""
        parse_result = ParseResult(
            text=markdown,
            tables=[],
            headings=[],
        )

        enrichment = EnrichmentResult(
            document_type=doc.detected_doc_type or "unknown",
            summary=doc.summary or "",
            entities=doc.entities or {},
            key_topics=doc.key_topics or [],
            table_descriptions=doc.table_descriptions or [],
        )

        chunks = chunker.chunk_document(
            parse_result=parse_result,
            enrichment=enrichment,
            document_id=doc.id,
            file_name=doc.file_name,
        )
        return chunks

    def _chunk_hierarchical(self, doc: Document, document_id: str, markdown: str) -> list[Chunk]:
        """Chunk using the hierarchical markdown-tree chunker."""
        layout_data = None
        if doc.layout_data:
            try:
                layout_data = json.loads(doc.layout_data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse layout data for {document_id}")

        doc_chunks = hierarchical_chunker.chunk_document(
            markdown=markdown,
            layout_data=layout_data,
            document_id=document_id,
            file_name=doc.file_name,
            detected_doc_type=doc.detected_doc_type,
            entities=doc.entities,
        )

        # Semantic chunking (refine large chunks)
        if settings.enable_semantic_chunking and doc_chunks:
            semantic_chunker = create_semantic_chunker(embedder)
            doc_chunks = semantic_chunker.refine_chunks(doc_chunks, settings.max_chunk_size)

        return doc_chunks

    # ------------------------------------------------------------------ #
    #  Private helpers — reindex single file                               #
    # ------------------------------------------------------------------ #

    async def _reindex_single_file(self, file_path: Path) -> bool:
        """Reindex a single file: parse -> doc-enrich -> chunk -> enrich -> index."""
        logger.info(f"Reindexing: {file_path}")

        document_id = generate_document_id(file_path)
        file_hash = compute_file_hash(file_path)

        # Step 1: Parse
        parser = parser_registry.get_parser(file_path)
        parse_result = parser.parse(file_path)

        if not parse_result.text:
            logger.warning(f"No text extracted from: {file_path}")
            return False

        # Step 2: Document-level enrichment
        file_type = get_file_type(file_path)
        enrichment = await entity_extractor.enrich(
            parse_result=parse_result,
            file_name=file_path.name,
            file_type=file_type,
        )

        # Step 3: Create + store Document
        document = Document(
            id=document_id,
            file_path=str(file_path.absolute()),
            file_name=file_path.name,
            file_type=file_type,
            file_hash=file_hash,
            detected_doc_type=enrichment.document_type,
            summary=enrichment.summary,
            entities=enrichment.entities,
            key_topics=enrichment.key_topics,
            table_descriptions=enrichment.table_descriptions,
            indexed_at=datetime.utcnow(),
            processing_status="processing",
            sheet_names=parse_result.sheet_names,
            column_schema=parse_result.column_types,
            row_count=parse_result.row_count,
        )
        await metadata_store.add_document(document)

        # Step 4: Store markdown for non-tabular files
        markdown = parse_result.markdown if hasattr(parse_result, "markdown") and parse_result.markdown else parse_result.text
        tabular = is_tabular(file_type)
        if not tabular:
            await metadata_store.update_document_markdown(document_id, markdown)

        # Step 5-7: chunk -> enrich -> index (using step methods)
        try:
            await self.chunk_document(document_id, markdown if not tabular else None)
        except ValueError as e:
            logger.warning(f"Chunking failed for {file_path}: {e}")
            await metadata_store.update_document_status(document_id, "failed")
            return False

        try:
            await self.enrich_chunks(document_id)
        except Exception as e:
            logger.warning(f"Chunk enrichment failed for {file_path}, continuing: {e}")

        await self.index_vectors(document_id, save=False)

        logger.info(f"Reindexed: {file_path.name}")
        return True


# Global instance
document_processor = DocumentProcessor()
