# LAN File Search System
## Complete Architecture with Dynamic LLM-Based Enrichment

---

## System Overview

```
                         YOUR OFFICE NETWORK (LAN)
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                        SERVER MACHINE                                │  │
│   │               (Only machine running Docker)                         │  │
│   │                                                                      │  │
│   │   ┌───────────────────┐    ┌──────────────────────────────────┐    │  │
│   │   │  SHARED FOLDER    │    │       SEARCH APPLICATION         │    │  │
│   │   │                   │    │                                  │    │  │
│   │   │  📄 Reports.pdf   │    │  • Parses PDFs, Office, CSV/Excel│    │  │
│   │   │  📄 Contract.docx │───▶│  • LLM extracts entities dynamically│   │  │
│   │   │  📄 Data.xlsx     │    │  • Creates searchable index      │    │  │
│   │   │  📄 Sales.csv     │    │  • Answers user queries          │    │  │
│   │   │                   │    │                                  │    │  │
│   │   └───────────────────┘    └──────────────────────────────────┘    │  │
│   │         ▲                              │                            │  │
│   │         │ Admins add files             │ Web Interface              │  │
│   └─────────┼──────────────────────────────┼────────────────────────────┘  │
│             │                              ▼                               │
│   ┌─────────┴──────────────────────────────────────────────────────────┐  │
│   │                         LAN USERS                                   │  │
│   │   👤 Browser → http://192.168.x.x:3000 (No installation needed)    │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Supported File Types

| Format | Extension | What Gets Extracted |
|--------|-----------|---------------------|
| PDF | `.pdf` | Text, tables, images with OCR |
| Word | `.docx` | Text, headings, tables, styles |
| Excel | `.xlsx`, `.xls` | All sheets, headers, cell data, formulas |
| CSV | `.csv` | Headers as schema, all rows as searchable data |
| PowerPoint | `.pptx` | Slide text, speaker notes, tables |

---

## Response Tier Strategy

| Tier | Latency | When Used |
|------|---------|-----------|
| **Cache Hit** | <15ms | Similar query asked before |
| **Retrieval Only** | <50ms | Simple lookups, keyword searches |
| **LLM Generation** | 500ms-1.5s | Complex questions needing synthesis |

---

## Core Architecture Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SYSTEM ARCHITECTURE                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         FILE WATCHER                                 │   │
│  │                   (Monitors shared folder)                          │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PARSING LAYER                                     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │   │
│  │  │ PDF Parser  │ │Office Parser│ │ CSV Parser  │ │Excel Parser │   │   │
│  │  │  (Docling)  │ │  (Docling)  │ │ (Pandas)    │ │ (Pandas)    │   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                 LLM ENRICHMENT LAYER                                 │   │
│  │           (Dynamic, Schema-Free Entity Extraction)                  │   │
│  │                                                                      │   │
│  │   • Document summarization                                          │   │
│  │   • Dynamic entity extraction (adapts to content)                   │   │
│  │   • Table/CSV semantic descriptions                                 │   │
│  │   • Hypothetical question generation                                │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    INDEXING LAYER                                    │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                   │   │
│  │  │FAISS Vector │ │ BM25 Keyword│ │  Metadata   │                   │   │
│  │  │   Index     │ │   Index     │ │   Store     │                   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                   │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SEARCH LAYER                                     │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                   │   │
│  │  │  Semantic   │ │   Hybrid    │ │   Entity    │                   │   │
│  │  │   Cache     │ │   Search    │ │  Filtering  │                   │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘                   │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      API LAYER                                       │   │
│  │              (FastAPI - serves Web UI and API)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Dynamic LLM-Based Entity Extraction

### Why Dynamic Instead of Predefined

| Approach | Problem |
|----------|---------|
| **Predefined schemas** | Cannot adapt to new document types; misses domain-specific entities |
| **SpaCy NER only** | Limited to generic types (PERSON, ORG, DATE); misses business context |
| **Dynamic LLM extraction** | Adapts to any document; extracts what matters for that specific content |

### How Dynamic Extraction Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DYNAMIC ENTITY EXTRACTION FLOW                            │
│                                                                              │
│   STEP 1: Parse Document                                                    │
│   ─────────────────────                                                     │
│   Extract raw text, structure, tables from PDF/Office/CSV/Excel             │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│   STEP 2: LLM Analyzes Content                                              │
│   ────────────────────────────                                              │
│   Single prompt asks LLM to:                                                │
│   • Identify document type/purpose                                          │
│   • Extract ALL relevant entities it finds                                  │
│   • Generate document summary                                               │
│   • Describe tables/data in natural language                                │
│                                                                              │
│   No predefined schema - LLM decides what's important                       │
│                                                                              │
│                               ▼                                              │
│                                                                              │
│   STEP 3: Structure Output                                                  │
│   ────────────────────────                                                  │
│   LLM returns structured JSON with:                                         │
│   • document_type: What kind of document (invoice, report, etc.)           │
│   • summary: 2-3 sentence summary                                          │
│   • entities: Key-value pairs of extracted information                      │
│   • table_descriptions: Natural language descriptions of any tables        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Example: Same System, Different Documents

```
DOCUMENT 1: Invoice
───────────────────
LLM automatically extracts:
  • vendor_name: "Acme Corp"
  • invoice_number: "INV-2024-001"
  • total_amount: "$15,420.00"
  • due_date: "2024-03-15"
  • line_items: "Software licenses, Support services"

