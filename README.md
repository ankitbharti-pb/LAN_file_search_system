# LAN File Search System — Knowledge Transfer Document

> **Version:** 2.0
> **Last Updated:** February 2026
> **Audience:** New developers onboarding to the project

---

## Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Project Structure](#2-project-structure)
3. [Backend Deep-Dive](#3-backend-deep-dive)
   - 3.1 [Entry Point & Startup](#31-entry-point--startup)
   - 3.2 [Configuration](#32-configuration)
   - 3.3 [Data Models](#33-data-models)
   - 3.4 [API Routes](#34-api-routes)
   - 3.5 [File Processing Pipeline](#35-file-processing-pipeline)
   - 3.6 [Indexing & RAG Pipeline](#36-indexing--rag-pipeline)
   - 3.7 [Search System](#37-search-system)
   - 3.8 [LLM Integration](#38-llm-integration)
4. [Frontend Deep-Dive](#4-frontend-deep-dive)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [Database Schema](#6-database-schema)
7. [Configuration Reference](#7-configuration-reference)
8. [Deployment](#8-deployment)
9. [Key Design Decisions](#9-key-design-decisions)

---

## 1. System Overview & Architecture

### What It Does

The LAN File Search System is a self-hosted document search engine for local area networks. Users upload documents (PDF, DOCX, PPTX, CSV, Excel), the system parses, enriches, chunks, and indexes them into a multi-vector store, then provides hybrid semantic + keyword search with optional LLM-synthesized answers.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         React UI (:3000)                        │
│   Search │ Documents │ Document Detail │ File Browser │ Admin   │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP / REST
┌─────────────────────────▼───────────────────────────────────────┐
│                     FastAPI Backend (:8000)                      │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Processing│  │ Chunking │  │Enrichment│  │    Search       │  │
│  │ Pipeline  │  │ Engine   │  │  (LLM)   │  │  (Hybrid+RRF)  │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───────┬────────┘  │
│       │              │             │                │            │
│  ┌────▼──────────────▼─────────────▼────────────────▼────────┐  │
│  │                    Index Layer                              │  │
│  │  FAISS (3 indices) │ BM25 │ SQLite │ Semantic Cache        │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18 + TypeScript, Vite, TailwindCSS, React Router |
| **Backend** | Python 3.11, FastAPI, Pydantic v2, uvicorn |
| **Database** | SQLite (aiosqlite) with WAL mode |
| **Vector Store** | FAISS (3 separate indices: main, summary, question) |
| **Keyword Index** | BM25 (rank_bm25) with domain synonym expansion |
| **Embeddings** | sentence-transformers (all-mpnet-base-v2, 768d) |
| **Layout Detection** | DocLayout-YOLO |
| **VLM** | Ollama (local) or HuggingFace Inference API |
| **LLM** | OpenAI API (GPT-4o-mini default) or Google Gemini |
| **Re-ranker** | cross-encoder/ms-marco-MiniLM-L-6-v2 (optional) |
| **Deployment** | Docker Compose (API + UI containers) |

### RAG Pipeline Summary

```
Upload → Parse → Enrich (doc-level) → Chunk → Enrich (chunk-level) → Embed → Index → Search
```

---

## 2. Project Structure

```
LAN_file_search_system/
├── api/                          # Python backend
│   ├── main.py                   # FastAPI entry point, lifespan manager
│   ├── Dockerfile                # API container (Python 3.11-slim)
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Full configuration reference
│   │
│   ├── config/
│   │   └── settings.py           # Pydantic Settings (all env vars)
│   │
│   ├── models/                   # Pydantic domain models
│   │   ├── document.py           # Document, DocumentSummary, DocumentEntity
│   │   ├── chunk.py              # Chunk, ChunkWithScore, ChunkMetadata, ChunkQuestion, VectorEmbedding
│   │   └── search_result.py      # SearchRequest, SearchResponse, SearchResultItem, SourceInfo
│   │
│   ├── api/                      # API layer
│   │   ├── routes/
│   │   │   ├── health.py         # GET /health
│   │   │   ├── search.py         # POST /search
│   │   │   ├── documents.py      # GET /documents, GET /documents/{id}
│   │   │   ├── stats.py          # GET /stats
│   │   │   ├── admin.py          # POST /admin/reindex, GET /admin/reindex/status, POST /admin/clear-cache
│   │   │   ├── files.py          # File browser: browse, upload, download, preview, delete
│   │   │   ├── processing.py     # PDF layout detection, text extraction, markdown management
│   │   │   └── chunking.py       # Chunk, enrich, index-vectors, chunk viewing, retrieval debug
│   │   └── schemas.py            # Shared Pydantic response schemas
│   │
│   ├── core/
│   │   ├── document_processor.py # DocumentProcessor orchestrator (THE single processing flow)
│   │   └── utils.py              # generate_document_id(), compute_file_hash()
│   │
│   ├── parsers/                  # File format parsers
│   │   ├── base.py               # ParseResult dataclass, ParserRegistry
│   │   ├── csv_parser.py         # CSV parser (pandas)
│   │   └── excel_parser.py       # Excel parser (pandas, openpyxl)
│   │
│   ├── processing/               # Document processing modules
│   │   ├── layout_detector.py    # DocLayout-YOLO wrapper
│   │   ├── box_filtering.py      # Containment/IoU/Soft-NMS post-processing
│   │   ├── page_renderer.py      # PDF → page images (PyMuPDF)
│   │   ├── reading_order.py      # Left-to-right, top-to-bottom ordering
│   │   ├── region_cropper.py     # Crop detected regions from pages
│   │   ├── text_extractor.py     # PDF text extraction (layout-aware + VLM)
│   │   ├── vlm_client.py         # Ollama / HuggingFace VLM integration
│   │   ├── docx_processor.py     # DOCX → markdown
│   │   ├── pptx_processor.py     # PPTX → markdown
│   │   └── tabular_processor.py  # CSV/Excel → markdown description
│   │
│   ├── enrichment/               # LLM-based enrichment
│   │   ├── llm_client.py         # LLMClient ABC, OpenAIClient, GeminiClient, factory functions
│   │   ├── entity_extractor.py   # Document-level enrichment (EntityExtractor)
│   │   ├── prompts.py            # All LLM prompt templates
│   │   └── __init__.py
│   │
│   ├── indexing/                  # Index management
│   │   ├── chunker.py            # Paragraph-based Chunker + rebuild_contextualized_text()
│   │   ├── hierarchical_chunker.py # Markdown-tree HierarchicalChunker
│   │   ├── semantic_chunker.py   # Embedding-based chunk refinement
│   │   ├── chunk_enricher.py     # ChunkEnricher (LLM metadata + questions per chunk)
│   │   ├── embedder.py           # sentence-transformers embedding wrapper
│   │   ├── vector_index.py       # Single FAISS index wrapper
│   │   ├── multi_vector_index.py # MultiVectorIndex (3 FAISS indices + thread pool)
│   │   ├── keyword_index.py      # BM25 KeywordIndex with synonym expansion
│   │   └── metadata_store.py     # SQLite MetadataStore (all 7 tables)
│   │
│   └── search/                   # Search subsystem
│       ├── enhanced_hybrid_search.py  # Multi-source RRF fusion, HyDE, re-ranking, MMR
│       ├── response_generator.py      # ResponseGenerator (cache → search → synthesize)
│       ├── query_processor.py         # QueryProcessor (intent detection, query type classification)
│       ├── hyde.py                    # HyDE query expansion
│       ├── reranker.py               # Cross-encoder re-ranker (optional)
│       ├── mmr.py                    # Maximum Marginal Relevance (optional)
│       ├── query_preprocessor.py     # Spell check, normalization
│       └── semantic_cache.py         # LRU vectorized semantic cache
│
├── ui/                           # React frontend
│   ├── Dockerfile                # Multi-stage build (Node 20 → nginx)
│   ├── nginx.conf                # Reverse proxy to API
│   ├── package.json              # Dependencies
│   ├── vite.config.ts            # Vite configuration
│   └── src/
│       ├── main.tsx              # React entry point
│       ├── App.tsx               # Router + navigation layout
│       ├── api/
│       │   └── client.ts         # APIClient class + TypeScript types
│       ├── pages/
│       │   ├── Search.tsx        # Search page with results + synthesis
│       │   ├── Documents.tsx     # Document listing
│       │   ├── DocumentDetail.tsx # Single document view with processing controls
│       │   ├── FileBrowser.tsx   # File/folder management with upload
│       │   └── Admin.tsx         # Reindex, cache, system stats
│       ├── components/
│       │   ├── SearchBar.tsx         # Query input
│       │   ├── SearchResults.tsx     # Result list rendering
│       │   ├── DocumentCard.tsx      # Document summary card
│       │   ├── DocumentPreview.tsx   # Preview panel
│       │   ├── LayoutPreview.tsx     # PDF layout detection viewer
│       │   ├── MarkdownEditor.tsx    # Markdown review/edit
│       │   ├── ChunkTreeView.tsx     # Hierarchical chunk tree
│       │   ├── ChunkMetadataPanel.tsx # Chunk enrichment details
│       │   ├── RetrievalDebugPanel.tsx # Debug retrieval sources/scores
│       │   ├── ProcessingStatus.tsx  # Processing pipeline status
│       │   ├── FileTableRow.tsx      # File list row
│       │   ├── FileUploadZone.tsx    # Drag-and-drop upload
│       │   ├── FolderBreadcrumb.tsx  # Folder navigation
│       │   ├── CreateFolderModal.tsx # New folder dialog
│       │   ├── InlineFilePreview.tsx # Inline file preview
│       │   ├── SourcePreviewModal.tsx # Source chunk preview modal
│       │   ├── StatsPanel.tsx        # System statistics panel
│       │   └── Modal.tsx             # Reusable modal
│       ├── styles/               # CSS/Tailwind styles
│       └── utils/                # Utility functions
│
├── docker-compose.yml            # Orchestrates API + UI containers
├── documents/                    # Watch folder (user files go here)
└── .gitignore
```

---

## 3. Backend Deep-Dive

### 3.1 Entry Point & Startup

**File:** `api/main.py`

The FastAPI application uses an async lifespan manager for startup/shutdown:

**Startup sequence:**
1. Initialize SQLite database (create tables, run migrations)
2. Load persisted indexes (FAISS, BM25, semantic cache) from disk
3. Preload ML models for faster first request:
   - DocLayout-YOLO (layout detection)
   - all-mpnet-base-v2 (embedding model)
   - cross-encoder/ms-marco-MiniLM-L-6-v2 (re-ranker)
4. Create watch folder if it doesn't exist

**Shutdown sequence:**
1. Close SQLite database connection
2. Save all indexes to disk (FAISS, BM25, semantic cache)

**CORS:** Allows all origins (`*`) for LAN access.

**Routers included (8 total):**
- `health_router`, `search_router`, `documents_router`, `stats_router`
- `admin_router`, `files_router`, `processing_router`, `chunking_router`

---

### 3.2 Configuration

**File:** `api/config/settings.py`

All configuration is managed through a single `Settings` class using `pydantic-settings`. Values are loaded from environment variables or a `.env` file.

**Configuration categories:**

| Category | Key Settings | Defaults |
|----------|-------------|----------|
| **Paths** | `watch_folder`, `data_folder`, `database_path` | `./documents`, `./data`, `./data/sqlite/metadata.db` |
| **LLM** | `llm_provider`, `openai_api_key`, `openai_model`, `gemini_api_key` | `openai`, `gpt-4o-mini` |
| **Model Overrides** | `enrichment_model`, `synthesis_model` | Empty (uses base model) |
| **VLM** | `vlm_provider`, `ollama_model`, `huggingface_vlm_model` | `ollama`, `qwen3-vl:8b` |
| **Box Filtering** | `box_filter_enabled`, containment/IoU thresholds, soft-NMS | Enabled, 0.85/0.5, sigma=0.3 |
| **Embedding** | `embedding_model`, `embedding_dimension` | `all-mpnet-base-v2`, 768 |
| **Chunking** | `chunk_size`, `chunk_overlap`, `max_chunk_size`, `chunking_strategy` | 1500, 0, 2500, `hierarchical` |
| **CSV** | `csv_rows_per_chunk`, `csv_max_rows_to_index` | 50, 0 (no limit) |
| **Cache** | `cache_ttl_seconds`, `cache_similarity_threshold`, `cache_max_entries` | 3600, 0.92, 2000 |
| **Search** | `search_top_k` | 10 |
| **Synthesis** | `synthesis_max_tokens`, `synthesis_temperature`, `synthesis_max_chunks` | 1500, 0.1, 10 |
| **RRF** | `rrf_k_constant` | 30 |
| **HyDE** | `enable_hyde`, `hyde_alpha`, `hyde_adaptive` | true, 0.5, true |
| **Re-ranking** | `reranker_enabled`, `reranker_model`, `reranker_top_k` | false, `cross-encoder/ms-marco-MiniLM-L-6-v2`, 20 |
| **MMR** | `mmr_enabled`, `mmr_lambda` | false, 0.7 |
| **BM25** | `bm25_expand_synonyms`, `bm25_min_token_length` | true, 2 |
| **Enrichment** | `enrichment_batch_size`, `questions_per_chunk` | 5, 5 |
| **Multi-Vector Weights** | main/question/bm25/summary | 0.40/0.20/0.25/0.15 |
| **Server** | `host`, `port`, `log_level` | `0.0.0.0`, 8000, `INFO` |

**Adaptive weight profiles** (selected by query type at search time):

| Profile | main_vector | bm25 | question_vector | summary_vector |
|---------|------------|------|-----------------|----------------|
| **Default** | 0.40 | 0.25 | 0.20 | 0.15 |
| **Factual** | 0.35 | 0.35 | 0.20 | 0.10 |
| **Exploratory** | 0.45 | 0.15 | 0.25 | 0.15 |
| **Comparative** | 0.35 | 0.20 | 0.30 | 0.15 |
| **Aggregation** | 0.30 | 0.30 | 0.20 | 0.20 |

**Derived paths (properties):**
- FAISS indices: `data/faiss/{main,summary,question}_index.faiss`
- BM25 index: `data/bm25/index.pkl`
- Semantic cache: `data/cache/semantic_cache.pkl`

---

### 3.3 Data Models

**File:** `api/models/document.py`

```python
class Document(BaseModel):
    id: str                    # SHA256 of file path
    file_path: str
    file_name: str
    file_type: str             # pdf, docx, xlsx, csv, pptx
    file_hash: str             # SHA256 of file content
    detected_doc_type: str     # LLM-detected type (invoice, report, etc.)
    summary: str               # LLM-generated 2-3 sentence summary
    entities: dict[str, Any]   # Dynamic key-value pairs from LLM
    key_topics: list[str]
    table_descriptions: list[str]
    indexed_at: datetime
    # Tabular-specific
    sheet_names: list[str] | None
    column_schema: dict[str, str] | None
    row_count: int | None
    date_range: str | None
    # Processing workflow
    processing_status: str     # pending|layout_detected|text_extracted|reviewed|chunked|enriched|indexed
    layout_data: str | None    # JSON layout detection results (PDF only)
    extracted_markdown: str | None
    reviewed_markdown: str | None
    page_count: int | None

class DocumentSummary(BaseModel):  # Lightweight listing model
    id, file_name, file_type, detected_doc_type, summary, indexed_at
```

**File:** `api/models/chunk.py`

```python
class Chunk(BaseModel):
    id: str                    # Unique chunk identifier
    document_id: str           # Parent document
    text: str                  # Original chunk content
    contextualized_text: str   # Enriched text (what gets embedded)
    content_type: Literal["paragraph", "table", "list", "summary", "schema",
                          "heading", "title", "section_header", "figure", "row_batch"]
    page: int | None
    sheet_name: str | None
    heading_path: str | None   # e.g., "1. Introduction > 1.1 Overview"
    entities: dict[str, Any]
    chunk_index: int
    # Hierarchical
    parent_chunk_id: str | None
    hierarchy_level: int       # 0=doc, 1=h1, 2=h2, etc.
    bbox: list[float] | None
    layout_label: str | None
    # Semantic boundaries
    is_semantic_boundary: bool
    semantic_similarity_prev: float | None
    # Cross-chunk context
    prev_chunk_id, next_chunk_id: str | None
    prev_chunk_summary, next_chunk_summary: str | None

class ChunkMetadata(BaseModel):   # LLM-enriched metadata
    chunk_id: str
    title: str | None             # 3-8 word title
    summary: str | None           # 1-2 sentence summary
    keywords: list[str]           # 5-10 keywords
    entities: dict[str, list[str]]  # {people, organizations, dates, ...}
    category: Literal["definition","procedure","data","narrative","example","reference"] | None
    contextual_description: str | None  # Role in document
    temporal_context: str | None        # Date applicability
    enriched_at: datetime | None

class ChunkQuestion(BaseModel):   # Hypothetical question for multi-vector retrieval
    id: int | None
    chunk_id: str
    question: str
    vector_id: str | None

class VectorEmbedding(BaseModel): # Tracks what was embedded
    id: str
    chunk_id: str
    vector_type: Literal["main", "summary", "question"]
    source_text: str | None
    question_id: int | None
```

**File:** `api/models/search_result.py`

```python
class SearchRequest(BaseModel):
    query: str                 # 1-1000 chars
    filters: dict | None       # doc_type, entities
    limit: int = 10            # 1-100
    mode: Literal["auto", "retrieval", "synthesis"] = "auto"

class SearchResultItem(BaseModel):
    document_id, file_name, file_type, detected_doc_type: str
    chunk_text: str            # Matching chunk (truncated to 500 chars)
    chunk_id: str
    score: float               # 0-1
    page, sheet_name, heading_path: optional
    highlights: list[str]      # Snippets with query matches
    entities: dict
    temporal_context: str | None

class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    answer: str | None         # LLM-synthesized answer
    total_results: int
    latency_ms: float
    cache_hit: bool
    response_tier: Literal["cache", "retrieval", "synthesis"]
    sources: list[SourceInfo]  # Unique source documents used
```

**Processing status state machine:**

```
pending → layout_detected → text_extracted → reviewed → chunked → enriched → indexed
                                                  ↗
                                          (skip review)
```

---

### 3.4 API Routes

#### Health Router (`api/api/routes/health.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{status: "healthy", version: "1.0.0"}` |

#### Search Router (`api/api/routes/search.py`)

| Method | Path | Request | Description |
|--------|------|---------|-------------|
| POST | `/search` | `SearchRequest` body | Main search endpoint. Delegates to `ResponseGenerator`. Supports 3 modes: `auto`, `retrieval`, `synthesis`. |

#### Documents Router (`api/api/routes/documents.py`)

| Method | Path | Parameters | Description |
|--------|------|-----------|-------------|
| GET | `/documents` | `skip`, `limit` query params | Paginated document listing |
| GET | `/documents/{document_id}` | - | Full document details |

#### Stats Router (`api/api/routes/stats.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stats` | System statistics: doc/chunk counts, vector counts, index sizes, cache entries |

#### Admin Router (`api/api/routes/admin.py`, prefix: `/admin`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/reindex` | Trigger full reindex (background task) |
| GET | `/admin/reindex/status` | Poll reindex progress: idle/in_progress/completed/failed |
| POST | `/admin/clear-cache` | Clear semantic cache |

#### Files Router (`api/api/routes/files.py`, prefix: `/files`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/files/browse`, `/files/browse/{path}` | Browse folder contents (files + subfolders) |
| POST | `/files/folder` | Create a subfolder |
| POST | `/files/upload` | Upload files (multipart, max 100MB each) |
| GET | `/files/download/{path}` | Download a file |
| GET | `/files/preview/{path}` | File preview (text for docs, JSON table data for spreadsheets) |
| DELETE | `/files/delete/{path}` | Delete file + remove from indexes |
| DELETE | `/files/folder/{path}` | Delete folder (force=true for non-empty) |

**Security:** All paths validated against the watch folder using `Path.relative_to()` to prevent directory traversal.

#### Processing Router (`api/api/routes/processing.py`, prefix: `/processing`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/processing/vlm/status` | Check VLM availability (Ollama or HuggingFace) |
| GET | `/processing/images/{doc_id}/{filename}` | Serve extracted figure/table images |
| GET | `/processing/{doc_id}/status` | Document processing status |
| POST | `/processing/{doc_id}/detect-layout` | Run DocLayout-YOLO on PDF (conf threshold) |
| GET | `/processing/{doc_id}/pages` | List all pages with detection counts |
| GET | `/processing/{doc_id}/pages/{page_num}/image` | Original page image |
| GET | `/processing/{doc_id}/pages/{page_num}/annotated` | Annotated image (filtered detections) |
| GET | `/processing/{doc_id}/pages/{page_num}/annotated-unfiltered` | Unfiltered annotated image |
| GET | `/processing/{doc_id}/pages/{page_num}/layout` | Page layout detection JSON |
| POST | `/processing/{doc_id}/extract-text` | Extract text → markdown (format-specific) |
| GET | `/processing/{doc_id}/markdown` | Get extracted + reviewed markdown |
| PUT | `/processing/{doc_id}/markdown` | Save edited markdown |
| POST | `/processing/{doc_id}/register` | Register new document (pending status) |

#### Chunking Router (`api/api/routes/chunking.py`, prefix: `/processing`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/processing/{doc_id}/chunk` | Trigger chunking (auto-selects strategy) |
| POST | `/processing/{doc_id}/enrich` | LLM-enrich all chunks |
| POST | `/processing/{doc_id}/index-vectors` | Build multi-vector index |
| GET | `/processing/{doc_id}/chunks` | List all chunks |
| GET | `/processing/{doc_id}/chunks/{chunk_id}` | Chunk detail with metadata + questions |
| GET | `/processing/{doc_id}/chunk-tree` | Hierarchical chunk tree |
| POST | `/processing/{doc_id}/test-retrieval` | Debug retrieval with full source attribution |

---

### 3.5 File Processing Pipeline

#### Layout Detection (`api/processing/layout_detector.py`)

Uses **DocLayout-YOLO** to detect document regions on PDF pages:
- Labels: title, text, table, figure, list, section_header, heading, etc.
- Each detection: `{bbox: [x1,y1,x2,y2], label, confidence}`

**Box Filtering** (`api/processing/box_filtering.py`):
- Containment removal: if box A is 85%+ inside box B, remove A
- IoU suppression: merge overlapping boxes (threshold: 0.5)
- Soft-NMS: Gaussian score decay instead of hard removal (sigma: 0.3)
- Both filtered and unfiltered results are saved for comparison

#### Page Rendering (`api/processing/page_renderer.py`)

Renders PDF pages to PNG images using PyMuPDF (`fitz`).

#### Text Extraction (`api/processing/text_extractor.py`)

PDF text extraction is layout-aware:
1. For each page, sort detected regions by reading order (top-to-bottom, left-to-right)
2. For text/heading regions: extract text using PyMuPDF
3. For figure/table regions: crop the region and send to VLM for description
4. Assemble into markdown with headings, paragraphs, and image references

**VLM Client** (`api/processing/vlm_client.py`):
- **Ollama provider**: Local inference via Ollama API (default: qwen3-vl:8b)
- **HuggingFace provider**: Cloud inference via HuggingFace API

**Non-PDF processors:**
- `docx_processor.py`: Extracts paragraphs, headings, tables → markdown
- `pptx_processor.py`: Extracts slides with text + tables → markdown
- `tabular_processor.py`: CSV/Excel → markdown description with sample data

---

### 3.6 Indexing & RAG Pipeline

#### DocumentProcessor (`api/core/document_processor.py`)

The single orchestrator for all processing. Three public step methods form the pipeline:

```python
class DocumentProcessor:
    async def chunk_document(document_id, markdown=None) -> int
    async def enrich_chunks(document_id) -> (chunks_enriched, questions_generated)
    async def index_vectors(document_id, save=True) -> dict
    async def reindex_all() -> dict
    async def remove_file(file_path, save=True) -> bool
```

**`chunk_document()` flow:**
1. Fetch document from DB
2. Detect if tabular (CSV/XLSX/XLS)
3. Delete existing chunks + vectors for this document
4. Dispatch to strategy:
   - **Tabular**: `_chunk_tabular()` → re-parses file, uses `chunker.chunk_tabular()`
   - **Paragraph**: `_chunk_paragraph()` → splits markdown into fixed-size chunks
   - **Hierarchical** (default): `_chunk_hierarchical()` → markdown-tree chunking + semantic refinement
5. Save chunks to DB, set status to `chunked`

**`enrich_chunks()` flow:**
1. Fetch all chunks for document
2. Call `chunk_enricher.enrich_batch()` (concurrent LLM calls in batches of 5)
3. Save ChunkMetadata and ChunkQuestions to DB
4. Call `rebuild_contextualized_text()` to rebuild chunk text with enrichment context
5. Persist updated contextualized_text to DB
6. Set status to `enriched`

**`index_vectors()` flow:**
1. For each chunk:
   - Embed `contextualized_text` → add to main FAISS index + BM25
   - If chunk has summary → embed → add to summary FAISS index
   - For each hypothetical question → embed → add to question FAISS index
   - Track all embeddings in `vector_embeddings` table
2. If `save=True`, persist FAISS + BM25 to disk
3. Set status to `indexed`

**`reindex_all()` flow:**
1. Clear ALL indexes (FAISS, BM25, DB)
2. Scan watch folder for supported files
3. For each file: `_reindex_single_file()` (parse → doc-enrich → chunk → enrich → index with `save=False`)
4. Save indexes once at the end

#### Chunking Strategies

**Paragraph Chunker** (`api/indexing/chunker.py`):
- Splits text by paragraphs, respects `chunk_size` (1500 chars default)
- No overlap (`chunk_overlap=0`) — context is added via LLM enrichment instead
- Tracks heading stack for `heading_path` (e.g., "1. Intro > 1.1 Overview")
- Prepends context header: file name, doc type, heading path, key entities
- Separate table chunks from inline tables

**Hierarchical Chunker** (`api/indexing/hierarchical_chunker.py`):
- Parses markdown heading structure (H1-H6) into a tree
- Each section becomes a chunk with parent-child relationships
- Respects `max_chunk_size` — splits oversized sections
- Preserves `hierarchy_level`, `parent_chunk_id`, `heading_path`
- Optionally incorporates layout detection data (bbox, layout_label)

**Semantic Chunker** (`api/indexing/semantic_chunker.py`):
- Post-processing refinement step (runs after hierarchical chunking)
- Embeds sentences within large chunks
- Detects topic shifts via cosine similarity drops (threshold: 0.72)
- Splits at semantic boundaries → marks `is_semantic_boundary=True`

**Tabular Chunker** (inside `api/indexing/chunker.py`):
- First chunk: schema description (column names, types, stats)
- Subsequent chunks: row batches (50 rows per chunk by default)
- Each batch includes column headers for context
- Content type: `row_batch`, `schema`, `summary`

#### Context Building & `rebuild_contextualized_text()`

**Module-level function** in `api/indexing/chunker.py`.

After chunk enrichment, rebuilds `contextualized_text` by prepending:
```
[Document: {file_name} | Type: {doc_type} | Section: {heading_path}]
[Context: {contextual_description}]
[Previous: {prev_chunk_summary}]
[Next: {next_chunk_summary}]
[Key Entities: entity1=value1, entity2=value2]

{original_chunk_text}
```

This enriched text is what gets embedded for vector search.

#### Chunk Enrichment (`api/indexing/chunk_enricher.py`)

Uses LLM to extract per-chunk metadata:
- **Title**: 3-8 word descriptive title
- **Summary**: 1-2 sentence summary
- **Keywords**: 5-10 relevant terms
- **Entities**: Insurance-domain entities (policy numbers, claim numbers, dates, amounts, etc.)
- **Category**: definition / procedure / data / narrative / example / reference
- **Hypothetical questions**: 5 questions this chunk could answer (with document context for specificity)
- **Contextual description**: 2-3 sentences about chunk's role
- **Temporal context**: Date applicability if present

Processes chunks in concurrent batches (`enrichment_batch_size=5`) with 0.5s delay between batches for rate limiting.

#### Multi-Vector Index (`api/indexing/multi_vector_index.py`)

Manages **3 separate FAISS indices**:

| Index | Contains | ID Format |
|-------|----------|-----------|
| **main** | Embeddings of `contextualized_text` | `{chunk_id}` |
| **summary** | Embeddings of chunk summaries | `{chunk_id}_summary` |
| **question** | Embeddings of hypothetical questions | `q_{chunk_id}_{question_id}` |

- Uses `ThreadPoolExecutor(max_workers=3)` for parallel FAISS searches
- Question-to-chunk mapping maintained in `_question_to_chunk` dict
- Save/load: 3 FAISS files + 3 ID maps + 1 question-chunk mapping JSON

**Single VectorIndex** (`api/indexing/vector_index.py`):
- Wraps FAISS `IndexFlatIP` (inner product / cosine similarity)
- ID mapping: chunk_id ↔ FAISS integer ID
- Supports add, search (with optional ID filtering), remove, batch operations

#### BM25 Keyword Index (`api/indexing/keyword_index.py`)

- Uses `rank_bm25` library
- **Tokenization**: lowercase, strip punctuation, remove stopwords, min token length=2
- **Insurance-domain synonym expansion**: Expands "policy" → ["coverage", "plan", "contract"]
- **Insurance acronym expansion**: Expands "coi" → "certificate of insurance"
- Supports `search_with_keywords()` for debug (returns matched keywords per result)

#### Metadata Store (`api/indexing/metadata_store.py`)

Async SQLite store using `aiosqlite`. Single persistent read connection + separate write connections with `PRAGMA journal_mode=WAL`.

Key patterns:
- `_get_db()`: Reuses persistent read connection
- `_write_db()`: Creates new connection per write (context manager)
- Auto-migration: Checks existing columns via `PRAGMA table_info`, adds missing columns

---

### 3.7 Search System

#### Enhanced Hybrid Search (`api/search/enhanced_hybrid_search.py`)

The core search algorithm uses **parallel multi-source retrieval + RRF fusion**:

```
┌─────────────────────────────────────────────────────────────┐
│                     Query Processing                         │
│  1. Embed query ONCE (reused everywhere)                     │
│  2. Check semantic cache                                     │
│  3. Process query intent (doc_type, synthesis need, type)    │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│              Parallel Retrieval Phase                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │    BM25       │  │          HyDE + Vector Search        │ │
│  │  (keyword)    │  │  ┌─────────────────────┐             │ │
│  │   runs in     │  │  │ LLM generates       │             │ │
│  │  parallel     │  │  │ hypothetical doc     │             │ │
│  │  with HyDE    │  │  │ → blend embedding    │             │ │
│  │              │  │  └──────────┬──────────┘             │ │
│  │              │  │             ▼                         │ │
│  │              │  │  ┌────────────────────┐               │ │
│  │              │  │  │ 3 FAISS searches   │               │ │
│  │              │  │  │ (parallel threads) │               │ │
│  │              │  │  │ main + summary +   │               │ │
│  │              │  │  │ question indices   │               │ │
│  │              │  │  └────────────────────┘               │ │
│  └──────────────┘  └──────────────────────────────────────┘ │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│                  RRF Fusion                                   │
│                                                              │
│  For each source (main_vector, summary_vector,               │
│                    question_vector, bm25):                    │
│    rrf_score = weight / (k_constant + rank)                  │
│                                                              │
│  Combined score = Σ rrf_scores across all sources            │
│  Sort by combined score descending                           │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│              Optional Post-Processing                        │
│                                                              │
│  Cross-encoder re-ranking (if enabled):                      │
│    Score chunks with cross-encoder, blend with RRF scores    │
│                                                              │
│  MMR diversity (if enabled):                                 │
│    Select diverse results (lambda=0.7 relevance/diversity)   │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│              Result Building                                 │
│                                                              │
│  Batch DB queries (not N+1):                                 │
│    - get_chunks_by_ids(top_chunk_ids)                        │
│    - get_documents_by_ids(doc_ids)                           │
│    - get_chunk_metadata_batch(chunk_ids)                     │
│                                                              │
│  Build SearchResultItem list with scores, highlights,        │
│  entities, temporal_context, source attribution              │
└─────────────────────────────────────────────────────────────┘
```

#### HyDE Query Expansion (`api/search/hyde.py`)

**Hypothetical Document Embeddings** — generates a fake document that would answer the query, embeds it, and blends with the original query embedding:

1. LLM generates a 150-250 word hypothetical document
2. Embed both query and hypothetical
3. Blend: `combined = (1 - alpha) * query_emb + alpha * hypo_emb`
4. L2-normalize the result

**Adaptive alpha** (based on query length):
- 1-3 words → `alpha_min` (0.3) — trust query more
- 4-8 words with `?` → midpoint (0.45)
- 4-10 words → `alpha_max * 0.8` (0.48)
- 10+ words → `alpha_max` (0.6) — trust hypothetical more

#### Query Processor (`api/search/query_processor.py`)

Heuristic-based query understanding:
- **Doc type detection**: Keyword matching against insurance-domain vocabulary
- **Synthesis detection**: Keywords like "summarize", "compare", "explain", or questions (`?`), or long queries (10+ words)
- **Query type classification**: factual / exploratory / comparative / aggregation
- Optional LLM-based understanding for complex queries (`use_llm=False` by default)

#### Response Generator (`api/search/response_generator.py`)

Orchestrates the full search-to-response pipeline:

1. **Embed query** once (reused in cache check, search, and cache store)
2. **Check semantic cache** — if hit, return cached response
3. **Process query** → extract intent, doc_type filter, entity filters
4. **Execute search** via `enhanced_hybrid_search`
5. **Determine mode**: if `auto`, use synthesis if `needs_synthesis=True`
6. **Synthesize** (if synthesis mode): send top chunks to LLM with synthesis prompt
7. **Cache response** (store embedding + response for future similarity matches)
8. Return `SearchResponse`

**Response tiers:**
- `cache`: Exact or semantically similar query was cached
- `retrieval`: Return matching chunks without LLM synthesis
- `synthesis`: LLM generates a comprehensive answer from top chunks

#### Semantic Cache (`api/search/semantic_cache.py`)

LRU cache with vectorized semantic similarity:
- **Lookup**: Matrix multiply `query_emb @ all_cached_embeddings.T` → find best match
- **Threshold**: similarity ≥ 0.92 counts as cache hit
- **TTL**: 3600s (1 hour)
- **Capacity**: 2000 entries (LRU eviction)
- **Invalidation**: Per-document (when a document is re-indexed)
- **Persistence**: Pickle to disk on shutdown, load on startup

---

### 3.8 LLM Integration

#### LLM Client (`api/enrichment/llm_client.py`)

Abstract `LLMClient` base class with two implementations:

**OpenAIClient:**
- Uses `AsyncOpenAI` from the `openai` package
- Supports all GPT-4/4.1/4o/5 models
- Logs token usage and estimated cost per call

**GeminiClient:**
- Uses `google.generativeai` SDK
- Supports Gemini 1.5/2.0/2.5 models
- Similar cost logging

**Factory functions:**
- `get_llm_client()` — base model
- `get_enrichment_llm_client()` — uses `enrichment_model` override if set
- `get_synthesis_llm_client()` — uses `synthesis_model` override if set

**`complete_json()`:** Shared method that calls `complete()` then parses JSON from response, handling markdown code blocks.

#### Entity Extractor (`api/enrichment/entity_extractor.py`)

Document-level enrichment:
- Takes `ParseResult` → sends first 6000 chars to LLM
- Returns `EnrichmentResult`: document_type, summary, entities, key_topics, table_descriptions
- Separate prompts for documents vs tabular data

#### Prompt Templates (`api/enrichment/prompts.py`)

| Prompt | Purpose |
|--------|---------|
| `DOCUMENT_ENRICHMENT_SYSTEM_PROMPT` | System prompt for document analysis |
| `DOCUMENT_ENRICHMENT_PROMPT` | Extract doc_type, summary, entities, topics |
| `TABULAR_ENRICHMENT_PROMPT` | Analyze tabular data with column types + stats |
| `QUERY_UNDERSTANDING_PROMPT` | Parse search query intent |
| `RESPONSE_SYNTHESIS_PROMPT` | Generate answer from search results |

---

## 4. Frontend Deep-Dive

### Tech Stack

- **React 18** + TypeScript
- **Vite** (build tool, dev server with API proxy)
- **TailwindCSS** (utility-first styling)
- **React Router** (client-side routing)

### Pages

| Page | Route | Description |
|------|-------|-------------|
| **Search** | `/` | Search bar, mode selector (auto/retrieval/synthesis), results with highlights, synthesized answers, source attribution |
| **Documents** | `/documents` | Document listing with type, summary, index status |
| **DocumentDetail** | `/documents/:id` | Full document view: processing status, layout preview, markdown editor, chunk tree, chunk metadata, retrieval debug |
| **FileBrowser** | `/files` | File/folder browser: upload, download, create folder, delete, inline preview, processing status per file |
| **Admin** | `/admin` | System stats (docs, chunks, vectors, cache), trigger reindex, clear cache |

### Key Components

| Component | Purpose |
|-----------|---------|
| `SearchBar` | Query input with mode selection |
| `SearchResults` | Result cards with score, highlights, heading path |
| `LayoutPreview` | Side-by-side original vs annotated page images (filtered + unfiltered) |
| `MarkdownEditor` | Edit/review extracted markdown before chunking |
| `ChunkTreeView` | Hierarchical tree visualization of chunks |
| `ChunkMetadataPanel` | View chunk title, summary, keywords, entities, questions |
| `RetrievalDebugPanel` | View per-source scores, RRF fusion breakdown |
| `ProcessingStatus` | Step-by-step pipeline progress indicator |
| `FileUploadZone` | Drag-and-drop multi-file upload |
| `SourcePreviewModal` | View chunk text from search result sources |

### API Client (`ui/src/api/client.ts`)

A typed `APIClient` class wrapping `fetch()`:
- Base URL: `/api` in dev (Vite proxy), empty in production (nginx proxies)
- All response types defined as TypeScript interfaces
- Methods for: search, documents, stats, admin, file browser, processing, chunking, retrieval debug

---

## 5. Data Flow Diagrams

### Document Processing Pipeline

```
                     ┌─────────────┐
                     │   Upload     │
                     │  (via UI or  │
                     │  watch dir)  │
                     └──────┬──────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │  Register Pending │  POST /files/upload
                  │  (create DB entry)│  → creates doc with status="pending"
                  └────────┬─────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         PDF files              Non-PDF files
              │                    │
              ▼                    │
    ┌──────────────────┐           │
    │  Layout Detection │           │
    │  (DocLayout-YOLO) │           │
    │  + Box Filtering  │           │
    │  status="layout_  │           │
    │  detected"        │           │
    └────────┬─────────┘           │
             │                     │
             ▼                     ▼
    ┌────────────────────────────────────┐
    │       Text Extraction              │
    │  PDF: layout-aware + VLM           │
    │  DOCX: paragraphs + tables         │
    │  PPTX: slides + tables             │
    │  CSV/Excel: schema + sample data   │
    │  → generates markdown              │
    │  status="text_extracted"           │
    └────────────────┬───────────────────┘
                     │
                     ▼ (optional)
           ┌──────────────────┐
           │  Markdown Review  │  User edits markdown in UI
           │  status="reviewed"│
           └────────┬─────────┘
                    │
                    ▼
          ┌──────────────────┐
          │   Chunk Document  │  POST /processing/{id}/chunk
          │                   │
          │  Strategy:        │
          │  - hierarchical   │  (default: markdown tree + semantic refinement)
          │  - paragraph      │  (fixed-size splits)
          │  - tabular        │  (auto for CSV/Excel)
          │                   │
          │  status="chunked" │
          └────────┬─────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  Enrich Chunks   │  POST /processing/{id}/enrich
         │                   │
         │  Per chunk (LLM): │
         │  - title, summary │
         │  - keywords       │
         │  - entities       │
         │  - category       │
         │  - 5 questions    │
         │  - context desc   │
         │  - temporal ctx   │
         │                   │
         │  Then rebuild     │
         │  contextualized_  │
         │  text             │
         │                   │
         │  status="enriched"│
         └────────┬─────────┘
                  │
                  ▼
        ┌──────────────────┐
        │  Index Vectors    │  POST /processing/{id}/index-vectors
        │                   │
        │  For each chunk:  │
        │  - main → FAISS   │  (contextualized_text embedding)
        │  - summary → FAISS│  (chunk summary embedding)
        │  - questions →    │  (hypothetical question embeddings)
        │    FAISS          │
        │  - text → BM25    │  (original text, tokenized)
        │                   │
        │  status="indexed" │
        └──────────────────┘
```

### Search-Time Flow

```
              ┌──────────────┐
              │  User Query  │
              └──────┬───────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Embed query ONCE│  (all-mpnet-base-v2, 768d)
            └────────┬────────┘
                     │
                     ▼
           ┌──────────────────┐
           │  Semantic Cache   │  cosine similarity ≥ 0.92?
           │  Check            │──── HIT ──→ Return cached response
           └────────┬─────────┘
                    │ MISS
                    ▼
          ┌──────────────────┐
          │  Query Processing │
          │  - detect doc_type│
          │  - detect query   │
          │    type           │
          │  - needs_synthesis│
          └────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
  ┌───────────┐       ┌──────────────┐
  │   BM25    │       │    HyDE      │   (runs in parallel)
  │  keyword  │       │  LLM gen →   │
  │  search   │       │  embed →     │
  │           │       │  blend with  │
  │           │       │  query emb   │
  └─────┬─────┘       └──────┬───────┘
        │                     │
        │                     ▼
        │            ┌────────────────┐
        │            │ 3x FAISS search│  (parallel via thread pool)
        │            │ main + summary │
        │            │ + question     │
        │            └────────┬───────┘
        │                     │
        └──────────┬──────────┘
                   │
                   ▼
          ┌────────────────┐
          │  RRF Fusion     │  Weighted rank aggregation
          │  (k=30)         │  across 4 sources
          └────────┬───────┘
                   │
                   ▼ (optional)
          ┌────────────────┐
          │  Re-rank (CE)  │  Cross-encoder scoring
          │  + MMR         │  Diversity selection
          └────────┬───────┘
                   │
                   ▼
          ┌────────────────┐
          │ Batch DB fetch  │  chunks + docs + metadata
          └────────┬───────┘
                   │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
  ┌──────────────┐  ┌─────────────────┐
  │  Retrieval   │  │   Synthesis     │
  │  (return     │  │  (LLM generates │
  │   chunks)    │  │   answer from   │
  │              │  │   top chunks)   │
  └──────┬───────┘  └───────┬─────────┘
         │                  │
         └────────┬─────────┘
                  │
                  ▼
         ┌────────────────┐
         │  Cache response │
         │  Return to user │
         └────────────────┘
```

---

## 6. Database Schema

All tables live in a single SQLite database (`data/sqlite/metadata.db`).

### `documents`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | SHA256 of file path |
| `file_path` | TEXT UNIQUE NOT NULL | Absolute file path |
| `file_name` | TEXT NOT NULL | Display name |
| `file_type` | TEXT NOT NULL | Extension (pdf, docx, ...) |
| `file_hash` | TEXT NOT NULL | SHA256 of file content |
| `detected_doc_type` | TEXT | LLM-detected type |
| `summary` | TEXT | LLM-generated summary |
| `entities` | TEXT (JSON) | Key-value entities |
| `key_topics` | TEXT (JSON) | Topic list |
| `table_descriptions` | TEXT (JSON) | Table descriptions |
| `indexed_at` | TEXT | ISO timestamp |
| `sheet_names` | TEXT (JSON) | Excel sheet names |
| `column_schema` | TEXT (JSON) | Column headers + types |
| `row_count` | INTEGER | Row count for tabular |
| `date_range` | TEXT | Date range if detected |
| `processing_status` | TEXT | pending/layout_detected/text_extracted/reviewed/chunked/enriched/indexed |
| `layout_data` | TEXT (JSON) | Layout detection results |
| `extracted_markdown` | TEXT | Generated markdown |
| `reviewed_markdown` | TEXT | User-edited markdown |
| `page_count` | INTEGER | Page count (PDF/PPTX) |

### `document_entities`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK AUTOINCREMENT | |
| `document_id` | TEXT FK → documents | |
| `entity_key` | TEXT NOT NULL | Entity key |
| `entity_value` | TEXT NOT NULL | Entity value |

### `chunks`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | Chunk ID |
| `document_id` | TEXT FK → documents | Parent document |
| `text` | TEXT NOT NULL | Original text |
| `contextualized_text` | TEXT NOT NULL | Enriched text (embedded) |
| `content_type` | TEXT | paragraph/table/list/heading/row_batch/... |
| `page` | INTEGER | Page number (PDF) |
| `sheet_name` | TEXT | Sheet name (Excel) |
| `heading_path` | TEXT | Section hierarchy |
| `entities` | TEXT (JSON) | Chunk-level entities |
| `chunk_index` | INTEGER | Position in document |
| `parent_chunk_id` | TEXT FK → chunks | Parent chunk |
| `hierarchy_level` | INTEGER | 0=doc, 1=h1, 2=h2... |
| `bbox` | TEXT (JSON) | Bounding box from layout |
| `layout_label` | TEXT | Layout detection label |
| `is_semantic_boundary` | INTEGER | 0/1 |
| `semantic_similarity_prev` | REAL | Similarity with previous |

### `chunk_metadata`

| Column | Type | Description |
|--------|------|-------------|
| `chunk_id` | TEXT PK FK → chunks | |
| `title` | TEXT | 3-8 word title |
| `summary` | TEXT | 1-2 sentence summary |
| `keywords` | TEXT (JSON) | Keyword list |
| `entities` | TEXT (JSON) | Structured entities |
| `category` | TEXT | definition/procedure/data/... |
| `contextual_description` | TEXT | Role in document |
| `temporal_context` | TEXT | Date applicability |
| `enriched_at` | TEXT | ISO timestamp |

### `chunk_questions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK AUTOINCREMENT | |
| `chunk_id` | TEXT FK → chunks | |
| `question` | TEXT NOT NULL | Hypothetical question |
| `vector_id` | TEXT | ID in question FAISS index |

### `vector_embeddings`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | Vector ID (matches FAISS) |
| `chunk_id` | TEXT FK → chunks | |
| `vector_type` | TEXT NOT NULL | main/summary/question |
| `source_text` | TEXT | Text that was embedded |
| `question_id` | INTEGER | For question vectors |

### `document_pages`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | `{doc_id}_page_{num}` |
| `document_id` | TEXT FK → documents | |
| `page_number` | INTEGER NOT NULL | 1-indexed |
| `image_path` | TEXT | Path to page PNG |
| `annotated_image_path` | TEXT | Filtered annotations |
| `unfiltered_annotated_image_path` | TEXT | Unfiltered annotations |
| `layout_json` | TEXT (JSON) | Filtered detections |
| `unfiltered_layout_json` | TEXT (JSON) | Unfiltered detections |
| `filter_stats_json` | TEXT (JSON) | Box filter statistics |
| `extracted_text` | TEXT | OCR/VLM text |
| UNIQUE | `(document_id, page_number)` | |

### Indexes

```sql
idx_doc_file_path     ON documents(file_path)
idx_doc_type          ON documents(detected_doc_type)
idx_doc_status        ON documents(processing_status)
idx_entity_key        ON document_entities(entity_key)
idx_chunks_doc_id     ON chunks(document_id)
idx_chunks_parent     ON chunks(parent_chunk_id)
idx_chunks_hierarchy  ON chunks(document_id, hierarchy_level)
idx_pages_doc_id      ON document_pages(document_id)
idx_chunk_meta_id     ON chunk_metadata(chunk_id)
idx_questions_chunk   ON chunk_questions(chunk_id)
idx_vectors_chunk     ON vector_embeddings(chunk_id)
idx_vectors_type      ON vector_embeddings(vector_type)
```

---

## 7. Configuration Reference

Complete `.env` reference (see `api/.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `WATCH_FOLDER` | `./documents` | Directory to scan for files |
| `DATA_FOLDER` | `./data` | Data storage root |
| `DATABASE_PATH` | `./data/sqlite/metadata.db` | SQLite database path |
| `LLM_PROVIDER` | `openai` | `openai` or `gemini` |
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default OpenAI model |
| `GEMINI_API_KEY` | - | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Default Gemini model |
| `ENRICHMENT_MODEL` | (empty=use base) | Model override for chunk enrichment |
| `SYNTHESIS_MODEL` | (empty=use base) | Model override for answer synthesis |
| `VLM_PROVIDER` | `ollama` | `ollama` or `huggingface` |
| `USE_VLM_EXTRACTION` | `true` | Use VLM for figure/table extraction |
| `VLM_FALLBACK_OCR` | `true` | Fall back to OCR if VLM fails |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3-vl:8b` | Ollama VLM model |
| `OLLAMA_TIMEOUT` | `120.0` | Ollama request timeout (seconds) |
| `HUGGINGFACE_API_KEY` | - | HuggingFace API key |
| `HUGGINGFACE_VLM_MODEL` | `Qwen/Qwen2.5-VL-32B-Instruct:fireworks-ai` | HF VLM model |
| `HUGGINGFACE_TIMEOUT` | `60.0` | HuggingFace request timeout |
| `BOX_FILTER_ENABLED` | `true` | Enable layout box filtering |
| `BOX_FILTER_CONTAINMENT_THRESHOLD` | `0.85` | Remove if 85%+ contained |
| `BOX_FILTER_IOU_THRESHOLD` | `0.5` | Suppress if IoU > 50% |
| `BOX_FILTER_CLASS_AGNOSTIC` | `true` | Apply across classes |
| `BOX_FILTER_USE_SOFT_NMS` | `true` | Use Soft-NMS |
| `BOX_FILTER_SOFT_NMS_SIGMA` | `0.3` | Gaussian sigma |
| `EMBEDDING_MODEL` | `all-mpnet-base-v2` | Sentence-transformers model |
| `EMBEDDING_DIMENSION` | `768` | Embedding vector size |
| `CHUNK_SIZE` | `1500` | Target chunk size (chars) |
| `CHUNK_OVERLAP` | `0` | Overlap between chunks |
| `MAX_CHUNK_SIZE` | `2500` | Maximum chunk size |
| `ENABLE_SEMANTIC_CHUNKING` | `true` | Enable semantic refinement |
| `SEMANTIC_SIMILARITY_THRESHOLD` | `0.72` | Topic shift detection |
| `ENABLE_CHUNK_LINKS` | `true` | Cross-chunk context |
| `CHUNKING_STRATEGY` | `hierarchical` | `hierarchical` or `paragraph` |
| `CSV_ROWS_PER_CHUNK` | `50` | Rows per tabular chunk |
| `CSV_MAX_ROWS_TO_INDEX` | `0` | Row cap (0=no limit) |
| `ENRICHMENT_BATCH_SIZE` | `5` | Concurrent LLM calls |
| `QUESTIONS_PER_CHUNK` | `5` | Hypothetical questions |
| `SEARCH_TOP_K` | `10` | Default result count |
| `RRF_K_CONSTANT` | `30` | RRF smoothing constant |
| `MULTI_VECTOR_WEIGHTS_MAIN` | `0.40` | Main vector weight |
| `MULTI_VECTOR_WEIGHTS_QUESTION` | `0.20` | Question vector weight |
| `MULTI_VECTOR_WEIGHTS_BM25` | `0.25` | BM25 weight |
| `MULTI_VECTOR_WEIGHTS_SUMMARY` | `0.15` | Summary vector weight |
| `ENABLE_HYDE` | `true` | Enable HyDE query expansion |
| `HYDE_NUM_HYPOTHETICALS` | `1` | Number of hypotheticals |
| `HYDE_ALPHA` | `0.5` | Fixed alpha |
| `HYDE_ALPHA_MIN` | `0.3` | Adaptive min alpha |
| `HYDE_ALPHA_MAX` | `0.6` | Adaptive max alpha |
| `HYDE_ADAPTIVE` | `true` | Use adaptive alpha |
| `CACHE_TTL_SECONDS` | `3600` | Cache TTL |
| `CACHE_SIMILARITY_THRESHOLD` | `0.92` | Cache match threshold |
| `CACHE_MAX_ENTRIES` | `2000` | Max cached queries |
| `RERANKER_ENABLED` | `false` | Enable cross-encoder |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model |
| `RERANKER_TOP_K` | `20` | Candidates to re-rank |
| `RERANKER_BLEND_RATIO` | `0.7` | Reranker vs original |
| `MMR_ENABLED` | `false` | Enable diversity ranking |
| `MMR_LAMBDA` | `0.7` | Relevance vs diversity |
| `BM25_EXPAND_SYNONYMS` | `true` | Domain synonym expansion |
| `BM25_MIN_TOKEN_LENGTH` | `2` | Min token length |
| `QUERY_EXPAND_SYNONYMS` | `true` | Query synonym expansion |
| `QUERY_SPELL_CHECK` | `false` | Spell correction |
| `SYNTHESIS_MAX_TOKENS` | `1500` | LLM answer max tokens |
| `SYNTHESIS_TEMPERATURE` | `0.1` | LLM answer temperature |
| `SYNTHESIS_MAX_CHUNKS` | `10` | Chunks sent to LLM |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## 8. Deployment

### Docker Compose

```yaml
# docker-compose.yml
services:
  search-api:          # Python FastAPI backend
    build: ./api       # Dockerfile: python:3.11-slim
    ports: ["8000:8000"]
    volumes:
      - ./documents:/documents:ro    # Watch folder (read-only)
      - search-data:/data            # Persistent data volume
    environment:       # All env vars from .env
    healthcheck:       # curl http://localhost:8000/health

  web-ui:              # React frontend
    build: ./ui        # Multi-stage: node:20-alpine → nginx:alpine
    ports: ["3000:3000"]
    depends_on: search-api (healthy)

volumes:
  search-data:         # Named volume for indexes + DB
```

### API Dockerfile (`api/Dockerfile`)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data/faiss /data/bm25 /data/sqlite /data/cache
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### UI Dockerfile (`ui/Dockerfile`)

```dockerfile
# Build stage
FROM node:20-alpine AS builder
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
```

### Local Development Setup

**Backend:**
```bash
cd api
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # Edit with your API keys
python main.py          # Starts on http://localhost:8000
```

**Frontend:**
```bash
cd ui
npm install
npm run dev             # Starts on http://localhost:5173 (proxies /api to :8000)
```

**Prerequisites:**
- Python 3.11+
- Node.js 20+
- OpenAI API key (or Gemini API key)
- (Optional) Ollama running locally for VLM-based PDF extraction

---

## 9. Key Design Decisions

### Why Multi-Vector Retrieval?

Single-embedding search misses queries that match on different semantic dimensions. Three indices capture:
- **Main**: Contextualized full text (broad semantic match)
- **Summary**: Short summaries (good for overview queries)
- **Question**: Hypothetical questions (bridges query-document gap)

RRF fusion combines them without needing learned weights — just ranked position matters.

### Why No Chunk Overlap?

Traditional overlap (e.g., 200 chars) creates redundant embeddings. Instead, this system uses:
- **LLM enrichment** to add context (document metadata, section info, neighboring chunk summaries)
- **`contextualized_text`** that prepends rich context to every chunk before embedding
- This is more effective than blind overlap and doesn't waste index space

### Why Hierarchical Chunking as Default?

Paragraph-based chunking ignores document structure. The hierarchical approach:
- Preserves heading hierarchy (parent-child relationships)
- Maintains section context via `heading_path`
- Enables tree-based visualization in the UI
- Supports semantic refinement to split topic-shifting sections

### Why HyDE?

Short queries like "claim process" have a semantic gap with long document passages. HyDE generates a hypothetical answer document, embeds it, and blends with the query embedding. This bridges the gap between query and document embedding spaces. Adaptive alpha trusts the hypothetical more for complex queries.

### Why BM25 Alongside Vectors?

Exact keyword matching catches things embeddings miss — especially proper nouns, policy numbers, acronyms, and domain-specific terms. The BM25 index includes insurance-domain synonym expansion for better recall.

### Why SQLite Instead of Postgres?

This is a LAN-deployed system designed for simplicity:
- Zero infrastructure (no separate DB server)
- WAL mode for concurrent reads during writes
- Sufficient for the expected document volumes (hundreds to low thousands)
- Single file for backup/migration

### Why Manual Processing Workflow?

Instead of auto-processing uploads, the system uses a step-by-step workflow:
1. Users can review layout detection results
2. Users can edit extracted markdown before chunking
3. Each step (chunk → enrich → index) can be triggered independently
4. This allows quality control at each stage

### Why Separate Enrichment and Synthesis Models?

Different LLM tasks have different requirements:
- **Enrichment** (chunk metadata): can use a cheaper/faster model (e.g., `gpt-4.1-nano`)
- **Synthesis** (answer generation): benefits from a more capable model (e.g., `gpt-4.1-mini`)
- Model overrides are configurable via `ENRICHMENT_MODEL` and `SYNTHESIS_MODEL`
