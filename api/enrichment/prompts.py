"""LLM prompt templates for document enrichment."""


DOCUMENT_ENRICHMENT_SYSTEM_PROMPT = """You are an expert document analyst. Your task is to analyze documents and extract key information in a structured format. Always respond with valid JSON only, no explanations."""


DOCUMENT_ENRICHMENT_PROMPT = """Analyze this document and return a JSON object with the following structure:

```json
{{
  "document_type": "string - What type of document is this? Choose from: policy_wording, endorsement, certificate_of_insurance, claim_form, underwriting_guide, premium_schedule, coverage_summary, process_document, announcement, training_material, compliance_document, regulatory_filing, agent_communication, customer_correspondence, renewal_notice, cancellation_notice, audit_report, risk_assessment, loss_run_report, policy_application, or other if none apply",
  "summary": "string - A 2-3 sentence summary of the document's main purpose and content",
  "entities": {{
    "key": "value pairs of ALL important information extracted from the document. Adapt to the document type - extract what's relevant for THIS specific document. Examples: dates, names, amounts, products, terms, metrics, etc."
  }},
  "key_topics": ["list", "of", "main", "topics", "covered"],
  "table_descriptions": ["Natural language description of any tables or data present"]
}}
```

DOCUMENT INFORMATION:
- File name: {file_name}
- File type: {file_type}

DOCUMENT CONTENT:
{content}

Respond with ONLY the JSON object, no additional text or explanation."""


TABULAR_ENRICHMENT_PROMPT = """Analyze this tabular data file and return a JSON object with the following structure:

```json
{{
  "document_type": "string - Type of data (e.g., premium_data, claims_data, policy_list, loss_run_report, commission_report, renewal_schedule, coverage_matrix, risk_analysis, underwriting_data, agent_performance, or other if none apply)",
  "summary": "string - A 2-3 sentence summary describing what this data contains and its purpose",
  "entities": {{
    "data_columns": "list of column names",
    "date_range": "date range if dates are present",
    "total_records": "number of rows",
    "key_metrics": "important summary metrics or totals",
    "categories": "distinct categories or groups in the data"
  }},
  "key_topics": ["list", "of", "main", "data", "subjects"],
  "table_descriptions": ["Natural language description of what the data shows and key insights"]
}}
```

FILE INFORMATION:
- File name: {file_name}
- File type: {file_type}
- Row count: {row_count}
- Columns: {columns}

COLUMN TYPES:
{column_types}

SAMPLE DATA:
{sample_data}

NUMERIC STATISTICS:
{numeric_stats}

Respond with ONLY the JSON object, no additional text or explanation."""


QUERY_UNDERSTANDING_PROMPT = """Analyze this search query and extract the user's intent:

Query: {query}

Return a JSON object:
```json
{{
  "search_terms": "string - core search terms for text matching",
  "doc_type_filter": "string or null - if user is looking for specific document type",
  "entity_filters": {{
    "key": "value pairs if user is filtering by specific entities (dates, amounts, names, etc.)"
  }},
  "needs_synthesis": true/false - does this query require combining information from multiple sources?,
  "query_type": "factual | exploratory | comparative | aggregation"
}}
```

Respond with ONLY the JSON object."""


RESPONSE_SYNTHESIS_PROMPT = """Answer the user's question using ONLY the search results below. Do not invent information.

QUESTION: {query}

SEARCH RESULTS:
{results}

Rules:
1. Answer ONLY what was asked. Ignore tangentially related results (e.g. question about X ≠ information about Y). Prefer higher-scoring results (score closer to 1.0).
2. If no result directly answers the question, reply: "No exact match was found for this query." and briefly note what related information is available.
3. Citations: Never reference result numbers. Cite the clause, section, or heading from WITHIN the content (e.g. "Clause 4.2", "Schedule B"). If none exists, cite Document Name + Section/Heading from metadata. Every claim needs an inline citation: *(Clause 4.2, Policy Wording)*.
4. Note temporal context — if a process changed on a date, state which version applies and when.

Format (Markdown): Start with a direct 1-2 sentence answer. Use ### headings only for distinct sub-topics, **bold** for document names and key terms, and bullet lists for steps or multiple items. Be concise."""
