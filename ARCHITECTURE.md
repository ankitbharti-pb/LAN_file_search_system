# LAN File Search System - Complete Architecture Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Chunking Architecture](#2-chunking-architecture)
3. [Enrichment Pipeline](#3-enrichment-pipeline)
4. [Indexing System](#4-indexing-system)
5. [Retrieval System](#5-retrieval-system)
6. [Response Synthesis](#6-response-synthesis)
7. [Data Flow Diagrams](#7-data-flow-diagrams)
8. [Configuration Reference](#8-configuration-reference)
9. [Storage Structure](#9-storage-structure)
10. [Key File Reference](#10-key-file-reference)

---

## 1. System Overview

This system implements a **Multi-Vector RAG (Retrieval-Augmented Generation)** architecture designed for enterprise document search across a LAN.

### Core Components
- **4-Tier Hybrid Search**: Main Vector + Summary Vector + Question Vector + BM25 Keyword
- **RRF Fusion**: Reciprocal Rank Fusion for combining search results
- **LLM-Powered Enrichment**: Document and chunk-level metadata extraction
- **LLM Synthesis**: Intelligent answer generation from retrieved context
- **Semantic Caching**: Query-level caching with embedding similarity matching

### Supported File Types
- **Documents**: PDF, DOCX, PPTX
- **Tabular Data**: CSV, XLSX, XLS

---

## 2. Chunking Architecture

The system implements **three chunking strategies** that can be used individually or in combination.

### 2.1 Basic Chunker

**File**: `api/indexing/chunker.py`

**Purpose**: Structure-aware paragraph-based chunking with document context preservation.

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `chunk_size` | 1500 chars | Target chunk size (~300 tokens) |
| `chunk_overlap` | 200 chars | Configured but not actively used |

#### Processing Flow

**For Documents (PDF, DOCX, PPTX)** - `chunk_document()` method:
1. Iterate through paragraphs from ParseResult
2. Detect headings and update heading stack for context
3. Split text by paragraph boundaries (`\n\n`)
4. Accumulate paragraphs until `chunk_size` reached
5. If paragraph exceeds `chunk_size`, split by sentences (`.`, `?`, `!`)
6. Process tables with descriptions (headers + first 5 rows)
7. Create summary chunk if enrichment available
8. Prepend document context to each chunk

**For Tabular Files (CSV, Excel)** - `chunk_tabular()` method:
1. Create file-level summary chunk (content_type: "summary")
2. Create schema chunk with column names and data types (content_type: "schema")
3. For Excel: Create per-sheet chunks with sheet name, columns, row count
4. Create content chunks from text representation

#### Context Prefix Format
Every chunk gets a context prefix prepended before embedding:
```
Document: {file_name}
Type: {detected_doc_type}
Section: {heading_path}
Key info: {entity1=value1, entity2=value2, ...}

{actual_chunk_text}
```

#### Text Splitting Logic

**`_split_text()` method** (lines 260-288):
```
1. Split by double newlines (paragraphs)
2. Accumulate paragraphs up to chunk_size
3. If adding paragraph exceeds chunk_size:
   - Save accumulated chunk
   - If paragraph > chunk_size, split by sentences
   - Otherwise, start new chunk with this paragraph
```

**`_split_long_paragraph()` method** (lines 290-313):
```
1. Split by sentence boundaries (., ?, !)
2. Accumulate sentences until reaching chunk_size
3. Create new chunk when threshold exceeded
```

---

### 2.2 Hierarchical Chunker

**File**: `api/indexing/hierarchical_chunker.py`

**Purpose**: Structure-aware chunking that respects markdown hierarchy and layout detection.

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `max_chunk_size` | 2500 chars | Maximum chunk size |
| `min_chunk_size` | 100 chars | Minimum meaningful chunk |

#### Data Structures

**MarkdownNode**:
```python
class MarkdownNode:
    level: int              # 0=root, 1=h1, 2=h2, etc.
    heading: Optional[str]  # Heading text if applicable
    content: str            # Content under this heading
    children: List[MarkdownNode]
    node_type: str          # "root", "heading", "paragraph", "table", "list", "figure", "code"
```

**LayoutBox** (from layout detection):
```python
class LayoutBox:
    label: str              # "title", "text", "table", "figure", etc.
    bbox: List[float]       # [x1, y1, x2, y2] bounding box
    page: int               # Page number
    text: str               # Detected text
```

#### Processing Flow

**`chunk_document()` method** (lines 47-89):
1. Parse markdown into tree structure using `_parse_markdown_tree()`
2. Integrate layout detection bounding boxes if available
3. Convert tree to chunks using `_tree_to_chunks()`
4. Set parent-child relationships via `parent_chunk_id`
5. Map content types based on hierarchy level and node type

**Markdown Tree Parsing** - `_parse_markdown_tree()`:
- Detects markdown headers (`#`, `##`, `###`, etc.)
- Preserves parent-child hierarchy using stack-based approach
- Identifies special content types:
  - Tables: Lines starting with `|`
  - Code blocks: Triple backticks (```)
  - Lists: Lines starting with `-`, `*`, or numbers
  - Figures: Markdown/HTML image syntax

**Tree to Chunks Conversion** - `_tree_to_chunks()`:
- Recursively converts tree nodes to Chunk objects
- Links chunks via `parent_chunk_id` for tree traversal
- Splits large content using `_split_content()`

#### Content Type Mapping
| Hierarchy Level | Node Type | Content Type |
|-----------------|-----------|--------------|
| Level 1 | heading | "title" |
| Level 2+ | heading | "section_header" |
| Any | table | "table" |
| Any | list | "list" |
| Any | figure | "figure" |
| Any | code | "paragraph" |
| Default | - | "paragraph" |

#### Size Management

**`_split_content()` method** (lines 321-362):
```
1. If content ≤ max_chunk_size: return as-is
2. Split by paragraph boundaries (regex: \n\n+)
3. Accumulate paragraphs until reaching max_chunk_size
4. If paragraph > max_chunk_size: split by sentences
5. Sentence regex: (?<=[.!?])\s+
```

---

### 2.3 Semantic Chunker

**File**: `api/indexing/semantic_chunker.py`

**Purpose**: Refines chunks by detecting topic changes using embedding similarity.

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `similarity_threshold` | 0.80 | Cosine similarity threshold for topic breaks |
| Min chunk size | 50 chars | Minimum meaningful segment |

#### Processing Flow

**`detect_breakpoints()` method** (lines 33-65):
1. Split text into sentences
2. Embed each sentence using the Embedder
3. Calculate cosine similarity between consecutive sentences
4. Identify breakpoints where similarity < threshold (0.80)
5. Return list of breakpoint indices

**`refine_chunks()` method** (lines 67-106):
1. Take hierarchical chunks as input
2. For each chunk larger than `max_chunk_size`:
   - Detect semantic breakpoints in chunk text
   - Split chunk at breakpoint locations
   - Only split if resulting segments are meaningful (≥50 chars)
3. Preserve original chunk metadata and hierarchy
4. Mark chunks with `is_semantic_boundary = True` at split points
5. Add `semantic_similarity_prev` score to each chunk

#### Sentence Splitting
Uses regex pattern for sentence detection:
- Endings: `.`, `?`, `!` followed by uppercase letter
- Newline boundaries
- Minimum 10-char sentences (filters very short fragments)

---

### 2.4 Chunk Data Model

**File**: `api/models/chunk.py`

```python
class Chunk(BaseModel):
    # Core fields
    id: str                          # 16-char SHA256 hash prefix
    document_id: str                 # Parent document ID
    text: str                        # Original content
    contextualized_text: str         # Text + document context (gets embedded)

    # Content classification
    content_type: Literal[
        "paragraph", "table", "list", "summary", "schema",
        "heading", "title", "section_header", "figure"
    ]

    # Location tracking
    page: Optional[int]              # For PDFs
    sheet_name: Optional[str]        # For Excel
    heading_path: Optional[str]      # Hierarchical section path (e.g., "1. Intro > 1.1 Overview")
    chunk_index: int                 # Position in document

    # Hierarchical structure
    parent_chunk_id: Optional[str]   # Parent in hierarchy
    hierarchy_level: int             # 0=doc, 1=h1, 2=h2, etc.

    # Layout detection
    bbox: Optional[List[float]]      # [x1, y1, x2, y2] bounding box
    layout_label: Optional[str]      # "title", "text", "table", "figure"

    # Semantic information
    is_semantic_boundary: bool       # Marks semantic split points
    semantic_similarity_prev: Optional[float]  # Similarity with previous chunk

    # Entities
    entities: Dict[str, Any]         # Document-level entities
```

---

## 3. Enrichment Pipeline

The enrichment pipeline extracts structured metadata using LLMs at both document and chunk levels.

### 3.1 Document-Level Enrichment

**File**: `api/enrichment/entity_extractor.py`

**Class**: `EntityExtractor`

#### Extracted Metadata
| Field | Description |
|-------|-------------|
| `document_type` | LLM-detected type (invoice, report, contract, etc.) |
| `summary` | 2-3 sentence document summary |
| `entities` | Dynamic key-value pairs (context-dependent) |
| `key_topics` | List of main topics covered |
| `table_descriptions` | Natural language descriptions of tables |

#### Processing Logic

**`enrich()` method**:
- Routes to `_enrich_document()` for PDF, Word, PowerPoint
- Routes to `_enrich_tabular()` for CSV, Excel
- Max 6000 characters sent to LLM

**Document Enrichment Prompt** extracts:
```json
{
  "document_type": "invoice|report|contract|...",
  "summary": "2-3 sentence summary",
  "entities": {"key1": "value1", "key2": "value2"},
  "key_topics": ["topic1", "topic2"],
  "table_descriptions": ["Table 1 shows...", "Table 2 contains..."]
}
```

**Tabular Enrichment** handles:
- Column descriptions and data types
- Date ranges if date columns present
- Key metrics and aggregations

---

### 3.2 Chunk-Level Enrichment

**File**: `api/indexing/chunk_enricher.py`

**Class**: `ChunkEnricher`

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `enrichment_batch_size` | 5 | Concurrent LLM calls per batch |
| `questions_per_chunk` | 3-5 | Hypothetical questions per chunk |
| Rate limit delay | 0.5s | Delay between batches |

#### Extracted Metadata

**ChunkMetadata Model**:
```python
class ChunkMetadata(BaseModel):
    chunk_id: str
    title: str                      # 3-8 word title
    summary: str                    # 1-2 sentence summary
    keywords: List[str]             # 5-10 keywords/phrases
    entities: Dict[str, List[str]]  # {people, organizations, dates, amounts, locations}
    category: Literal[
        "definition", "procedure", "data",
        "narrative", "example", "reference"
    ]
    contextual_description: str     # 2-3 sentences explaining role in document
    enriched_at: datetime
```

**ChunkQuestion Model**:
```python
class ChunkQuestion(BaseModel):
    id: Optional[int]               # Auto-increment
    chunk_id: str
    question: str                   # Hypothetical question chunk answers
    vector_id: Optional[str]        # Maps to question index
```

#### Enrichment Prompt Structure
```
You are an expert document analyzer. Given this chunk from a document:

File: {file_name}
Type: {doc_type}
Section: {heading_path}

Chunk text:
{chunk_text (max 3000 chars)}

Extract the following as JSON:
1. title: Brief 3-8 word title
2. summary: 1-2 sentence summary
3. keywords: 5-10 relevant keywords
4. entities: {people, organizations, dates, amounts, locations}
5. category: one of [definition, procedure, data, narrative, example, reference]
6. contextual_description: 2-3 sentences on role in document
7. questions: 3-5 hypothetical questions this chunk answers
```

---

### 3.3 LLM Client Integration

**File**: `api/enrichment/llm_client.py`

#### Abstract Base Class
```python
class LLMClient(ABC):
    @abstractmethod
    async def complete(self, prompt: str, system_prompt: str,
                       max_tokens: int, temperature: float) -> str

    @abstractmethod
    async def complete_json(self, prompt: str, system_prompt: str,
                           max_tokens: int) -> Dict
```

#### Implementations

**OpenAIClient**:
- Model: `gpt-4o-mini` (configurable)
- Handles markdown code block extraction for JSON

**GeminiClient**:
- Model: `gemini-1.5-flash` (configurable)
- Same interface as OpenAI

#### Factory Function
```python
def get_llm_client() -> LLMClient:
    if settings.llm_provider == "openai":
        return OpenAIClient(settings.openai_api_key, settings.openai_model)
    elif settings.llm_provider == "gemini":
        return GeminiClient(settings.gemini_api_key, settings.gemini_model)
```

---

## 4. Indexing System

The system maintains four separate indices for hybrid search.

### 4.1 Embedding Generation

**File**: `api/indexing/embedder.py`

**Class**: `Embedder`

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `embedding_model` | `all-mpnet-base-v2` | Sentence transformer model |
| `embedding_dimension` | 768 | Vector dimension |
| MTEB Score | 61.0 | Benchmark score |
| Normalization | L2 | For cosine similarity via dot product |

#### Key Methods
```python
def embed(self, text: str) -> np.ndarray:
    """Single text embedding, L2 normalized"""

def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
    """Batch embeddings with progress bar"""

def similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Cosine similarity (dot product of normalized vectors)"""

def find_similar(self, query_emb: np.ndarray, embeddings: np.ndarray,
                 top_k: int) -> List[Tuple[int, float]]:
    """Efficient similarity search"""
```

#### Implementation Details
- **Lazy Loading**: Model only loaded on first use
- **Empty Text Handling**: Returns zero vector for empty strings
- **Batch Filtering**: Filters non-empty texts before processing

---

### 4.2 FAISS Vector Index

**File**: `api/indexing/vector_index.py`

**Class**: `VectorIndex`

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| Index Type | `IndexFlatIP` | Inner product for normalized vectors |
| Dimension | 768 | From embedding model |

#### ID Mapping
Two dictionaries maintained for chunk_id ↔ FAISS index mapping:
```python
_id_to_idx: Dict[str, int]   # chunk_id → FAISS position
_idx_to_id: Dict[int, str]   # FAISS position → chunk_id
```

#### Key Methods
```python
def add(self, chunk_id: str, embedding: np.ndarray)
def add_batch(self, chunk_ids: List[str], embeddings: np.ndarray)
def search(self, query_embedding: np.ndarray, k: int,
           filter_ids: Optional[Set[str]]) -> List[Tuple[str, float]]
def remove(self, chunk_ids: List[str])  # Mapping removal only
def save(self, index_path: str, id_map_path: str)
def load(self, index_path: str, id_map_path: str)
```

#### Limitations
- FAISS `IndexFlatIP` doesn't support true deletion
- Removal only updates mappings (periodic rebuild recommended)

---

### 4.3 Multi-Vector Index

**File**: `api/indexing/multi_vector_index.py`

**Class**: `MultiVectorIndex`

Manages three separate FAISS indices for multi-vector retrieval.

#### Three Index Types

| Index | Content | ID Format | Purpose |
|-------|---------|-----------|---------|
| Main | Contextualized chunk text | `chunk_id` | Direct semantic matching |
| Summary | Chunk summaries (LLM) | `{chunk_id}_summary` | Broader topic matching |
| Question | Hypothetical questions | `question_id` | Query-to-question matching |

#### Key Methods
```python
def add_chunk(self, chunk_id: str, main_embedding: np.ndarray,
              summary_embedding: Optional[np.ndarray],
              question_embeddings: Optional[List[np.ndarray]])

def search(self, query_embedding: np.ndarray, k: int = 10,
           vector_types: List[str] = None,
           filter_ids: Optional[Set[str]] = None) -> Dict[str, List[Tuple[str, float]]]

def search_all(self, query_embedding: np.ndarray, k: int = 10,
               filter_ids: Optional[Set[str]] = None) -> Dict[str, List[Tuple[str, float]]]

def remove_chunk(self, chunk_id: str)  # Removes from all indices
```

#### Question-to-Chunk Mapping
```python
_question_to_chunk: Dict[str, str]  # question_id → chunk_id
```

#### Storage Files
```
./data/faiss/
  ├── main_index.faiss
  ├── main_id_map.json
  ├── summary_index.faiss
  ├── summary_id_map.json
  ├── question_index.faiss
  ├── question_id_map.json
  └── question_chunk_map.json
```

---

### 4.4 BM25 Keyword Index

**File**: `api/indexing/keyword_index.py`

**Class**: `KeywordIndex`

#### Algorithm
BM25 Okapi (from `rank_bm25` library)

#### Tokenization Pipeline
```
Input text
    ↓
1. Lowercase conversion
    ↓
2. Remove special characters (keep alphanumeric + spaces)
    ↓
3. Split on whitespace
    ↓
4. Remove stopwords (140+ common English words)
    ↓
5. Basic stemming (suffix stripping)
    ↓
Tokenized output
```

#### Stemming Rules
60+ suffix patterns handled:
```
ational → ate    (e.g., relational → relate)
tional  → tion   (e.g., conditional → condition)
encies  → ence   (e.g., frequencies → frequence)
ness    → ""     (e.g., happiness → happi)
ment    → ""     (e.g., adjustment → adjust)
...
```
Minimum 2-char tokens retained.

#### Key Methods
```python
def add(self, chunk_id: str, text: str)
def add_batch(self, chunk_ids: List[str], texts: List[str])
def search(self, query: str, k: int = 10) -> List[Tuple[str, float]]
def search_with_keywords(self, query: str, k: int) -> List[Tuple[str, float, List[str]]]
def remove(self, chunk_ids: List[str])
def save(self, path: str)  # Pickle serialization
def load(self, path: str)
```

#### Lazy BM25 Build
Index rebuilt on first search after modifications.

---

### 4.5 Metadata Storage (SQLite)

**File**: `api/indexing/metadata_store.py`

**Class**: `MetadataStore`

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| Database | SQLite | Local file-based |
| Mode | WAL | Write-Ahead Logging for concurrency |
| Driver | aiosqlite | Async operations |
| Path | `./data/sqlite/metadata.db` | Storage location |

#### Database Schema (11 Tables)

**1. documents**
```sql
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    file_path TEXT UNIQUE,
    file_name TEXT,
    file_type TEXT,
    file_hash TEXT,
    detected_doc_type TEXT,
    summary TEXT,
    entities TEXT,              -- JSON
    key_topics TEXT,            -- JSON array
    table_descriptions TEXT,    -- JSON array
    indexed_at TIMESTAMP,
    sheet_names TEXT,           -- For tabular
    column_schema TEXT,         -- For tabular
    row_count INTEGER,          -- For tabular
    date_range TEXT,            -- For tabular
    processing_status TEXT,     -- pending|layout_detected|text_extracted|reviewed|indexed
    layout_data TEXT,           -- JSON
    extracted_markdown TEXT,
    reviewed_markdown TEXT,
    page_count INTEGER
)
```

**2. document_entities** (for efficient filtering)
```sql
CREATE TABLE document_entities (
    document_id TEXT,
    entity_key TEXT,
    entity_value TEXT,
    FOREIGN KEY (document_id) REFERENCES documents(id)
)
```

**3. chunks**
```sql
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    text TEXT,
    contextualized_text TEXT,
    content_type TEXT,
    page INTEGER,
    sheet_name TEXT,
    heading_path TEXT,
    entities TEXT,              -- JSON
    chunk_index INTEGER,
    parent_chunk_id TEXT,       -- Hierarchical
    hierarchy_level INTEGER,    -- Hierarchical
    bbox TEXT,                  -- JSON
    layout_label TEXT,
    is_semantic_boundary INTEGER,
    semantic_similarity_prev REAL,
    FOREIGN KEY (document_id) REFERENCES documents(id)
)
```

**4. chunk_metadata** (LLM-enriched)
```sql
CREATE TABLE chunk_metadata (
    chunk_id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    keywords TEXT,              -- JSON array
    entities TEXT,              -- JSON
    category TEXT,
    contextual_description TEXT,
    enriched_at TIMESTAMP
)
```

**5. chunk_questions**
```sql
CREATE TABLE chunk_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT,
    question TEXT,
    vector_id TEXT,
    FOREIGN KEY (chunk_id) REFERENCES chunks(id)
)
```

**6. vector_embeddings**
```sql
CREATE TABLE vector_embeddings (
    id TEXT PRIMARY KEY,
    chunk_id TEXT,
    vector_type TEXT,           -- "main", "summary", "question"
    source_text TEXT,
    question_id TEXT
)
```

**7. document_pages** (PDF layout detection)
```sql
CREATE TABLE document_pages (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    page_number INTEGER,
    image_path TEXT,
    annotated_image_path TEXT,
    layout_json TEXT,
    extracted_text TEXT,
    unfiltered_annotated_image_path TEXT,
    unfiltered_layout_json TEXT,
    filter_stats_json TEXT,
    UNIQUE(document_id, page_number)
)
```

#### Indexes
```sql
CREATE INDEX idx_doc_file_path ON documents(file_path);
CREATE INDEX idx_doc_type ON documents(detected_doc_type);
CREATE INDEX idx_entity_key ON document_entities(entity_key);
CREATE INDEX idx_chunks_doc_id ON chunks(document_id);
CREATE INDEX idx_doc_status ON documents(processing_status);
CREATE INDEX idx_pages_doc_id ON document_pages(document_id);
CREATE INDEX idx_chunks_parent ON chunks(parent_chunk_id);
CREATE INDEX idx_chunks_hierarchy ON chunks(hierarchy_level);
CREATE INDEX idx_chunk_meta_id ON chunk_metadata(chunk_id);
CREATE INDEX idx_questions_chunk ON chunk_questions(chunk_id);
CREATE INDEX idx_vectors_chunk ON vector_embeddings(chunk_id);
CREATE INDEX idx_vectors_type ON vector_embeddings(vector_type);
```

---

## 5. Retrieval System

### 5.1 Query Processing

**File**: `api/search/query_processor.py`

**Class**: `QueryProcessor`

#### QueryIntent Output
```python
@dataclass
class QueryIntent:
    search_terms: str               # Core query
    doc_type_filter: Optional[str]  # Detected document type
    entity_filters: Dict[str, str]  # Entity constraints
    needs_synthesis: bool           # Requires LLM answer
    query_type: str                 # comparative|aggregation|exploratory|factual
```

#### Document Type Detection

**Keyword patterns** (`DOC_TYPE_KEYWORDS`):
```python
{
    "invoice": ["invoice", "bill", "payment", "receipt"],
    "contract": ["contract", "agreement", "terms", "lease"],
    "report": ["report", "analysis", "findings", "study"],
    "policy": ["policy", "procedure", "guideline", "standard"],
    "data": ["data", "spreadsheet", "csv", "excel", "table"],
    "presentation": ["presentation", "slides", "ppt", "deck"]
}
```

#### Synthesis Need Detection

**Triggers** (`_detect_synthesis_need()`):
- Keywords: "summarize", "explain", "compare", "difference", "how does", "why"
- Questions (ending with "?")
- Long queries (>10 words)

#### Query Type Classification

| Type | Trigger Keywords |
|------|------------------|
| `comparative` | "compare", "difference", "versus", "vs" |
| `aggregation` | "total", "sum", "average", "count", "how many" |
| `exploratory` | "what", "how", "why", "explain" |
| `factual` | Default |

---

### 5.2 HyDE Query Expansion

**File**: `api/search/hyde.py`

**Class**: `HyDEQueryExpander`

#### Purpose
HyDE (Hypothetical Document Embeddings) bridges the semantic gap between short queries and detailed documents by generating a hypothetical document that would answer the query.

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `alpha` | 0.6 | Weight: 60% hypothetical + 40% query |
| `temperature` | 0.7 | LLM creativity setting |
| `max_tokens` | 300 | Hypothetical document length |
| Target length | 150-250 words | Optimal detail level |

#### Processing Flow

**`expand_query()` method**:
```python
async def expand_query(self, query: str) -> Tuple[np.ndarray, Optional[str]]:
    # 1. Generate hypothetical document
    hypothetical = await self.generate_hypothetical(query)

    # 2. Embed both query and hypothetical
    query_embedding = self.embedder.embed(query)
    hypo_embedding = self.embedder.embed(hypothetical)

    # 3. Combine with weighted average
    combined = (1 - self.alpha) * query_embedding + self.alpha * hypo_embedding

    # 4. L2 normalize for cosine similarity
    combined = combined / np.linalg.norm(combined)

    return combined, hypothetical
```

**LLM Prompt for Hypothetical Generation**:
```
Generate a detailed, factual paragraph that would directly answer this query:
{query}

The response should be 150-250 words and contain specific information
that would be found in a relevant document.
```

---

### 5.3 Enhanced Hybrid Search

**File**: `api/search/enhanced_hybrid_search.py`

**Class**: `EnhancedHybridSearch`

#### Search Pipeline

**`async def search(query, k=10, filters, debug=False, document_id=None)`**:

**Step 1: Apply Filters**
```python
filter_chunk_ids = None
if document_id:
    # Search within specific document
    doc_chunks = await metadata_store.get_chunks_by_document(document_id)
    filter_chunk_ids = {c.id for c in doc_chunks}
elif filters:
    # Apply doc_type and entity filters
    filter_doc_ids = await self._apply_filters(filters)
    # Get chunk IDs for filtered documents
    filter_chunk_ids = await self._get_chunk_ids_for_documents(filter_doc_ids)
```

**Step 2: Query Embedding**
```python
if settings.enable_hyde:
    query_embedding, hypothetical_text = await hyde_expander.expand_query(query)
else:
    query_embedding = embedder.embed(query)
```

**Step 3: Multi-Vector Search**
```python
search_k = k * 3  # Search 3x to ensure enough results after fusion
vector_results = multi_vector_index.search_all(
    query_embedding,
    k=search_k,
    filter_ids=filter_chunk_ids
)
# Returns: {
#   "main": [(chunk_id, score), ...],
#   "summary": [(chunk_id, score), ...],
#   "question": [(chunk_id, score), ...]
# }
```

**Step 4: BM25 Keyword Search**
```python
bm25_results = keyword_index.search(query, k=search_k)
# Returns: [(chunk_id, score), ...]
```

**Step 5: RRF Fusion**
```python
combined_results = self._multi_source_rrf(
    main_results=vector_results["main"],
    summary_results=vector_results["summary"],
    question_results=vector_results["question"],
    bm25_results=bm25_results
)
```

---

### 5.4 RRF (Reciprocal Rank Fusion)

**Method**: `_multi_source_rrf()`

#### Formula
```
rrf_score = weight / (k_constant + rank)
```

Where:
- `k_constant = 60` (higher = more emphasis on top ranks)
- `weight` = source-specific weight
- `rank` = position in source results (1-indexed)

#### Source Weights
| Source | Weight | Purpose |
|--------|--------|---------|
| Main Vector | 0.40 (40%) | Direct semantic matching |
| BM25 Keyword | 0.25 (25%) | Exact term matching |
| Question Vector | 0.20 (20%) | Query-to-question matching |
| Summary Vector | 0.15 (15%) | Broad topic matching |

#### Fusion Logic
```python
def _multi_source_rrf(self, main_results, summary_results,
                       question_results, bm25_results):
    k_constant = 60
    total_scores = defaultdict(float)

    sources = [
        ("main_vector", main_results, 0.40),
        ("summary_vector", summary_results, 0.15),
        ("question_vector", question_results, 0.20),
        ("bm25", bm25_results, 0.25),
    ]

    for source_name, results, weight in sources:
        for rank, (chunk_id, _) in enumerate(results, 1):
            rrf_contribution = weight / (k_constant + rank)
            total_scores[chunk_id] += rrf_contribution

    # Sort by combined score
    return sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
```

---

### 5.5 Result Building

**Method**: `_build_result_item(chunk_id, score, query)`

For each top result:
1. Get chunk from metadata store
2. Get document metadata
3. Create highlights (contextual snippets with query terms)
4. Build `SearchResultItem`

**SearchResultItem Structure**:
```python
class SearchResultItem(BaseModel):
    document_id: str
    file_name: str
    file_type: str
    detected_doc_type: str
    chunk_text: str              # First 500 chars
    chunk_id: str
    score: float                 # RRF combined score (0-1)
    page: Optional[int]
    sheet_name: Optional[str]
    heading_path: Optional[str]
    highlights: List[str]        # Up to 3 query matches
    entities: Dict[str, Any]     # Chunk-specific entities
```

---

## 6. Response Synthesis

### 6.1 Response Generator

**File**: `api/search/response_generator.py`

**Class**: `ResponseGenerator`

#### Modes
| Mode | Behavior |
|------|----------|
| `auto` | Uses `needs_synthesis` flag from QueryIntent |
| `retrieval` | Return chunks only, no LLM |
| `synthesis` | LLM-generated answer from context |

#### Complete Flow

**`async def generate(query, mode="auto", k=10, filters=None)`**:

**Step 1: Cache Check**
```python
cached = await semantic_cache.get(query)
if cached:
    return SearchResponse(**cached.response, cache_hit=True)
```

**Step 2: Query Processing**
```python
intent = await query_processor.process(query)
combined_filters = filters or {}
if intent.doc_type_filter:
    combined_filters["doc_type"] = intent.doc_type_filter
```

**Step 3: Execute Search**
```python
search_result = await enhanced_hybrid_search.search(
    query=query,
    k=k,
    filters=combined_filters
)
results = search_result.results
```

**Step 4: Mode Decision**
```python
if mode == "auto":
    mode = "synthesis" if intent.needs_synthesis else "retrieval"
```

**Step 5: LLM Synthesis (if needed)**
```python
if mode == "synthesis" and results:
    answer = await self._synthesize_answer(query, results)
else:
    answer = None
```

**Step 6: Extract Sources**
```python
sources = self._extract_sources(results)
# Returns unique documents with chunk counts
```

**Step 7: Build Response**
```python
response = SearchResponse(
    query=query,
    results=results,
    answer=answer,
    total_results=len(results),
    latency_ms=(time.time() - start_time) * 1000,
    cache_hit=False,
    response_tier="synthesis" if answer else "retrieval",
    sources=sources
)
```

**Step 8: Cache Response**
```python
document_ids = list(set(r.document_id for r in results))
await semantic_cache.set(query, response.model_dump(), document_ids)
```

---

### 6.2 LLM Synthesis

**Method**: `_synthesize_answer(query, results)`

#### Result Formatting for LLM
```python
def _format_results_for_llm(results: List[SearchResultItem]) -> str:
    parts = []
    for i, result in enumerate(results[:10], 1):  # Top 10 only
        part = f"""
Result {i}:
- Document: {result.file_name}
- Type: {result.detected_doc_type}
- Section: {result.heading_path or 'N/A'}
- Content: {result.chunk_text[:500]}
"""
        if result.entities:
            entities_str = ", ".join(f"{k}={v}" for k, v in result.entities.items())
            part += f"- Key Info: {entities_str}\n"
        parts.append(part)
    return "\n".join(parts)
```

#### Synthesis Prompt
```
Based on the following search results, provide a comprehensive answer to the query.

Query: {query}

Search Results:
{formatted_results}

Instructions:
- Synthesize information from multiple sources when relevant
- Cite specific documents when making claims
- Be concise but complete
- If information is not found in the results, say so
- Do not fabricate information
```

#### LLM Configuration
- Temperature: 0.3 (low for consistency)
- Max tokens: 500

---

### 6.3 Semantic Cache

**File**: `api/search/semantic_cache.py`

**Class**: `SemanticCache`

#### Configuration
| Parameter | Value | Description |
|-----------|-------|-------------|
| `cache_similarity_threshold` | 0.92 | 92% semantic match for cache hit |
| `cache_ttl_seconds` | 3600 | 1 hour TTL |
| `cache_max_entries` | 2000 | LRU eviction when exceeded |

#### Data Structure
```python
@dataclass
class CachedResponse:
    query: str                      # Original query string
    response: Dict                  # Cached search response
    document_ids: List[str]         # Contributing documents
    created_at: datetime            # Timestamp

# Internal storage
_cache: Dict[str, CachedResponse]   # cache_key → response
_embeddings: Dict[str, np.ndarray]  # cache_key → query embedding
_access_order: List[str]            # LRU tracking
```

#### Cache Operations

**`async def get(query: str)`**:
1. Embed the query
2. Find most similar cached query embedding
3. Check if similarity >= 0.92
4. Check TTL (evict if expired)
5. Update LRU access order
6. Return cached response or None

**`async def set(query, response, document_ids)`**:
1. Generate cache key (SHA256 hash of query)
2. Embed query
3. Evict LRU entry if at capacity
4. Store response with embeddings and document IDs

**`invalidate_for_document(document_id)`**:
- Clears all cache entries referencing a document (when document is updated)

#### Cache Hit Conditions
1. Query embedding similarity ≥ 0.92
2. Cache entry not expired (within TTL)
3. All contributing documents still valid

---

## 7. Data Flow Diagrams

### 7.1 Document Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DOCUMENT PROCESSING PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐
     │   File   │
     │ (PDF/    │
     │ DOCX/    │
     │ PPTX/    │
     │ CSV/XLS) │
     └────┬─────┘
          │
          ▼
┌─────────────────┐
│   1. PARSE      │
│   ────────      │
│ • Format detect │
│ • Text extract  │
│ • Tables parse  │
│ • Headings find │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. ENRICH      │
│  ─────────      │
│ • LLM analysis  │
│ • Doc type      │
│ • Summary       │
│ • Entities      │
│ • Topics        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   3. CHUNK      │
│   ────────      │
│ • Hierarchical  │
│ • Semantic      │
│ • Context add   │
│ • Parent-child  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   4. EMBED      │
│   ────────      │
│ • Batch embed   │
│ • 768-dim vecs  │
│ • L2 normalize  │
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┐
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  5a. FAISS      │ │  5b. BM25       │ │  5c. SQLite     │
│  ───────────    │ │  ─────────      │ │  ───────────    │
│ • Main index    │ │ • Tokenize      │ │ • Documents     │
│ • Summary index │ │ • Stopwords     │ │ • Chunks        │
│ • Question idx  │ │ • Stemming      │ │ • Metadata      │
│ • ID mappings   │ │ • BM25 scores   │ │ • Questions     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 7.2 Query-to-Response Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QUERY-TO-RESPONSE FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

                            ┌─────────────┐
                            │   QUERY     │
                            │ "Find all   │
                            │  invoices"  │
                            └──────┬──────┘
                                   │
                                   ▼
                     ┌─────────────────────────┐
                     │    QUERY PROCESSING     │
                     │    ─────────────────    │
                     │ • Intent detection      │
                     │ • Doc type filter       │
                     │ • Synthesis need        │
                     │ • Query classification  │
                     └───────────┬─────────────┘
                                 │
                                 ▼
                     ┌─────────────────────────┐
                     │     CACHE CHECK         │
                     │     ───────────         │
                     │ • Embed query           │
                     │ • Find similar (≥0.92)  │
                     │ • Check TTL             │
                     └───────────┬─────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                HIT │                         │ MISS
                    ▼                         ▼
          ┌─────────────────┐      ┌─────────────────────┐
          │ Return Cached   │      │   QUERY EMBEDDING   │
          │ Response        │      │   ───────────────   │
          └─────────────────┘      │ • HyDE hypothetical │
                                   │ • 60% hypo + 40% q  │
                                   │ • L2 normalize      │
                                   └──────────┬──────────┘
                                              │
                         ┌────────────────────┴────────────────────┐
                         │                                         │
                         ▼                                         ▼
              ┌────────────────────┐                    ┌────────────────────┐
              │  MULTI-VECTOR      │                    │     BM25           │
              │  ─────────────     │                    │     ─────          │
              │ • Main (40%)       │                    │ • Tokenize query   │
              │ • Summary (15%)    │                    │ • BM25 scores      │
              │ • Question (20%)   │                    │ • Top k*3 results  │
              │ • Filter by doc    │                    │ • Weight: 25%      │
              └─────────┬──────────┘                    └──────────┬─────────┘
                        │                                          │
                        └────────────────┬─────────────────────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │    RRF FUSION       │
                              │    ──────────       │
                              │ score = w/(60+rank) │
                              │ Combine all sources │
                              │ Sort by total score │
                              │ Take top k          │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   RESULT BUILDING   │
                              │   ───────────────   │
                              │ • Get chunk text    │
                              │ • Get doc metadata  │
                              │ • Create highlights │
                              │ • Build result item │
                              └──────────┬──────────┘
                                         │
                                         ▼
                              ┌─────────────────────┐
                              │   MODE DECISION     │
                              │   ─────────────     │
                              │ auto → check intent │
                              │ needs_synthesis?    │
                              └──────────┬──────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        │                                 │
               RETRIEVAL│                                 │SYNTHESIS
                        ▼                                 ▼
              ┌─────────────────┐              ┌─────────────────────┐
              │ Return chunks   │              │   LLM SYNTHESIS     │
              │ only            │              │   ─────────────     │
              └─────────────────┘              │ • Format top 10     │
                                               │ • Add context       │
                                               │ • Call LLM (t=0.3)  │
                                               │ • Generate answer   │
                                               └──────────┬──────────┘
                                                          │
                                                          ▼
                                               ┌─────────────────────┐
                                               │   CACHE STORAGE     │
                                               │   ─────────────     │
                                               │ • Hash query        │
                                               │ • Store response    │
                                               │ • Track doc IDs     │
                                               │ • LRU eviction      │
                                               └──────────┬──────────┘
                                                          │
                                                          ▼
                                               ┌─────────────────────┐
                                               │   SearchResponse    │
                                               │   ──────────────    │
                                               │ • results[]         │
                                               │ • answer (if synth) │
                                               │ • sources[]         │
                                               │ • latency_ms        │
                                               └─────────────────────┘
```

---

## 8. Configuration Reference

**File**: `api/config/settings.py`

### Paths
| Parameter | Default | Description |
|-----------|---------|-------------|
| `watch_folder` | `./documents` | Document watch directory |
| `data_folder` | `./data` | Data storage root |
| `database_path` | `./data/sqlite/metadata.db` | SQLite database |

### Chunking
| Parameter | Value | Description |
|-----------|-------|-------------|
| `chunk_size` | 1500 | Basic chunker target size (chars) |
| `chunk_overlap` | 200 | Configured but not actively used |
| `max_chunk_size` | 2500 | Max for hierarchical/semantic (chars) |
| `enable_semantic_chunking` | True | Enable semantic refinement |
| `semantic_similarity_threshold` | 0.80 | Topic break threshold |

### Embedding
| Parameter | Value | Description |
|-----------|-------|-------------|
| `embedding_model` | `all-mpnet-base-v2` | Sentence transformer |
| `embedding_dimension` | 768 | Vector size |

### Search
| Parameter | Value | Description |
|-----------|-------|-------------|
| `search_top_k` | 10 | Default results |
| `enable_hyde` | True | Enable HyDE expansion |
| `hyde_alpha` | 0.6 | HyDE blend ratio |

### Multi-Vector Weights
| Parameter | Value | Description |
|-----------|-------|-------------|
| `multi_vector_weights_main` | 0.40 | Main vector weight |
| `multi_vector_weights_question` | 0.20 | Question vector weight |
| `multi_vector_weights_bm25` | 0.25 | BM25 weight |
| `multi_vector_weights_summary` | 0.15 | Summary vector weight |

### Cache
| Parameter | Value | Description |
|-----------|-------|-------------|
| `cache_ttl_seconds` | 3600 | Cache lifetime (1 hour) |
| `cache_similarity_threshold` | 0.92 | Semantic cache hit threshold |
| `cache_max_entries` | 2000 | LRU cache size |

### Enrichment
| Parameter | Value | Description |
|-----------|-------|-------------|
| `enrichment_batch_size` | 5 | Concurrent LLM calls |
| `questions_per_chunk` | 3 | Hypothetical Qs per chunk |

### LLM
| Parameter | Value | Description |
|-----------|-------|-------------|
| `llm_provider` | `openai` | Provider selection |
| `openai_model` | `gpt-4o-mini` | OpenAI model |
| `gemini_model` | `gemini-1.5-flash` | Gemini model |

---

## 9. Storage Structure

```
./data/
├── faiss/
│   ├── main_index.faiss          # Main vector embeddings
│   ├── main_id_map.json          # chunk_id ↔ FAISS position
│   ├── summary_index.faiss       # Summary embeddings
│   ├── summary_id_map.json       # Summary ID mapping
│   ├── question_index.faiss      # Question embeddings
│   ├── question_id_map.json      # Question ID mapping
│   └── question_chunk_map.json   # question_id → chunk_id
├── bm25/
│   └── index.pkl                 # Pickled BM25 index
├── cache/
│   └── semantic_cache.pkl        # Pickled semantic cache
└── sqlite/
    └── metadata.db               # SQLite database (WAL mode)
```

---

## 10. Key File Reference

### Core Processing
| File | Purpose |
|------|---------|
| `api/core/document_processor.py` | Main processing orchestration |
| `api/parsers/base.py` | Parser interface and ParseResult |

### Chunking
| File | Purpose |
|------|---------|
| `api/indexing/chunker.py` | Basic paragraph chunker |
| `api/indexing/hierarchical_chunker.py` | Markdown structure chunker |
| `api/indexing/semantic_chunker.py` | Topic-aware chunker |

### Indexing
| File | Purpose |
|------|---------|
| `api/indexing/embedder.py` | Sentence transformer wrapper |
| `api/indexing/vector_index.py` | Single FAISS index |
| `api/indexing/multi_vector_index.py` | 3-index manager |
| `api/indexing/keyword_index.py` | BM25 implementation |
| `api/indexing/metadata_store.py` | SQLite async storage |

### Enrichment
| File | Purpose |
|------|---------|
| `api/enrichment/entity_extractor.py` | Document enrichment |
| `api/indexing/chunk_enricher.py` | LLM chunk enrichment |
| `api/enrichment/llm_client.py` | OpenAI/Gemini abstraction |
| `api/enrichment/prompts.py` | LLM prompt templates |

### Search
| File | Purpose |
|------|---------|
| `api/search/enhanced_hybrid_search.py` | Multi-vector + BM25 + RRF |
| `api/search/response_generator.py` | Synthesis orchestration |
| `api/search/query_processor.py` | Query intent analysis |
| `api/search/hyde.py` | Hypothetical document generation |
| `api/search/semantic_cache.py` | LRU semantic cache |

### Models
| File | Purpose |
|------|---------|
| `api/models/chunk.py` | Chunk data model |
| `api/models/document.py` | Document data model |

### Configuration
| File | Purpose |
|------|---------|
| `api/config/settings.py` | All configuration settings |

### API Routes
| File | Purpose |
|------|---------|
| `api/api/routes/search.py` | Search endpoints |
| `api/api/routes/chunking.py` | Chunking endpoints |
| `api/api/routes/documents.py` | Document management |

---

## Summary

This architecture implements a sophisticated **Multi-Vector RAG system** that:

1. **Chunks documents intelligently** using three strategies (basic, hierarchical, semantic)
2. **Enriches content with LLMs** at both document and chunk levels
3. **Indexes content in four ways** (main vector, summary vector, question vector, BM25)
4. **Retrieves with hybrid search** combining semantic and keyword matching
5. **Ranks results using RRF** for robust multi-source fusion
6. **Synthesizes answers with LLMs** when complex queries require it
7. **Caches responses semantically** for performance optimization

The modular design allows each component to be configured, extended, or replaced independently while maintaining the overall system coherence.