DOCUMENT 2: Employee Handbook  
─────────────────────────────
LLM automatically extracts:
  • policy_areas: "Leave, Benefits, Code of Conduct"
  • effective_date: "January 2024"
  • departments: "All employees"
  • key_contacts: "HR Director: Jane Smith"

DOCUMENT 3: Sales Data (CSV)
────────────────────────────
LLM automatically extracts:
  • data_columns: "Date, Product, Region, Revenue, Units"
  • date_range: "Q1 2024 - Q4 2024"
  • total_records: "2,847 rows"
  • key_metrics: "Total Revenue: $4.2M, Top Region: Northeast"
  • data_description: "Quarterly sales transactions by product and region"

No predefined schema needed - LLM adapts to each document type
```

---

## CSV and Excel Handling

### The Challenge with Tabular Data

```
RAW CSV/EXCEL:
┌──────────┬─────────┬────────┬─────────┐
│ Date     │ Product │ Region │ Revenue │
├──────────┼─────────┼────────┼─────────┤
│ 2024-01  │ Widget  │ North  │ 45000   │
│ 2024-01  │ Gadget  │ South  │ 32000   │
│ ...      │ ...     │ ...    │ ...     │
└──────────┴─────────┴────────┴─────────┘

Problem: Searching "Q1 North revenue" won't match raw cell values
```

### Solution: Multi-Level Tabular Indexing

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CSV/EXCEL PROCESSING PIPELINE                            │
│                                                                              │
│   LEVEL 1: File-Level Metadata                                              │
│   ────────────────────────────                                              │
│   • File name, sheet names (for Excel)                                      │
│   • Column headers as schema                                                │
│   • Row count, date range                                                   │
│   • LLM-generated description of what the data contains                     │
│                                                                              │
│   LEVEL 2: Schema Description                                               │
│   ───────────────────────────                                               │
│   • Each column described in natural language                               │
│   • Data types detected (dates, currency, categories, etc.)                 │
│   • Sample values for context                                               │
│                                                                              │
│   LEVEL 3: Aggregated Summaries                                             │
│   ─────────────────────────────                                             │
│   • LLM generates natural language summary of the data                      │
│   • Key statistics: totals, averages, min/max                               │
│   • Trends and patterns described                                           │
│                                                                              │
│   LEVEL 4: Row-Level Indexing (Optional, for small files)                   │
│   ───────────────────────────────────────────────────────                   │
│   • Each row converted to natural language sentence                         │
│   • Enables specific record lookup                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What Gets Indexed for a CSV/Excel File

```
FILE: sales_data_2024.xlsx

INDEXED CONTENT:
────────────────

