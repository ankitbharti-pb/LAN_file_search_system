# CLAUDE.md

## Quick Reference

### Backend (run from `api/`)
```bash
pip install -r requirements.txt          # Install deps
python main.py                           # Dev server (port 8000, auto-reload)
pytest tests/                            # Run tests
```

### Frontend (run from `ui/`)
```bash
npm install                              # Install deps
npm run dev                              # Dev server (port 3000, proxies to :8000)
npm run build                            # TypeScript check + Vite build -> dist/
```

## Architecture

Two-tier app: React/TypeScript frontend + Python/FastAPI backend.

**RAG pipeline**: Upload → Layout Detection → Text Extraction → Markdown → Chunk → Enrich → Embed → Index → Search

### Backend (`api/`)
- **Entry point**: `main.py` — FastAPI app with lifespan manager (loads indexes, models on startup; saves on shutdown)
- **Routers**: `api/routes/` — health, search, documents, stats, admin, files, processing, chunking
- **Schemas**: `api/schemas/` — Pydantic request/response models per domain
- **Core**: `core/document_processor.py` — single orchestrator with step methods: `chunk_document()` → `enrich_chunks()` → `index_vectors()`
- **Indexing**: FAISS vector index (`indexing/vector_index.py`), BM25 keyword index (`indexing/keyword_index.py`), SQLite metadata store (`indexing/metadata_store.py`)
- **Search**: hybrid search with RRF fusion (`search/enhanced_hybrid_search.py`), optional HyDE, MMR, cross-encoder reranking
- **Parsers**: `parsers/base.py` — document parsing with layout detection (`processing/layout_detector.py`)
- **Enrichment**: LLM-based chunk enrichment (`indexing/chunk_enricher.py`), entity extraction (`enrichment/entity_extractor.py`)
- **Config**: `config/settings.py` — Pydantic Settings, reads from `.env`

### Frontend (`ui/`)
- React + TypeScript + Vite + Tailwind CSS
- Vite proxy: `/api/*` → `localhost:8000` (strips prefix), `/processing/*` → `localhost:8000` (keeps path)
- TypeScript strict mode enabled

## Processing Flow

The `DocumentProcessor` (`core/document_processor.py`) is the single orchestrator:

1. **`chunk_document(file_id)`** — Picks chunker based on `CHUNKING_STRATEGY` setting:
   - `"hierarchical"` → `HierarchicalChunker` (markdown-tree based)
   - `"paragraph"` → `Chunker` (paragraph-based)
   - Tabular files auto-detected → `chunk_tabular()` regardless of strategy
2. **`enrich_chunks(file_id)`** — LLM enrichment: generates summaries, contextual descriptions, HyDE questions per chunk. Calls `rebuild_contextualized_text()` (single insertion point).
3. **`index_vectors(file_id)`** — Reads enriched text from DB, embeds with sentence-transformers, adds to FAISS + BM25 indexes.

`reindex_all()` chains: `_reindex_single_file()` → chunk → enrich → `index(save=False)`, saves once at end.

## Key Patterns

- **Enrichment results**: `list[tuple[ChunkMetadata | None, list[ChunkQuestion]]]` parallel to chunks list. Failed enrichment falls back to `[(None, []) for _ in chunks]`.
- **Route error handling**: Routes catch `ValueError` from DocumentProcessor step methods and return `HTTPException(400)`.
- **Chunking routes** (`api/routes/chunking.py`): thin wrappers delegating to `document_processor`.
- **Processing routes** (`api/routes/processing.py`): upload, layout, extract-text, markdown endpoints (no indexing).
- **`index_vectors(save=True)`**: `save` param controls whether FAISS/BM25 indexes flush to disk (False during batch reindex).

## Key Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `openai` | `openai` or `gemini` |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Base LLM model |
| `ENRICHMENT_MODEL` | *(empty=base)* | Override for chunk enrichment |
| `SYNTHESIS_MODEL` | *(empty=base)* | Override for response synthesis |
| `VLM_PROVIDER` | `ollama` | `ollama` or `huggingface` |
| `OLLAMA_MODEL` | `qwen3-vl:8b` | Vision model for PDF layout |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Sentence-transformers model (768-dim) |
| `CHUNKING_STRATEGY` | `hierarchical` | `hierarchical` or `paragraph` |
| `CHUNK_SIZE` | `1500` | Target chars per chunk |
| `WATCH_FOLDER` | `./documents` | Document ingestion folder |
| `DATA_FOLDER` | `./data` | Runtime data (FAISS, BM25, SQLite, cache) |
