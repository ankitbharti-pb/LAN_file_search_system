# Configuration Flow Diagrams

This document provides visual flow diagrams showing how each process is configured in the LAN File Search System, including current settings and all available configuration options.

## Table of Contents
1. [Document Processing Flow](#1-document-processing-flow)
2. [Indexing Flow](#2-indexing-flow)
3. [Search Flow](#3-search-flow)
4. [Synthesis Flow](#4-synthesis-flow)
5. [Complete Configuration Reference](#5-complete-configuration-reference)
6. [Configuration Profiles](#6-configuration-profiles)

---

## 1. Document Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DOCUMENT PROCESSING FLOW                                    │
│                              ────────────────────────                                    │
│                                                                                          │
│  Shows how documents are processed from input to indexed chunks with all config points  │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────────┐
                                    │    INPUT FILE    │
                                    │  ─────────────   │
                                    │  PDF / DOCX /    │
                                    │  PPTX / CSV /    │
                                    │  XLSX / XLS      │
                                    └────────┬─────────┘
                                             │
                                             ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  DECISION: use_vlm_extraction                          ║
                        ║  ─────────────────────────────                         ║
                        ║  CURRENT VALUE: True                                   ║
                        ║  ENV VAR: USE_VLM_EXTRACTION                           ║
                        ║                                                        ║
                        ║  OPTIONS:                                              ║
                        ║  • True  → Use Vision Language Model for extraction   ║
                        ║  • False → Use direct text parsing (PyMuPDF, etc.)    ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         │                                                      │
                   True  ▼                                                False ▼
        ┌────────────────────────────────┐                    ┌────────────────────────────────┐
        │      VLM EXTRACTION PATH       │                    │      DIRECT PARSING PATH       │
        │      ────────────────────      │                    │      ────────────────────      │
        │                                │                    │                                │
        │  ╔════════════════════════╗    │                    │  • PyMuPDF (PDF)               │
        │  ║ vlm_provider           ║    │                    │  • python-docx (DOCX)          │
        │  ║ ───────────────        ║    │                    │  • python-pptx (PPTX)          │
        │  ║ CURRENT: ollama        ║    │                    │  • pandas (CSV/Excel)          │
        │  ║ ENV: VLM_PROVIDER      ║    │                    │                                │
        │  ║                        ║    │                    │  No VLM overhead               │
        │  ║ OPTIONS:               ║    │                    │  Faster but less accurate      │
        │  ║ • ollama (local)       ║    │                    │  for complex layouts           │
        │  ║ • huggingface (cloud)  ║    │                    │                                │
        │  ╚════════════════════════╝    │                    └───────────────┬────────────────┘
        │                                │                                    │
        │  ┌──────────────────────────┐  │                                    │
        │  │ IF ollama:               │  │                                    │
        │  │ ───────────              │  │                                    │
        │  │ ollama_base_url:         │  │                                    │
        │  │   http://localhost:11434 │  │                                    │
        │  │ ollama_model:            │  │                                    │
        │  │   qwen3-vl:8b            │  │                                    │
        │  │ ollama_timeout:          │  │                                    │
        │  │   120.0 seconds          │  │                                    │
        │  └──────────────────────────┘  │                                    │
        │                                │                                    │
        │  ┌──────────────────────────┐  │                                    │
        │  │ IF huggingface:          │  │                                    │
        │  │ ─────────────            │  │                                    │
        │  │ huggingface_api_key:     │  │                                    │
        │  │   (from env)             │  │                                    │
        │  │ huggingface_vlm_model:   │  │                                    │
        │  │   Qwen/Qwen2.5-VL-32B-   │  │                                    │
        │  │   Instruct:fireworks-ai  │  │                                    │
        │  │ huggingface_timeout:     │  │                                    │
        │  │   60.0 seconds           │  │                                    │
        │  └──────────────────────────┘  │                                    │
        │                                │                                    │
        │  Extracts:                     │                                    │
        │  • Tables (as Markdown)        │                                    │
        │  • Figures (descriptions)      │                                    │
        │  • Formulas (LaTeX)            │                                    │
        │  • Text (OCR)                  │                                    │
        └───────────────┬────────────────┘                                    │
                        │                                                      │
                        └──────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  DECISION: vlm_fallback_ocr (if VLM fails)             ║
                        ║  ─────────────────────────────────────────             ║
                        ║  CURRENT VALUE: True                                   ║
                        ║  ENV VAR: VLM_FALLBACK_OCR                             ║
                        ║                                                        ║
                        ║  OPTIONS:                                              ║
                        ║  • True  → Fall back to OCR if VLM extraction fails   ║
                        ║  • False → Fail if VLM extraction fails               ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                                                    ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  DECISION: box_filter_enabled                          ║
                        ║  ─────────────────────────                             ║
                        ║  CURRENT VALUE: True                                   ║
                        ║  ENV VAR: BOX_FILTER_ENABLED                           ║
                        ║                                                        ║
                        ║  OPTIONS:                                              ║
                        ║  • True  → Filter overlapping bounding boxes           ║
                        ║  • False → Keep all detected boxes (may have dups)    ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         │                                                      │
                   True  ▼                                                False ▼
        ┌────────────────────────────────┐                    ┌────────────────────────────────┐
        │       BOX FILTERING            │                    │      NO BOX FILTERING          │
        │       ─────────────            │                    │      ────────────────          │
        │                                │                    │                                │
        │  box_filter_containment_       │                    │  Raw bounding boxes            │
        │  threshold: 0.85               │                    │  passed through                │
        │  (Remove if 85%+ contained)    │                    │                                │
        │                                │                    │  May have duplicates           │
        │  box_filter_iou_threshold:     │                    │  and overlapping regions       │
        │  0.5                           │                    │                                │
        │  (Suppress if IoU > 50%)       │                    │                                │
        │                                │                    │                                │
        │  box_filter_class_agnostic:    │                    │                                │
        │  True                          │                    │                                │
        │  (Apply across classes)        │                    │                                │
        │                                │                    │                                │
        │  ╔════════════════════════╗    │                    │                                │
        │  ║ box_filter_use_soft_   ║    │                    │                                │
        │  ║ nms: True              ║    │                    │                                │
        │  ║ ───────────────────    ║    │                    │                                │
        │  ║ OPTIONS:               ║    │                    │                                │
        │  ║ • True → Soft-NMS      ║    │                    │                                │
        │  ║   (Gaussian decay)     ║    │                    │                                │
        │  ║ • False → Hard NMS     ║    │                    │                                │
        │  ║   (Binary removal)     ║    │                    │                                │
        │  ║                        ║    │                    │                                │
        │  ║ soft_nms_sigma: 0.3    ║    │                    │                                │
        │  ╚════════════════════════╝    │                    │                                │
        └───────────────┬────────────────┘                    └───────────────┬────────────────┘
                        │                                                      │
                        └──────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                            ┌──────────────────────────────────────────┐
                            │           LLM ENRICHMENT                 │
                            │           ──────────────                 │
                            │                                          │
                            │  ╔════════════════════════════════════╗  │
                            │  ║ llm_provider                       ║  │
                            │  ║ ────────────                       ║  │
                            │  ║ CURRENT: openai                    ║  │
                            │  ║ ENV: LLM_PROVIDER                  ║  │
                            │  ║                                    ║  │
                            │  ║ OPTIONS:                           ║  │
                            │  ║ • openai → OpenAI API              ║  │
                            │  ║ • gemini → Google Gemini API       ║  │
                            │  ╚════════════════════════════════════╝  │
                            │                                          │
                            │  ┌─────────────────┐ ┌─────────────────┐ │
                            │  │ IF openai:      │ │ IF gemini:      │ │
                            │  │ ───────────     │ │ ──────────      │ │
                            │  │ openai_model:   │ │ gemini_model:   │ │
                            │  │  gpt-4o-mini    │ │  gemini-1.5-    │ │
                            │  │                 │ │  flash          │ │
                            │  │ Alt models:     │ │                 │ │
                            │  │ • gpt-4         │ │ Alt models:     │ │
                            │  │ • gpt-4o        │ │ • gemini-1.5-   │ │
                            │  │ • gpt-3.5-turbo │ │   pro           │ │
                            │  └─────────────────┘ └─────────────────┘ │
                            │                                          │
                            │  Extracts:                               │
                            │  • document_type                         │
                            │  • summary (2-3 sentences)               │
                            │  • entities (key-value pairs)            │
                            │  • key_topics                            │
                            │  • table_descriptions                    │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  DECISION: enable_semantic_chunking                    ║
                        ║  ───────────────────────────────                       ║
                        ║  CURRENT VALUE: True                                   ║
                        ║  ENV VAR: ENABLE_SEMANTIC_CHUNKING                     ║
                        ║                                                        ║
                        ║  OPTIONS:                                              ║
                        ║  • True  → Topic-aware chunking with embedding sim    ║
                        ║  • False → Size-based paragraph chunking only         ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         │                                                      │
                   True  ▼                                                False ▼
        ┌────────────────────────────────┐                    ┌────────────────────────────────┐
        │      SEMANTIC CHUNKING         │                    │       BASIC CHUNKING           │
        │      ──────────────────        │                    │       ──────────────           │
        │                                │                    │                                │
        │  1. Hierarchical Chunking      │                    │  chunk_size: 1500              │
        │     (markdown tree parsing)    │                    │  (target chunk size in chars)  │
        │                                │                    │                                │
        │  2. Semantic Refinement        │                    │  chunk_overlap: 200            │
        │     at topic boundaries        │                    │  (configured but not active)   │
        │                                │                    │                                │
        │  ┌──────────────────────────┐  │                    │  Splits at:                    │
        │  │ chunk_size: 1500         │  │                    │  • Paragraph boundaries        │
        │  │ (target size)            │  │                    │  • Sentence boundaries         │
        │  │                          │  │                    │    (if paragraph too large)    │
        │  │ max_chunk_size: 2500     │  │                    │                                │
        │  │ (max allowed size)       │  │                    │                                │
        │  │                          │  │                    │                                │
        │  │ semantic_similarity_     │  │                    │                                │
        │  │ threshold: 0.80          │  │                    │                                │
        │  │ (topic change detection) │  │                    │                                │
        │  │                          │  │                    │                                │
        │  │ Higher = cleaner splits  │  │                    │                                │
        │  │ Lower = more splits      │  │                    │                                │
        │  └──────────────────────────┘  │                    │                                │
        │                                │                    │                                │
        │  Preserves:                    │                    │                                │
        │  • Heading hierarchy           │                    │                                │
        │  • Parent-child relationships  │                    │                                │
        │  • Content type labels         │                    │                                │
        └───────────────┬────────────────┘                    └───────────────┬────────────────┘
                        │                                                      │
                        └──────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                            ┌──────────────────────────────────────────┐
                            │          CHUNK ENRICHMENT                │
                            │          ────────────────                │
                            │                                          │
                            │  enrichment_batch_size: 5                │
                            │  (concurrent LLM calls per batch)        │
                            │                                          │
                            │  questions_per_chunk: 3                  │
                            │  (hypothetical questions generated)      │
                            │                                          │
                            │  Extracts per chunk:                     │
                            │  • title (3-8 words)                     │
                            │  • summary (1-2 sentences)               │
                            │  • keywords (5-10)                       │
                            │  • entities                              │
                            │  • category                              │
                            │  • contextual_description                │
                            │  • 3-5 hypothetical questions            │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                                    ┌──────────────────────┐
                                    │    OUTPUT: CHUNKS    │
                                    │    ─────────────     │
                                    │  Ready for indexing  │
                                    └──────────────────────┘
```

---

## 2. Indexing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   INDEXING FLOW                                          │
│                                   ─────────────                                          │
│                                                                                          │
│  Shows how chunks are converted to searchable indices with all configuration points     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────────┐
                                    │  ENRICHED CHUNKS │
                                    │  ──────────────  │
                                    │  From processing │
                                    │  pipeline        │
                                    └────────┬─────────┘
                                             │
                                             ▼
                            ┌──────────────────────────────────────────┐
                            │          EMBEDDING GENERATION            │
                            │          ────────────────────            │
                            │                                          │
                            │  ╔════════════════════════════════════╗  │
                            │  ║ embedding_model                    ║  │
                            │  ║ ───────────────                    ║  │
                            │  ║ CURRENT: all-mpnet-base-v2         ║  │
                            │  ║ ENV: EMBEDDING_MODEL               ║  │
                            │  ║                                    ║  │
                            │  ║ OPTIONS:                           ║  │
                            │  ║ • all-mpnet-base-v2 (768d, MTEB    ║  │
                            │  ║   61.0) ← RECOMMENDED              ║  │
                            │  ║ • all-MiniLM-L6-v2 (384d, MTEB     ║  │
                            │  ║   56.3) ← Lighter/faster           ║  │
                            │  ║ • Any sentence-transformers model  ║  │
                            │  ╚════════════════════════════════════╝  │
                            │                                          │
                            │  ┌────────────────────────────────────┐  │
                            │  │ embedding_dimension: 768           │  │
                            │  │ (must match model output size)     │  │
                            │  │                                    │  │
                            │  │ Normalization: L2                  │  │
                            │  │ (for cosine similarity via dot)    │  │
                            │  │                                    │  │
                            │  │ Batch size: 32 (internal)          │  │
                            │  └────────────────────────────────────┘  │
                            │                                          │
                            │  Embeds:                                 │
                            │  • contextualized_text (main)            │
                            │  • chunk summaries (summary)             │
                            │  • hypothetical questions (question)     │
                            └─────────────────────┬────────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
    ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
    │     MAIN VECTOR INDEX     │ │   SUMMARY VECTOR INDEX    │ │  QUESTION VECTOR INDEX    │
    │     ─────────────────     │ │   ────────────────────    │ │  ──────────────────────   │
    │                           │ │                           │ │                           │
    │  FAISS IndexFlatIP        │ │  FAISS IndexFlatIP        │ │  FAISS IndexFlatIP        │
    │  (inner product)          │ │  (inner product)          │ │  (inner product)          │
    │                           │ │                           │ │                           │
    │  Content:                 │ │  Content:                 │ │  Content:                 │
    │  contextualized_text      │ │  LLM-generated chunk      │ │  Hypothetical questions   │
    │  (text + doc context)     │ │  summaries                │ │  (3-5 per chunk)          │
    │                           │ │                           │ │                           │
    │  ID format: chunk_id      │ │  ID: {chunk_id}_summary   │ │  ID: question_id          │
    │                           │ │                           │ │                           │
    │  Storage:                 │ │  Storage:                 │ │  Storage:                 │
    │  ./data/faiss/            │ │  ./data/faiss/            │ │  ./data/faiss/            │
    │  main_index.faiss         │ │  summary_index.faiss      │ │  question_index.faiss     │
    │  main_id_map.json         │ │  summary_id_map.json      │ │  question_id_map.json     │
    │                           │ │                           │ │  question_chunk_map.json  │
    └───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘
                    │                             │                             │
                    └─────────────────────────────┼─────────────────────────────┘
                                                  │
                                                  ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  MULTI-VECTOR WEIGHTS (for RRF fusion)                 ║
                        ║  ─────────────────────────────────────                 ║
                        ║                                                        ║
                        ║  multi_vector_weights_main: 0.40 (40%)                 ║
                        ║  ENV: MULTI_VECTOR_WEIGHTS_MAIN                        ║
                        ║  ↑ Contextualized text - highest semantic weight       ║
                        ║                                                        ║
                        ║  multi_vector_weights_question: 0.20 (20%)             ║
                        ║  ENV: MULTI_VECTOR_WEIGHTS_QUESTION                    ║
                        ║  ↑ Query-to-question matching                          ║
                        ║                                                        ║
                        ║  multi_vector_weights_summary: 0.15 (15%)              ║
                        ║  ENV: MULTI_VECTOR_WEIGHTS_SUMMARY                     ║
                        ║  ↑ Broad topic matching                                ║
                        ║                                                        ║
                        ║  TOTAL VECTOR WEIGHT: 75%                              ║
                        ╚═══════════════════════════════════════════════════════╝
                                                  │
                                                  │
                    ┌─────────────────────────────┴─────────────────────────────┐
                    │                                                           │
                    ▼                                                           ▼
    ┌───────────────────────────────────────┐           ┌───────────────────────────────────────┐
    │         BM25 KEYWORD INDEX            │           │         SQLITE METADATA               │
    │         ──────────────────            │           │         ────────────────              │
    │                                       │           │                                       │
    │  Algorithm: BM25 Okapi                │           │  database_path:                       │
    │  (rank_bm25 library)                  │           │  ./data/sqlite/metadata.db            │
    │                                       │           │                                       │
    │  Tokenization:                        │           │  Mode: WAL (Write-Ahead Logging)      │
    │  1. Lowercase                         │           │  Driver: aiosqlite (async)            │
    │  2. Remove special chars              │           │                                       │
    │  3. Split on whitespace               │           │  Tables:                              │
    │  4. Remove stopwords (140+)           │           │  • documents (metadata)               │
    │  5. Basic stemming (60+ rules)        │           │  • document_entities (filtering)      │
    │                                       │           │  • chunks (text, hierarchy)           │
    │  ╔════════════════════════════════╗   │           │  • chunk_metadata (enrichment)        │
    │  ║ multi_vector_weights_bm25:     ║   │           │  • chunk_questions (Q&A)              │
    │  ║ 0.25 (25%)                     ║   │           │  • vector_embeddings (tracking)       │
    │  ║ ENV: MULTI_VECTOR_WEIGHTS_BM25 ║   │           │  • document_pages (layout)            │
    │  ║                                ║   │           │                                       │
    │  ║ Keyword matching importance    ║   │           │                                       │
    │  ╚════════════════════════════════╝   │           │                                       │
    │                                       │           │                                       │
    │  Storage: ./data/bm25/index.pkl       │           │                                       │
    └───────────────────────────────────────┘           └───────────────────────────────────────┘
                    │                                                           │
                    └─────────────────────────────┬─────────────────────────────┘
                                                  │
                                                  ▼
                                    ┌──────────────────────┐
                                    │   INDEXED DOCUMENT   │
                                    │   ────────────────   │
                                    │  Ready for search    │
                                    └──────────────────────┘

                        ┌─────────────────────────────────────────────────┐
                        │           WEIGHT DISTRIBUTION SUMMARY           │
                        │           ───────────────────────────           │
                        │                                                 │
                        │  ┌─────────────────────────────────────────┐   │
                        │  │ Main Vector:     ████████████████ 40%   │   │
                        │  │ BM25 Keyword:    ██████████       25%   │   │
                        │  │ Question Vector: ████████         20%   │   │
                        │  │ Summary Vector:  ██████           15%   │   │
                        │  └─────────────────────────────────────────┘   │
                        │                                                 │
                        │  RRF Formula: score = weight / (60 + rank)     │
                        │  K-constant: 60 (emphasizes top ranks)         │
                        └─────────────────────────────────────────────────┘
```

---

## 3. Search Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    SEARCH FLOW                                           │
│                                    ───────────                                           │
│                                                                                          │
│  Shows the query-to-results pipeline with all configuration decision points             │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────────┐
                                    │   USER QUERY     │
                                    │   ──────────     │
                                    │  "Find invoices  │
                                    │   from 2024"     │
                                    └────────┬─────────┘
                                             │
                                             ▼
                            ┌──────────────────────────────────────────┐
                            │          QUERY PROCESSING                │
                            │          ────────────────                │
                            │                                          │
                            │  Extracts:                               │
                            │  • search_terms                          │
                            │  • doc_type_filter (invoice, report...)  │
                            │  • entity_filters                        │
                            │  • needs_synthesis (boolean)             │
                            │  • query_type (factual, exploratory...)  │
                            │                                          │
                            │  Detection patterns:                     │
                            │  • Doc types: invoice, contract, report  │
                            │  • Synthesis: summarize, explain, how... │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  CACHE CHECK (Semantic Cache)                          ║
                        ║  ────────────────────────────                          ║
                        ║                                                        ║
                        ║  cache_similarity_threshold: 0.92                      ║
                        ║  ENV: CACHE_SIMILARITY_THRESHOLD                       ║
                        ║  (92% semantic match required for cache hit)           ║
                        ║                                                        ║
                        ║  cache_ttl_seconds: 3600                               ║
                        ║  ENV: CACHE_TTL_SECONDS                                ║
                        ║  (1 hour cache lifetime)                               ║
                        ║                                                        ║
                        ║  cache_max_entries: 2000                               ║
                        ║  ENV: CACHE_MAX_ENTRIES                                ║
                        ║  (LRU eviction when exceeded)                          ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         │                                                      │
                   HIT   ▼                                                MISS  ▼
        ┌────────────────────────────────┐                    ┌────────────────────────────────┐
        │       CACHE HIT                │                    │       CACHE MISS               │
        │       ─────────                │                    │       ──────────               │
        │                                │                    │                                │
        │  Return cached response        │                    │  Proceed to search             │
        │  (fast path)                   │                    │                                │
        │                                │                    │                                │
        │  Conditions for hit:           │                    │                                │
        │  1. similarity >= 0.92         │                    │                                │
        │  2. not expired (TTL)          │                    │                                │
        │  3. docs still valid           │                    │                                │
        └────────────────────────────────┘                    └───────────────┬────────────────┘
                                                                              │
                                                                              ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  DECISION: enable_hyde                                 ║
                        ║  ─────────────────────                                 ║
                        ║  CURRENT VALUE: True                                   ║
                        ║  ENV VAR: ENABLE_HYDE                                  ║
                        ║                                                        ║
                        ║  OPTIONS:                                              ║
                        ║  • True  → Generate hypothetical document for query   ║
                        ║  • False → Direct query embedding (faster)            ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                         ┌──────────────────────────┴──────────────────────────┐
                         │                                                      │
                   True  ▼                                                False ▼
        ┌────────────────────────────────┐                    ┌────────────────────────────────┐
        │        HyDE EXPANSION          │                    │     DIRECT EMBEDDING           │
        │        ──────────────          │                    │     ────────────────           │
        │                                │                    │                                │
        │  hyde_num_hypotheticals: 1     │                    │  query_embedding =             │
        │  (usually 1 is sufficient)     │                    │    embedder.embed(query)       │
        │                                │                    │                                │
        │  1. Generate hypothetical doc  │                    │  Direct, faster approach       │
        │     (150-250 words via LLM)    │                    │  Good for simple queries       │
        │                                │                    │                                │
        │  2. Embed both query and       │                    │                                │
        │     hypothetical document      │                    │                                │
        │                                │                    │                                │
        │  3. Weighted combination:      │                    │                                │
        │     alpha = 0.6                │                    │                                │
        │     60% hypothetical +         │                    │                                │
        │     40% query embedding        │                    │                                │
        │                                │                    │                                │
        │  Better for complex/ambiguous  │                    │                                │
        │  queries                       │                    │                                │
        └───────────────┬────────────────┘                    └───────────────┬────────────────┘
                        │                                                      │
                        └──────────────────────────┬───────────────────────────┘
                                                   │
                                                   ▼
                            ┌──────────────────────────────────────────┐
                            │       MULTI-SOURCE SEARCH                │
                            │       ──────────────────                 │
                            │                                          │
                            │  search_top_k: 10                        │
                            │  ENV: SEARCH_TOP_K                       │
                            │  (search with k*3 = 30 per source)       │
                            └─────────────────────┬────────────────────┘
                                                  │
                    ┌─────────────────────────────┼─────────────────────────────┐
                    │                             │                             │
                    ▼                             ▼                             ▼
    ┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
    │   MAIN VECTOR SEARCH      │ │  SUMMARY VECTOR SEARCH    │ │  QUESTION VECTOR SEARCH   │
    │   ──────────────────      │ │  ────────────────────     │ │  ───────────────────────  │
    │                           │ │                           │ │                           │
    │  Weight: 0.40 (40%)       │ │  Weight: 0.15 (15%)       │ │  Weight: 0.20 (20%)       │
    │                           │ │                           │ │                           │
    │  Searches chunk           │ │  Searches chunk           │ │  Searches hypothetical    │
    │  contextualized_text      │ │  summaries                │ │  questions                │
    │                           │ │                           │ │                           │
    │  Best for: Semantic       │ │  Best for: Broad          │ │  Best for: Exact          │
    │  similarity matching      │ │  topic matching           │ │  question matching        │
    └───────────────┬───────────┘ └───────────────┬───────────┘ └───────────────┬───────────┘
                    │                             │                             │
                    └─────────────────────────────┼─────────────────────────────┘
                                                  │
                                                  ▼
                            ┌──────────────────────────────────────────┐
                            │        BM25 KEYWORD SEARCH               │
                            │        ───────────────────               │
                            │                                          │
                            │  Weight: 0.25 (25%)                      │
                            │                                          │
                            │  Tokenized query matching                │
                            │  Good for exact term matches             │
                            │                                          │
                            │  Complements semantic search             │
                            │  (catches keyword-specific matches)      │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                            ┌──────────────────────────────────────────┐
                            │          RRF FUSION                      │
                            │          ──────────                      │
                            │                                          │
                            │  Formula: rrf_score = weight/(60+rank)   │
                            │                                          │
                            │  Combines all 4 sources:                 │
                            │  • Main Vector  (0.40)                   │
                            │  • BM25         (0.25)                   │
                            │  • Question     (0.20)                   │
                            │  • Summary      (0.15)                   │
                            │                                          │
                            │  Sorts by combined RRF score             │
                            │  Returns top k results                   │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                            ┌──────────────────────────────────────────┐
                            │         RESULT BUILDING                  │
                            │         ───────────────                  │
                            │                                          │
                            │  For each result:                        │
                            │  • Get chunk text from SQLite            │
                            │  • Get document metadata                 │
                            │  • Create highlights (query matches)     │
                            │  • Build SearchResultItem                │
                            │                                          │
                            │  Returns: List[SearchResultItem]         │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                                    ┌──────────────────────┐
                                    │   SEARCH RESULTS     │
                                    │   ──────────────     │
                                    │  Ranked by RRF score │
                                    │  Ready for synthesis │
                                    └──────────────────────┘
```

---

## 4. Synthesis Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  SYNTHESIS FLOW                                          │
│                                  ──────────────                                          │
│                                                                                          │
│  Shows how search results are optionally synthesized into natural language answers      │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                                    ┌──────────────────┐
                                    │  SEARCH RESULTS  │
                                    │  ──────────────  │
                                    │  From search     │
                                    │  pipeline        │
                                    └────────┬─────────┘
                                             │
                                             ▼
                        ╔═══════════════════════════════════════════════════════╗
                        ║  DECISION: Response Mode                               ║
                        ║  ───────────────────────                               ║
                        ║                                                        ║
                        ║  OPTIONS:                                              ║
                        ║  • auto      → Check needs_synthesis from QueryIntent ║
                        ║  • retrieval → Return chunks only (no LLM)            ║
                        ║  • synthesis → Always generate LLM answer             ║
                        ╚═══════════════════════════╤═══════════════════════════╝
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────┐
                    │                               │                               │
              auto  ▼                         retrieval                       synthesis
        ┌───────────────────────┐                   │                               │
        │   AUTO MODE           │                   │                               │
        │   ─────────           │                   │                               │
        │                       │                   │                               │
        │  Check QueryIntent:   │                   │                               │
        │  needs_synthesis?     │                   │                               │
        │                       │                   │                               │
        │  True if query:       │                   │                               │
        │  • Contains "how"     │                   │                               │
        │  • Contains "why"     │                   │                               │
        │  • Contains "explain" │                   │                               │
        │  • Ends with "?"      │                   │                               │
        │  • > 10 words         │                   │                               │
        └───────────┬───────────┘                   │                               │
                    │                               │                               │
                    │ ┌────────────────┐            │                               │
                    ├─│ needs_synthesis│────────────┴───────────────────────────────┤
                    │ │ = True         │                                            │
                    │ └────────────────┘                                            │
                    │                                                               │
                    │ ┌────────────────┐                                            │
                    └─│ needs_synthesis│────────────────────────────┐               │
                      │ = False        │                            │               │
                      └────────────────┘                            │               │
                                                                    │               │
                         ┌──────────────────────────────────────────┴───────────────┘
                         │
                   SYNTHESIS MODE
                         │
                         ▼
                ╔════════════════════════════════════════════════════╗
                ║  LLM PROVIDER SELECTION                            ║
                ║  ───────────────────────                           ║
                ║                                                    ║
                ║  llm_provider: openai (current)                    ║
                ║  ENV: LLM_PROVIDER                                 ║
                ║                                                    ║
                ║  OPTIONS:                                          ║
                ║  • openai → OpenAI API (gpt-4o-mini)              ║
                ║  • gemini → Google Gemini (gemini-1.5-flash)      ║
                ╚═══════════════════════════╤════════════════════════╝
                                            │
                         ┌──────────────────┴──────────────────┐
                         │                                      │
                   openai▼                                gemini▼
        ┌────────────────────────────────┐    ┌────────────────────────────────┐
        │       OPENAI SYNTHESIS         │    │       GEMINI SYNTHESIS         │
        │       ────────────────         │    │       ───────────────          │
        │                                │    │                                │
        │  openai_model: gpt-4o-mini     │    │  gemini_model: gemini-1.5-     │
        │  ENV: OPENAI_MODEL             │    │  flash                         │
        │                                │    │  ENV: GEMINI_MODEL             │
        │  Alternative models:           │    │                                │
        │  • gpt-4                       │    │  Alternative models:           │
        │  • gpt-4o                      │    │  • gemini-1.5-pro              │
        │  • gpt-3.5-turbo               │    │  • gemini-1.0-pro              │
        │                                │    │                                │
        │  Temperature: 0.3              │    │  Temperature: 0.3              │
        │  (low for factual answers)     │    │  (low for factual answers)     │
        │                                │    │                                │
        │  Max tokens: 500               │    │  Max tokens: 500               │
        └───────────────┬────────────────┘    └───────────────┬────────────────┘
                        │                                      │
                        └──────────────────┬───────────────────┘
                                           │
                                           ▼
                            ┌──────────────────────────────────────────┐
                            │         SYNTHESIS PROCESS                │
                            │         ─────────────────                │
                            │                                          │
                            │  1. Format top 10 results for LLM:       │
                            │     • Document name                      │
                            │     • Document type                      │
                            │     • Section/heading path               │
                            │     • Chunk content (first 500 chars)    │
                            │     • Key entities                       │
                            │                                          │
                            │  2. Send to LLM with synthesis prompt    │
                            │                                          │
                            │  3. Extract sources with chunk counts    │
                            │                                          │
                            │  Output: Natural language answer         │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                            ┌──────────────────────────────────────────┐
                            │         CACHE STORAGE                    │
                            │         ─────────────                    │
                            │                                          │
                            │  Store response in semantic cache:       │
                            │  • Query embedding                       │
                            │  • Full response                         │
                            │  • Contributing document IDs             │
                            │  • Timestamp                             │
                            │                                          │
                            │  TTL: 3600 seconds (1 hour)              │
                            │  Max entries: 2000 (LRU)                 │
                            └─────────────────────┬────────────────────┘
                                                  │
                                                  ▼
                                    ┌──────────────────────────────┐
                                    │       SEARCH RESPONSE        │
                                    │       ───────────────        │
                                    │                              │
                                    │  • query: original query     │
                                    │  • results: ranked chunks    │
                                    │  • answer: LLM synthesis     │
                                    │  • total_results: count      │
                                    │  • latency_ms: timing        │
                                    │  • cache_hit: boolean        │
                                    │  • response_tier: mode       │
                                    │  • sources: doc references   │
                                    └──────────────────────────────┘

                                                  │
                                                  │
                                  ┌───────────────┴───────────────┐
                                  │                               │
                            RETRIEVAL MODE                        │
                                  │                               │
                                  ▼                               │
                    ┌──────────────────────────────┐              │
                    │    RETRIEVAL ONLY RESPONSE   │              │
                    │    ────────────────────────  │              │
                    │                              │              │
                    │  No LLM synthesis            │              │
                    │  Returns ranked chunks only  │              │
                    │  Faster, cheaper             │              │
                    │                              │              │
                    │  response_tier: "retrieval"  │              │
                    │  answer: null                │              │
                    └──────────────────────────────┘              │
                                                                  │
                                  ┌───────────────────────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────────┐
                    │      FINAL RESPONSE          │
                    │      ──────────────          │
                    │                              │
                    │  Returned to user            │
                    └──────────────────────────────┘
```

---

## 5. Complete Configuration Reference

### A. Path Settings

| Parameter | Type | Current Value | Environment Variable | Description |
|-----------|------|---------------|----------------------|-------------|
| `watch_folder` | Path | `./documents` | `WATCH_FOLDER` | Directory to monitor for new documents |
| `data_folder` | Path | `./data` | `DATA_FOLDER` | Root directory for all indices and caches |
| `database_path` | Path | `./data/sqlite/metadata.db` | `DATABASE_PATH` | SQLite metadata database location |

### B. LLM Settings

| Parameter | Type | Current Value | Options | Environment Variable | Description |
|-----------|------|---------------|---------|----------------------|-------------|
| `llm_provider` | Literal | `openai` | `openai`, `gemini` | `LLM_PROVIDER` | Primary LLM provider for enrichment and synthesis |
| `openai_api_key` | str | *(from env)* | - | `OPENAI_API_KEY` | OpenAI API authentication key |
| `openai_model` | str | `gpt-4o-mini` | `gpt-4`, `gpt-4o`, `gpt-3.5-turbo` | `OPENAI_MODEL` | OpenAI model for LLM tasks |
| `gemini_api_key` | str | *(from env)* | - | `GEMINI_API_KEY` | Google Gemini API key |
| `gemini_model` | str | `gemini-1.5-flash` | `gemini-1.5-pro`, `gemini-1.0-pro` | `GEMINI_MODEL` | Gemini model for LLM tasks |

### C. VLM (Vision Language Model) Settings

| Parameter | Type | Current Value | Options | Environment Variable | Description |
|-----------|------|---------------|---------|----------------------|-------------|
| `vlm_provider` | Literal | `ollama` | `ollama`, `huggingface` | `VLM_PROVIDER` | Vision model provider for document analysis |
| `use_vlm_extraction` | bool | `True` | `True`, `False` | `USE_VLM_EXTRACTION` | Enable VLM-based visual content extraction |
| `vlm_fallback_ocr` | bool | `True` | `True`, `False` | `VLM_FALLBACK_OCR` | Fall back to OCR if VLM fails |
| `ollama_base_url` | str | `http://localhost:11434` | Any URL | `OLLAMA_BASE_URL` | Ollama service URL (local inference) |
| `ollama_model` | str | `qwen3-vl:8b` | Any Ollama vision model | `OLLAMA_MODEL` | Vision model name in Ollama |
| `ollama_timeout` | float | `120.0` | 1.0 - 600.0 | `OLLAMA_TIMEOUT` | Request timeout in seconds |
| `huggingface_api_key` | str | *(from env)* | - | `HUGGINGFACE_API_KEY` | HuggingFace API key |
| `huggingface_vlm_model` | str | `Qwen/Qwen2.5-VL-32B-Instruct:fireworks-ai` | Any HF vision model | `HUGGINGFACE_VLM_MODEL` | HuggingFace vision model identifier |
| `huggingface_timeout` | float | `60.0` | 1.0 - 300.0 | `HUGGINGFACE_TIMEOUT` | Request timeout in seconds |

### D. Box Filtering Settings

| Parameter | Type | Current Value | Range | Environment Variable | Description |
|-----------|------|---------------|-------|----------------------|-------------|
| `box_filter_enabled` | bool | `True` | `True`, `False` | `BOX_FILTER_ENABLED` | Enable bounding box filtering |
| `box_filter_containment_threshold` | float | `0.85` | 0.0 - 1.0 | `BOX_FILTER_CONTAINMENT_THRESHOLD` | Remove if 85%+ contained in another box |
| `box_filter_iou_threshold` | float | `0.5` | 0.0 - 1.0 | `BOX_FILTER_IOU_THRESHOLD` | Suppress if IoU > 50% |
| `box_filter_class_agnostic` | bool | `True` | `True`, `False` | `BOX_FILTER_CLASS_AGNOSTIC` | Apply filtering across different classes |
| `box_filter_use_soft_nms` | bool | `True` | `True`, `False` | `BOX_FILTER_USE_SOFT_NMS` | Use Soft-NMS (Gaussian) vs hard removal |
| `box_filter_soft_nms_sigma` | float | `0.3` | 0.01 - 1.0 | `BOX_FILTER_SOFT_NMS_SIGMA` | Gaussian sigma for Soft-NMS |

### E. Embedding Settings

| Parameter | Type | Current Value | Options | Environment Variable | Description |
|-----------|------|---------------|---------|----------------------|-------------|
| `embedding_model` | str | `all-mpnet-base-v2` | See below | `EMBEDDING_MODEL` | Sentence transformer model |
| `embedding_dimension` | int | `768` | Model-dependent | `EMBEDDING_DIMENSION` | Embedding vector dimension |

**Embedding Model Options:**
| Model | Dimension | MTEB Score | Notes |
|-------|-----------|------------|-------|
| `all-mpnet-base-v2` | 768 | 61.0 | **Recommended** - Best quality |
| `all-MiniLM-L6-v2` | 384 | 56.3 | Lighter, faster |
| `all-MiniLM-L12-v2` | 384 | 59.0 | Balance |
| `paraphrase-multilingual-mpnet-base-v2` | 768 | 57.0 | Multilingual |

### F. Chunking Settings

| Parameter | Type | Current Value | Range | Environment Variable | Description |
|-----------|------|---------------|-------|----------------------|-------------|
| `chunk_size` | int | `1500` | 256 - 4000 | `CHUNK_SIZE` | Target chunk size in characters (~300 tokens) |
| `chunk_overlap` | int | `200` | 0 - 500 | `CHUNK_OVERLAP` | Overlap between chunks (configured but not active) |
| `max_chunk_size` | int | `2500` | 512 - 5000 | `MAX_CHUNK_SIZE` | Maximum chunk size for semantic chunking |
| `enable_semantic_chunking` | bool | `True` | `True`, `False` | `ENABLE_SEMANTIC_CHUNKING` | Enable topic-aware semantic chunking |
| `semantic_similarity_threshold` | float | `0.80` | 0.5 - 0.95 | `SEMANTIC_SIMILARITY_THRESHOLD` | Topic change detection threshold |

**Chunking Strategy Guide:**
| Goal | Recommended Settings |
|------|---------------------|
| Better context | `chunk_size=2000`, `max_chunk_size=3000` |
| More precise | `chunk_size=512`, `max_chunk_size=1000` |
| Faster processing | `enable_semantic_chunking=False` |
| Cleaner boundaries | `semantic_similarity_threshold=0.85` |

### G. Cache Settings

| Parameter | Type | Current Value | Range | Environment Variable | Description |
|-----------|------|---------------|-------|----------------------|-------------|
| `cache_ttl_seconds` | int | `3600` | 60 - 86400 | `CACHE_TTL_SECONDS` | Cache entry lifetime (1 hour default) |
| `cache_similarity_threshold` | float | `0.92` | 0.8 - 0.99 | `CACHE_SIMILARITY_THRESHOLD` | Semantic similarity for cache hit |
| `cache_max_entries` | int | `2000` | 100 - 50000 | `CACHE_MAX_ENTRIES` | Maximum cached queries (LRU eviction) |

**Cache Tuning Guide:**
| Goal | Recommended Settings |
|------|---------------------|
| More cache hits | `cache_similarity_threshold=0.88`, `cache_ttl_seconds=7200` |
| Fresher results | `cache_ttl_seconds=1800`, `cache_similarity_threshold=0.95` |
| Lower memory | `cache_max_entries=500` |

### H. Search Settings

| Parameter | Type | Current Value | Range | Environment Variable | Description |
|-----------|------|---------------|-------|----------------------|-------------|
| `search_top_k` | int | `10` | 1 - 100 | `SEARCH_TOP_K` | Default number of results to return |
| `hybrid_alpha` | float | `0.5` | 0.0 - 1.0 | `HYBRID_ALPHA` | Legacy weight parameter (not actively used) |

### I. HyDE Settings

| Parameter | Type | Current Value | Options | Environment Variable | Description |
|-----------|------|---------------|---------|----------------------|-------------|
| `enable_hyde` | bool | `True` | `True`, `False` | `ENABLE_HYDE` | Enable HyDE query expansion |
| `hyde_num_hypotheticals` | int | `1` | 1 - 5 | `HYDE_NUM_HYPOTHETICALS` | Number of hypothetical documents to generate |

**HyDE Configuration Guide:**
| Goal | Recommended Settings |
|------|---------------------|
| Better complex queries | `enable_hyde=True`, `hyde_num_hypotheticals=1` |
| Faster simple queries | `enable_hyde=False` |
| Maximum retrieval | `enable_hyde=True`, `hyde_num_hypotheticals=3` |

### J. Enrichment Settings

| Parameter | Type | Current Value | Range | Environment Variable | Description |
|-----------|------|---------------|-------|----------------------|-------------|
| `enrichment_batch_size` | int | `5` | 1 - 20 | `ENRICHMENT_BATCH_SIZE` | Concurrent LLM calls per batch |
| `questions_per_chunk` | int | `3` | 1 - 10 | `QUESTIONS_PER_CHUNK` | Hypothetical questions generated per chunk |

### K. Multi-Vector Weight Settings

| Parameter | Type | Current Value | Range | Environment Variable | Description |
|-----------|------|---------------|-------|----------------------|-------------|
| `multi_vector_weights_main` | float | `0.40` | 0.0 - 1.0 | `MULTI_VECTOR_WEIGHTS_MAIN` | Weight for contextualized text embedding |
| `multi_vector_weights_question` | float | `0.20` | 0.0 - 1.0 | `MULTI_VECTOR_WEIGHTS_QUESTION` | Weight for Q&A embeddings |
| `multi_vector_weights_bm25` | float | `0.25` | 0.0 - 1.0 | `MULTI_VECTOR_WEIGHTS_BM25` | Weight for keyword/BM25 matching |
| `multi_vector_weights_summary` | float | `0.15` | 0.0 - 1.0 | `MULTI_VECTOR_WEIGHTS_SUMMARY` | Weight for chunk summary embeddings |

**Weight Distribution Presets:**
| Preset | Main | BM25 | Question | Summary | Best For |
|--------|------|------|----------|---------|----------|
| Default (Balanced) | 0.40 | 0.25 | 0.20 | 0.15 | General use |
| Semantic Focus | 0.50 | 0.15 | 0.20 | 0.15 | Conceptual queries |
| Keyword Focus | 0.30 | 0.40 | 0.15 | 0.15 | Technical/exact terms |
| Question Match | 0.30 | 0.20 | 0.35 | 0.15 | Q&A style queries |

### L. Server Settings

| Parameter | Type | Current Value | Options | Environment Variable | Description |
|-----------|------|---------------|---------|----------------------|-------------|
| `host` | str | `0.0.0.0` | Any IP | `HOST` | FastAPI server bind address |
| `port` | int | `8000` | 1-65535 | `PORT` | FastAPI server port |
| `log_level` | str | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `LOG_LEVEL` | Logging verbosity |

---

## 6. Configuration Profiles

### Profile 1: High Performance (Best Quality)

```bash
# .env file
EMBEDDING_MODEL=all-mpnet-base-v2
CHUNK_SIZE=2000
MAX_CHUNK_SIZE=3000
ENABLE_SEMANTIC_CHUNKING=true
SEMANTIC_SIMILARITY_THRESHOLD=0.75
SEARCH_TOP_K=20
ENABLE_HYDE=true
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
VLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3-vl:8b
```

### Profile 2: Lightweight (Speed Optimized)

```bash
# .env file
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=1000
MAX_CHUNK_SIZE=1500
ENABLE_SEMANTIC_CHUNKING=false
SEARCH_TOP_K=10
ENABLE_HYDE=false
CACHE_TTL_SECONDS=7200
CACHE_SIMILARITY_THRESHOLD=0.88
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-1.5-flash
USE_VLM_EXTRACTION=false
```

### Profile 3: Local Only (Privacy Focused)

```bash
# .env file
VLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5vl:3b
OLLAMA_TIMEOUT=250.0
ENABLE_HYDE=false
USE_VLM_EXTRACTION=true
VLM_FALLBACK_OCR=true
# Note: LLM enrichment still requires API key
```

### Profile 4: Maximum Caching

```bash
# .env file
CACHE_TTL_SECONDS=86400
CACHE_SIMILARITY_THRESHOLD=0.85
CACHE_MAX_ENTRIES=10000
ENABLE_HYDE=true
SEARCH_TOP_K=15
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           CONFIGURATION QUICK REFERENCE                                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘

  DOCUMENT PROCESSING                     SEARCH & RETRIEVAL
  ────────────────────                    ──────────────────
  use_vlm_extraction    = True            enable_hyde           = True
  vlm_provider          = ollama          search_top_k          = 10
  vlm_fallback_ocr      = True            cache_ttl_seconds     = 3600
  box_filter_enabled    = True            cache_similarity      = 0.92

  CHUNKING                                MULTI-VECTOR WEIGHTS
  ────────                                ────────────────────
  chunk_size            = 1500            main_vector           = 0.40
  max_chunk_size        = 2500            bm25                  = 0.25
  enable_semantic       = True            question              = 0.20
  semantic_threshold    = 0.80            summary               = 0.15

  EMBEDDING                               LLM PROVIDERS
  ─────────                               ─────────────
  model                 = mpnet-v2        llm_provider          = openai
  dimension             = 768             openai_model          = gpt-4o-mini
                                          gemini_model          = gemini-1.5-flash

  ENRICHMENT                              SERVER
  ──────────                              ──────
  batch_size            = 5               host                  = 0.0.0.0
  questions_per_chunk   = 3               port                  = 8000
                                          log_level             = INFO

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  All settings can be overridden via environment variables (UPPERCASE with underscores) │
│  Example: ENABLE_HYDE=false CHUNK_SIZE=2000 python -m api.main                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

*Configuration file location: `api/config/settings.py`*
*Environment file location: `api/.env`*