1. File Summary (embedded as searchable chunk):
   "Excel file containing 2024 sales data across 3 sheets. 
    Main sheet has 2,847 transactions from January to December 2024.
    Columns: Date, Product, Region, Sales Rep, Revenue, Units Sold.
    Total revenue: $4.2M. Top performing region: Northeast (35% of sales)."

2. Sheet Descriptions:
   "Sheet 'Transactions': Individual sales records with date, product, region
    Sheet 'Summary': Monthly aggregates by region
    Sheet 'Products': Product catalog with pricing"

3. Column Schema:
   "Date: Transaction dates from 2024-01-01 to 2024-12-31
    Product: Product names including Widget, Gadget, Gizmo (15 unique)
    Region: Sales regions - North, South, East, West, Northeast
    Revenue: Dollar amounts ranging from $500 to $125,000"

4. Key Insights:
   "Q4 showed 23% growth over Q3. Widget is the top seller.
    Northeast region outperforms others by 2x."

All of this is searchable - so "Q4 growth" or "top selling product" will match
```

---

## Enriched Indexing Pipeline (Complete Flow)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE INDEXING PIPELINE                                │
│                                                                              │
│  📄 NEW FILE DETECTED                                                       │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: FILE TYPE ROUTING                                           │   │
│  │                                                                       │   │
│  │   .pdf, .docx, .pptx  ──▶  Document Parser (Docling)                │   │
│  │   .xlsx, .xls         ──▶  Excel Parser (Pandas + Sheet handling)   │   │
│  │   .csv                ──▶  CSV Parser (Pandas + Schema detection)   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: STRUCTURE EXTRACTION                                        │   │
│  │                                                                       │   │
│  │   Documents: Headings, paragraphs, tables, page numbers             │   │
│  │   Excel: Sheet names, headers, data types, row counts               │   │
│  │   CSV: Column headers, data types, sample values                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: LLM ENRICHMENT (Single API Call)                           │   │
│  │                                                                       │   │
│  │   Input to LLM:                                                      │   │
│  │   • File name and type                                              │   │
│  │   • Extracted text/structure (truncated if needed)                  │   │
│  │   • For tabular: headers + sample rows + basic stats                │   │
│  │                                                                       │   │
│  │   LLM Returns:                                                       │   │
│  │   • document_type: Auto-detected type                               │   │
│  │   • summary: 2-3 sentence description                               │   │
│  │   • entities: Key information extracted (dynamic, not predefined)   │   │
│  │   • table_descriptions: Natural language for any tables/data        │   │
│  │   • key_topics: Main subjects covered                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: CHUNKING                                                    │   │
│  │                                                                       │   │
│  │   Documents:                                                         │   │
│  │   • Structure-aware chunks (respect paragraphs, tables)             │   │
│  │   • Each chunk tagged with heading hierarchy                        │   │
│  │                                                                       │   │
│  │   Tabular (CSV/Excel):                                              │   │
│  │   • File-level summary chunk                                        │   │
│  │   • Schema description chunk                                        │   │
│  │   • Per-sheet summary chunks (Excel)                                │   │
│  │   • Optional: Row groups for large files                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 5: CONTEXTUAL EMBEDDING                                        │   │
│  │                                                                       │   │
│  │   Each chunk is prepended with context before embedding:            │   │
│  │                                                                       │   │
│  │   "Document: [filename]                                             │   │
│  │    Type: [auto-detected type]                                       │   │
│  │    Section: [heading path]                                          │   │
│  │    Entities: [key extracted entities]                               │   │
│  │                                                                       │   │
│  │    [actual chunk content]"                                          │   │
│  │                                                                       │   │
│  │   This enriched text is what gets embedded (not raw text)           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 6: MULTI-INDEX STORAGE                                         │   │
│  │                                                                       │   │
│  │   FAISS Vector Index: Semantic similarity search                    │   │
│  │   BM25 Keyword Index: Exact term matching                           │   │
│  │   Metadata Store: Entities, file info, timestamps (for filtering)  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Gets Stored Per Document

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STORED DATA STRUCTURE                                     │
│                                                                              │
│  DOCUMENT LEVEL:                                                            │
│  ───────────────                                                            │
│  • file_path: Full path to file                                            │
│  • file_name: Display name                                                 │
│  • file_type: pdf, docx, xlsx, csv, pptx                                   │
│  • detected_doc_type: LLM-detected (invoice, report, contract, etc.)       │
│  • summary: LLM-generated 2-3 sentence summary                             │
│  • entities: Dynamic key-value pairs extracted by LLM                      │
│  • key_topics: Main subjects covered                                       │
│  • indexed_at: Timestamp                                                   │
│                                                                              │
│  FOR TABULAR FILES (CSV/EXCEL) ADDITIONALLY:                               │
│  ────────────────────────────────────────────                              │
│  • sheet_names: List of sheets (Excel only)                                │
│  • column_schema: Headers with detected data types                         │
│  • row_count: Number of records                                            │
│  • date_range: If date columns detected                                    │
│  • numeric_summary: Totals, averages for numeric columns                   │
│  • data_description: Natural language description of the data              │
│                                                                              │
│  CHUNK LEVEL:                                                               │
│  ────────────                                                               │
│  • chunk_id: Unique identifier                                             │
│  • text: Original chunk content                                            │
│  • contextualized_text: Enriched text (what gets embedded)                 │
│  • embedding: Vector representation                                        │
│  • headings: Section hierarchy (documents only)                            │
│  • page: Page number (PDFs only)                                           │
│  • sheet_name: Sheet name (Excel only)                                     │
│  • content_type: paragraph, table, list, summary, schema                   │
│  • chunk_entities: Entities specific to this chunk                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Search Flow with Dynamic Entities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SEARCH FLOW                                          │
│                                                                              │
│  USER QUERY: "Show me Q4 invoices over $10,000"                             │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: CACHE CHECK                                                 │   │
│  │  Look for semantically similar previous query (<15ms)               │   │
│  │  If found → return cached response                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │ Cache miss                                                        │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: QUERY UNDERSTANDING (Optional LLM call for complex queries)│   │
│  │                                                                       │   │
│  │  Extracted intent:                                                   │   │
│  │  • doc_type_filter: "invoice"                                       │   │
│  │  • time_filter: "Q4" (Oct-Dec)                                      │   │
│  │  • amount_filter: "> $10,000"                                       │   │
│  │  • search_terms: "invoice Q4 $10,000"                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: METADATA FILTERING                                          │   │
│  │                                                                       │   │
│  │  Filter documents where:                                             │   │
│  │  • detected_doc_type contains "invoice"                             │   │
│  │  • entities contain amounts > 10000                                 │   │
│  │  • entities contain Q4 dates                                        │   │
│  │                                                                       │   │
│  │  This narrows search space before vector search                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: HYBRID SEARCH (on filtered set)                            │   │
│  │                                                                       │   │
│  │  Run in parallel:                                                    │   │
│  │  • Vector search: Semantic similarity                               │   │
│  │  • BM25 search: Keyword matching                                    │   │
│  │                                                                       │   │
│  │  Combine with Reciprocal Rank Fusion (RRF)                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 5: ENTITY BOOSTING                                             │   │
│  │                                                                       │   │
│  │  Boost scores for chunks where:                                      │   │
│  │  • Extracted entities match query terms                             │   │
│  │  • Document type matches detected intent                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                                                                    │
│         ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 6: RESPONSE GENERATION                                         │   │
│  │                                                                       │   │
│  │  Simple query → Return ranked chunks with highlights                │   │
│  │  Complex query → LLM synthesizes answer from top chunks             │   │
│  │                                                                       │   │
│  │  Cache response for future similar queries                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## LLM Enrichment Prompt Strategy

### Single-Prompt Approach

Instead of multiple LLM calls, use one comprehensive prompt that handles all enrichment:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LLM ENRICHMENT PROMPT                                     │
│                                                                              │
│  INPUT TO LLM:                                                              │
│  ─────────────                                                              │
│  • File name and type                                                       │
│  • First ~6000 characters of content                                        │
│  • For tabular: column headers + 10 sample rows + basic stats              │
│  • Any detected structure (headings, tables)                                │
│                                                                              │
│  LLM INSTRUCTIONS:                                                          │
│  ─────────────────                                                          │
│  "Analyze this document and return JSON with:                              │
│                                                                              │
│   1. document_type: What type of document is this?                         │
│      (invoice, contract, report, policy, data file, etc.)                  │
│                                                                              │
│   2. summary: 2-3 sentence summary of the document                         │
│                                                                              │
│   3. entities: Extract ALL important information as key-value pairs.       │
│      Adapt to the document - extract what's relevant for THIS document.   │
│      Examples: dates, names, amounts, products, terms, metrics, etc.       │
│                                                                              │
│   4. key_topics: List of main topics/subjects covered                      │
│                                                                              │
│   5. table_descriptions: If tables or data present, describe in            │
│      natural language what the data shows                                  │
│                                                                              │
│  Return ONLY valid JSON, no explanation."                                  │
│                                                                              │
│  LLM OUTPUT EXAMPLE:                                                        │
│  ────────────────────                                                       │
│  {                                                                          │
│    "document_type": "quarterly_financial_report",                          │
│    "summary": "Q4 2024 financial report showing 15% revenue growth...",   │
│    "entities": {                                                           │
│      "report_period": "Q4 2024",                                          │
│      "total_revenue": "$2.4M",                                            │
│      "revenue_growth": "15%",                                             │
│      "net_profit": "$340K",                                               │
│      "top_product": "Widget Pro",                                         │
│      "prepared_by": "Finance Department",                                 │
│      "approval_date": "2025-01-15"                                        │
│    },                                                                       │
│    "key_topics": ["revenue", "profit", "product performance", "forecast"],│
│    "table_descriptions": [                                                 │
│      "Table 1: Quarterly revenue by product line",                        │
│      "Table 2: Regional sales breakdown showing Northeast leading"        │
│    ]                                                                        │
│  }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Caching Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MULTI-LEVEL CACHE                                     │
│                                                                              │
│  LEVEL 1: Query Embedding Cache                                             │
│  ─────────────────────────────────                                          │
│  • Cache computed query embeddings                                          │
│  • Saves 50-100ms per repeated/similar query                                │
│  • LRU eviction, max 2000 entries                                           │
│                                                                              │
│  LEVEL 2: Semantic Response Cache                                           │
│  ─────────────────────────────────                                          │
│  • Cache full responses (answer + sources)                                  │
│  • Matched by semantic similarity (threshold: 0.92)                         │
│  • Invalidated when source documents change                                 │
│  • TTL: 1 hour (configurable)                                               │
│                                                                              │
│  LEVEL 3: LLM Response Cache                                                │
│  ───────────────────────────────                                            │
│  • Cache LLM-generated answers                                              │
│  • Keyed by (query + context hash)                                          │
│  • Saves API costs and 500ms+ latency                                       │
│                                                                              │
│  CACHE INVALIDATION:                                                        │
│  ───────────────────                                                        │
│  • When file is modified → invalidate all cache entries referencing it     │
│  • When file is deleted → remove from index + invalidate cache             │
│  • Admin can manually clear cache via API                                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT OVERVIEW                                     │
│                                                                              │
│  SERVER REQUIREMENTS:                                                       │
│  ────────────────────                                                       │
│  • RAM: 16GB recommended (8GB minimum)                                     │
│  • CPU: 4+ cores                                                           │
│  • Storage: 50GB+ SSD                                                      │
│  • OS: Ubuntu 22.04 / Windows Server / macOS                               │
│  • Network: Gigabit LAN connection                                         │
│  • Internet: Required for Gemini/OpenAI API calls                          │
│                                                                              │
│  DOCKER SERVICES:                                                           │
│  ────────────────                                                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Container: search-api                                               │   │
│  │  • FastAPI application                                              │   │
│  │  • Indexing service                                                 │   │
│  │  • Search engine                                                    │   │
│  │  • File watcher                                                     │   │
│  │  • Port: 8000                                                       │   │
│  │                                                                       │   │
│  │  Volumes:                                                            │   │
│  │  • /documents (shared folder, read-only)                            │   │
│  │  • /data (index storage, persistent)                                │   │
│  │                                                                       │   │
│  │  Environment:                                                        │   │
│  │  • LLM_PROVIDER: gemini or openai                                   │   │
│  │  • GEMINI_API_KEY or OPENAI_API_KEY                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Container: web-ui                                                   │   │
│  │  • Streamlit web interface                                          │   │
│  │  • Port: 3000                                                       │   │
│  │  • Connects to search-api internally                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  USER ACCESS:                                                               │
│  ────────────                                                               │
│  • Users open browser to http://<server-ip>:3000                           │
│  • No installation required on user machines                               │
│  • Works on any device with a web browser                                  │
│                                                                              │
│  ADMIN ACCESS:                                                              │
│  ─────────────                                                              │
│  • Copy files to shared folder (network drive)                             │
│  • Optional: API endpoints for reindex, clear cache                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Performance Targets

| Operation | Target Latency | Method |
|-----------|----------------|--------|
| Cache hit | <15ms | In-memory semantic similarity |
| Simple retrieval | <50ms | Hybrid search (FAISS + BM25) |
| Complex query with LLM | 500ms-1.5s | Gemini Flash / GPT-4o-mini |
| Index new PDF | 3-8 seconds | Parse + LLM enrichment + embed |
| Index CSV/Excel | 2-5 seconds | Schema extract + LLM summary |
| Full reindex (1000 files) | 15-30 minutes | Background process |

---

## Accuracy Improvements from Enrichment

| Technique | Accuracy Gain | Latency Impact |
|-----------|---------------|----------------|
| Contextual chunk embedding | +15-25% | None |
| LLM-generated summaries | +5-10% | None (pre-computed) |
| Dynamic entity extraction | +10-20% | None (pre-computed) |
| Table/CSV descriptions | +20-30% for tabular | None (pre-computed) |
| Entity-based filtering | +5-10% | Faster (fewer candidates) |
| Hybrid search (vector + BM25) | +10-15% | Minimal |
| Query embedding cache | None | -60% on cache hits |

---

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/search` | POST | Main search endpoint |
| `/documents` | GET | List all indexed documents |
| `/documents/{id}` | GET | Get document details and summary |
| `/stats` | GET | Index statistics |
| `/admin/reindex` | POST | Trigger full reindex |
| `/admin/clear-cache` | POST | Clear all caches |
| `/health` | GET | Health check |

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API Framework | FastAPI | Async HTTP API |
| Document Parsing | Docling | PDF, Word, PowerPoint |
| Tabular Parsing | Pandas | CSV, Excel |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Fast, lightweight embeddings |
| Vector Index | FAISS | Similarity search |
| Keyword Index | rank_bm25 | Term matching |
| Metadata Store | SQLite | Document metadata, entities |
| LLM Provider | Gemini API / OpenAI API | Enrichment + answer generation |
| File Watching | watchdog | Detect file changes |
| Web UI | Streamlit | User interface |
| Deployment | Docker Compose | Containerization |

---

## Summary: Key Design Decisions

1. **Dynamic LLM Entity Extraction**: No predefined schemas. LLM analyzes each document and extracts what's relevant for that specific content.

2. **First-Class CSV/Excel Support**: Tabular data gets special treatment with schema detection, natural language descriptions, and aggregated summaries.

3. **Contextual Embeddings**: Every chunk is prepended with document context (title, type, section, entities) before embedding for better semantic matching.

4. **Three-Tier Response Strategy**: Cache → Retrieval → LLM. Most queries hit fast tiers; LLM reserved for complex synthesis.

5. **Single LLM Call Per Document**: All enrichment (summary, entities, descriptions) in one API call to minimize cost and latency.

6. **Centralized Architecture**: Docker runs on one server only. Users access via browser. Admins manage files via shared folder.
