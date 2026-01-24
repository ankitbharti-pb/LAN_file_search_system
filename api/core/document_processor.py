"""Document processor that orchestrates parsing, enrichment, and indexing."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from config.settings import settings
from models.document import Document
from models.chunk import VectorEmbedding
from parsers import parser_registry
from parsers.base import ParseResult
from enrichment import entity_extractor
from indexing.chunker import chunker
from indexing.embedder import embedder
from indexing.vector_index import vector_index
from indexing.keyword_index import keyword_index
from indexing.metadata_store import metadata_store
from indexing.multi_vector_index import multi_vector_index
from indexing.hierarchical_chunker import hierarchical_chunker
from indexing.semantic_chunker import create_semantic_chunker
from indexing.chunk_enricher import chunk_enricher

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Orchestrates the complete document processing pipeline."""

    async def process_file(self, file_path: Path) -> Document | None:
        """Process a file through the complete pipeline.

        Steps:
        1. Parse file
        2. Enrich with LLM
        3. Create chunks
        4. Embed chunks
        5. Index in vector store
        6. Index in keyword store
        7. Store metadata
        """
        logger.info(f"Processing file: {file_path}")

        # Check if file is supported
        if not parser_registry.is_supported(file_path):
            logger.warning(f"Unsupported file type: {file_path}")
            return None

        try:
            # Generate document ID and check for changes
            document_id = self._generate_document_id(file_path)
            file_hash = self._compute_file_hash(file_path)

            # Check if already indexed with same hash
            existing = await metadata_store.get_document(document_id)
            if existing and existing.file_hash == file_hash:
                logger.info(f"File unchanged, skipping: {file_path}")
                return existing

            # If exists but changed, remove old data
            if existing:
                logger.info(f"File changed, reindexing: {file_path}")
                await self.remove_file(file_path)

            # Step 1: Parse
            logger.debug(f"Parsing: {file_path}")
            parser = parser_registry.get_parser(file_path)
            parse_result = parser.parse(file_path)

            # Step 2: Enrich with LLM
            logger.debug(f"Enriching: {file_path}")
            file_type = file_path.suffix.lower().lstrip(".")
            enrichment = await entity_extractor.enrich(
                parse_result=parse_result,
                file_name=file_path.name,
                file_type=file_type,
            )

            # Step 3: Create document model
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
                sheet_names=parse_result.sheet_names,
                column_schema=parse_result.column_types,
                row_count=parse_result.row_count,
            )

            # Step 4: Create chunks
            logger.debug(f"Chunking: {file_path}")
            is_tabular = file_type in ["csv", "xlsx", "xls"]
            if is_tabular:
                chunks = chunker.chunk_tabular(
                    parse_result=parse_result,
                    enrichment=enrichment,
                    document_id=document_id,
                    file_name=file_path.name,
                )
            else:
                chunks = chunker.chunk_document(
                    parse_result=parse_result,
                    enrichment=enrichment,
                    document_id=document_id,
                    file_name=file_path.name,
                )

            if not chunks:
                logger.warning(f"No chunks created for: {file_path}")
                return None

            # Step 5: Embed chunks
            logger.debug(f"Embedding {len(chunks)} chunks")
            contextualized_texts = [c.contextualized_text for c in chunks]
            embeddings = embedder.embed_batch(contextualized_texts)

            # Step 6: Index in vector store
            logger.debug("Indexing in vector store")
            chunk_ids = [c.id for c in chunks]
            vector_index.add_batch(chunk_ids, embeddings)

            # Step 7: Index in keyword store
            logger.debug("Indexing in keyword store")
            keyword_index.add_batch(chunk_ids, contextualized_texts)

            # Step 8: Store metadata
            logger.debug("Storing metadata")
            await metadata_store.add_document(document)
            await metadata_store.add_chunks(chunks)

            logger.info(
                f"Successfully indexed {file_path.name}: "
                f"{len(chunks)} chunks, type={enrichment.document_type}"
            )

            return document

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
            raise

    async def remove_file(self, file_path: Path) -> bool:
        """Remove a file from all indexes."""
        document_id = self._generate_document_id(file_path)

        logger.info(f"Removing from index: {file_path}")

        try:
            # Get chunks for this document
            chunks = await metadata_store.get_chunks_by_document(document_id)
            chunk_ids = [c.id for c in chunks]

            if chunk_ids:
                # Remove from vector index
                vector_index.remove(chunk_ids)

                # Remove from keyword index
                keyword_index.remove(chunk_ids)

                # Remove from multi-vector index
                for chunk_id in chunk_ids:
                    multi_vector_index.remove_chunk(chunk_id)

                # Remove chunks from metadata store
                await metadata_store.delete_chunks_by_document(document_id)

            # Remove document from metadata store
            result = await metadata_store.delete_document(document_id)

            logger.info(f"Removed {len(chunk_ids)} chunks for: {file_path}")
            return result

        except Exception as e:
            logger.error(f"Failed to remove {file_path}: {e}")
            return False

    async def reindex_all(self) -> dict:
        """Reindex all files in the watch folder."""
        logger.info("Starting full reindex")

        # Clear all indexes
        vector_index.clear()
        keyword_index.clear()

        # Get all supported files
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
                    result = await self.process_file(file_path)
                    if result:
                        processed += 1
                    else:
                        skipped += 1
                except Exception as e:
                    logger.error(f"Failed to reindex {file_path}: {e}")
                    failed += 1

        # Save indexes
        await self.save_indexes()

        logger.info(f"Reindex complete: {processed} processed, {failed} failed, {skipped} skipped")

        return {"processed": processed, "failed": failed, "skipped": skipped}

    async def save_indexes(self) -> None:
        """Save all indexes to disk."""
        logger.info("Saving indexes to disk")
        vector_index.save()
        keyword_index.save()
        logger.info("Indexes saved")

    async def load_indexes(self) -> None:
        """Load all indexes from disk."""
        logger.info("Loading indexes from disk")
        vector_index.load()
        keyword_index.load()
        logger.info("Indexes loaded")

    def _generate_document_id(self, file_path: Path) -> str:
        """Generate a unique document ID from file path."""
        path_str = str(file_path.absolute())
        return hashlib.sha256(path_str.encode()).hexdigest()[:32]

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def index_from_markdown(self, document_id: str, markdown: str) -> Document | None:
        """Index a document from its extracted/reviewed markdown.

        This is used for the manual processing workflow where:
        1. Layout detection and text extraction have been completed
        2. The user has reviewed/edited the markdown
        3. Now we index it for search

        Steps:
        1. Get document metadata from database
        2. Create ParseResult from markdown
        3. Enrich with LLM
        4. Create chunks
        5. Embed chunks
        6. Index in vector store
        7. Index in keyword store
        8. Update document with enrichment data
        """
        logger.info(f"Indexing document from markdown: {document_id}")

        # Get document from database
        doc = await metadata_store.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        file_path = Path(doc.file_path)
        file_type = doc.file_type

        try:
            # Remove existing chunks if reindexing
            chunks = await metadata_store.get_chunks_by_document(document_id)
            if chunks:
                chunk_ids = [c.id for c in chunks]
                vector_index.remove(chunk_ids)
                keyword_index.remove(chunk_ids)
                await metadata_store.delete_chunks_by_document(document_id)

            # Create minimal ParseResult from markdown
            parse_result = ParseResult(
                text=markdown,
                tables=[],
                headings=[],
            )

            # Enrich with LLM
            logger.debug(f"Enriching: {doc.file_name}")
            enrichment = await entity_extractor.enrich(
                parse_result=parse_result,
                file_name=doc.file_name,
                file_type=file_type,
            )

            # Create chunks
            logger.debug(f"Chunking: {doc.file_name}")
            is_tabular = file_type in ["csv", "xlsx", "xls"]
            if is_tabular:
                doc_chunks = chunker.chunk_tabular(
                    parse_result=parse_result,
                    enrichment=enrichment,
                    document_id=document_id,
                    file_name=doc.file_name,
                )
            else:
                doc_chunks = chunker.chunk_document(
                    parse_result=parse_result,
                    enrichment=enrichment,
                    document_id=document_id,
                    file_name=doc.file_name,
                )

            if not doc_chunks:
                logger.warning(f"No chunks created for: {doc.file_name}")
                return None

            # Embed chunks
            logger.debug(f"Embedding {len(doc_chunks)} chunks")
            contextualized_texts = [c.contextualized_text for c in doc_chunks]
            embeddings = embedder.embed_batch(contextualized_texts)

            # Index in vector store
            logger.debug("Indexing in vector store")
            chunk_ids = [c.id for c in doc_chunks]
            vector_index.add_batch(chunk_ids, embeddings)

            # Index in keyword store
            logger.debug("Indexing in keyword store")
            keyword_index.add_batch(chunk_ids, contextualized_texts)

            # Add chunks to metadata store
            await metadata_store.add_chunks(doc_chunks)

            # Update document with enrichment data
            await metadata_store.update_document_enrichment(
                document_id=document_id,
                detected_doc_type=enrichment.document_type,
                summary=enrichment.summary,
                entities=enrichment.entities,
                key_topics=enrichment.key_topics,
                table_descriptions=enrichment.table_descriptions,
            )

            logger.info(
                f"Successfully indexed {doc.file_name}: "
                f"{len(doc_chunks)} chunks, type={enrichment.document_type}"
            )

            # Save indexes
            await self.save_indexes()

            # Return the updated document
            return await metadata_store.get_document(document_id)

        except Exception as e:
            logger.error(f"Failed to index {document_id}: {e}", exc_info=True)
            raise

    async def chunk_document_advanced(
        self,
        document_id: str,
        markdown: str | None = None,
    ) -> int:
        """Create hierarchical + semantic chunks for a document.

        Args:
            document_id: Document ID to chunk
            markdown: Optional markdown content (if not provided, uses reviewed/extracted from DB)

        Returns:
            Number of chunks created
        """
        logger.info(f"Running advanced chunking for: {document_id}")

        # Get document
        doc = await metadata_store.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        # Get markdown if not provided
        if markdown is None:
            markdown_data = await metadata_store.get_document_markdown(document_id)
            if markdown_data:
                markdown = markdown_data.get("reviewed_markdown") or markdown_data.get("extracted_markdown")

        if not markdown:
            raise ValueError(f"No markdown content available for: {document_id}")

        # Parse layout data
        import json
        layout_data = None
        if doc.layout_data:
            try:
                layout_data = json.loads(doc.layout_data)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse layout data for {document_id}")

        # Delete existing chunks
        chunks = await metadata_store.get_chunks_by_document(document_id)
        if chunks:
            chunk_ids = [c.id for c in chunks]
            vector_index.remove(chunk_ids)
            keyword_index.remove(chunk_ids)
            for cid in chunk_ids:
                multi_vector_index.remove_chunk(cid)
            await metadata_store.delete_chunks_by_document(document_id)

        # Hierarchical chunking
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

        # Save chunks
        await metadata_store.add_chunks(doc_chunks)

        # Update status
        await metadata_store.update_document_status(document_id, "chunked")

        logger.info(f"Created {len(doc_chunks)} chunks for {document_id}")
        return len(doc_chunks)

    async def enrich_chunks_advanced(self, document_id: str) -> tuple[int, int]:
        """Enrich document chunks with LLM-generated metadata.

        Args:
            document_id: Document ID to enrich

        Returns:
            Tuple of (chunks_enriched, questions_generated)
        """
        logger.info(f"Enriching chunks for: {document_id}")

        # Get document
        doc = await metadata_store.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        # Get chunks
        chunks = await metadata_store.get_chunks_by_document(document_id)
        if not chunks:
            raise ValueError(f"No chunks found for: {document_id}")

        # Prepare context
        doc_context = {
            "file_name": doc.file_name,
            "detected_doc_type": doc.detected_doc_type,
            "summary": doc.summary,
        }

        # Enrich
        results = await chunk_enricher.enrich_batch(chunks, doc_context)

        # Save results
        total_questions = 0
        for (metadata, questions), chunk in zip(results, chunks):
            await metadata_store.add_chunk_metadata(metadata)
            if questions:
                await metadata_store.add_chunk_questions(chunk.id, questions)
                total_questions += len(questions)

        # Update status
        await metadata_store.update_document_status(document_id, "enriched")

        logger.info(f"Enriched {len(chunks)} chunks with {total_questions} questions")
        return len(chunks), total_questions

    async def index_multi_vector(self, document_id: str) -> dict:
        """Build multi-vector index for a document.

        Args:
            document_id: Document ID to index

        Returns:
            Dict with counts of vectors created
        """
        logger.info(f"Building multi-vector index for: {document_id}")

        # Get chunks
        chunks = await metadata_store.get_chunks_by_document(document_id)
        if not chunks:
            raise ValueError(f"No chunks found for: {document_id}")

        main_count = 0
        summary_count = 0
        question_count = 0

        for chunk in chunks:
            # Get metadata and questions
            metadata = await metadata_store.get_chunk_metadata(chunk.id)
            questions = await metadata_store.get_chunk_questions(chunk.id)

            # Main embedding
            main_emb = embedder.embed(chunk.contextualized_text)
            multi_vector_index.main_index.add(chunk.id, main_emb)
            keyword_index.add(chunk.id, chunk.text)
            main_count += 1

            # Track embedding
            await metadata_store.add_vector_embedding(VectorEmbedding(
                id=chunk.id,
                chunk_id=chunk.id,
                vector_type="main",
                source_text=chunk.contextualized_text[:200],
            ))

            # Summary embedding
            if metadata and metadata.summary:
                summary_emb = embedder.embed(metadata.summary)
                summary_id = f"{chunk.id}_summary"
                multi_vector_index.summary_index.add(summary_id, summary_emb)
                summary_count += 1

                await metadata_store.add_vector_embedding(VectorEmbedding(
                    id=summary_id,
                    chunk_id=chunk.id,
                    vector_type="summary",
                    source_text=metadata.summary,
                ))

            # Question embeddings
            for q in questions:
                q_emb = embedder.embed(q.question)
                q_vector_id = f"q_{chunk.id}_{q.id}"
                multi_vector_index.question_index.add(q_vector_id, q_emb)

                if q.id:
                    await metadata_store.update_question_vector_id(q.id, q_vector_id)

                await metadata_store.add_vector_embedding(VectorEmbedding(
                    id=q_vector_id,
                    chunk_id=chunk.id,
                    vector_type="question",
                    source_text=q.question,
                    question_id=q.id,
                ))
                question_count += 1

        # Save indices
        multi_vector_index.save()
        keyword_index.save()

        # Update status
        await metadata_store.update_document_status(document_id, "indexed")

        logger.info(
            f"Indexed {document_id}: "
            f"{main_count} main, {summary_count} summary, {question_count} question"
        )

        return {
            "main_vectors": main_count,
            "summary_vectors": summary_count,
            "question_vectors": question_count,
        }


# Global instance
document_processor = DocumentProcessor()
