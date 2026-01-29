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


RESPONSE_SYNTHESIS_PROMPT = """Based on the following search results, provide a comprehensive answer to the user's question.

USER QUESTION: {query}

SEARCH RESULTS:
{results}

Instructions:
1. Synthesize information from the relevant results
2. Cite sources by document name when appropriate
3. Be concise but complete
4. If the results don't contain enough information to answer, say so
5. Don't make up information not present in the results

Provide a clear, helpful answer:"""
