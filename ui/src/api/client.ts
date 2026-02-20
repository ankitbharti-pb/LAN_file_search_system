// API Types
export interface SearchResult {
  document_id: string
  file_name: string
  file_type: string
  detected_doc_type: string
  chunk_text: string
  chunk_id: string
  score: number
  page?: number
  sheet_name?: string
  heading_path?: string
  highlights: string[]
  entities: Record<string, unknown>
  temporal_context?: string
  chunk_title?: string
}

export interface SourceInfo {
  document_id: string
  file_name: string
  file_type: string
  detected_doc_type: string
  chunks_used: number
  chunk_ids: string[]
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  answer?: string
  total_results: number
  latency_ms: number
  cache_hit: boolean
  response_tier: 'cache' | 'retrieval' | 'synthesis'
  sources?: SourceInfo[]
}

export interface DocumentSummary {
  id: string
  file_name: string
  file_type: string
  detected_doc_type: string
  summary: string
  indexed_at: string
}

export interface Document extends DocumentSummary {
  file_path: string
  file_hash: string
  entities: Record<string, unknown>
  key_topics: string[]
  table_descriptions: string[]
  sheet_names?: string[]
  column_schema?: Record<string, string>
  row_count?: number
  date_range?: string
  processing_status?: 'pending' | 'layout_detected' | 'text_extracted' | 'chunked' | 'enriched' | 'reviewed' | 'indexed'
}

export interface Stats {
  total_documents: number
  total_chunks: number
  documents_by_detected_type: Record<string, number>
  documents_by_file_type: Record<string, number>
  // Multi-vector index stats
  main_vectors: number
  summary_vectors: number
  question_vectors: number
  keyword_index_size: number
  cache_entries: number
}

export interface ReindexStatus {
  status: string
  processed: number
  failed: number
  skipped: number
  message: string
}

// File Browser Types
export interface FolderItem {
  name: string
  type: 'file' | 'folder'
  path: string
  size?: number
  file_type?: string
  is_supported: boolean
  is_indexed: boolean
  modified_at: string
  // Processing workflow fields
  doc_id?: string
  processing_status?: 'pending' | 'layout_detected' | 'text_extracted' | 'chunked' | 'enriched' | 'reviewed' | 'indexed'
}

export interface FolderContents {
  current_path: string
  parent_path?: string
  items: FolderItem[]
}

export interface UploadResponse {
  uploaded: string[]
  failed: string[]
  message: string
}

export interface FilePreview {
  name: string
  path: string
  file_type: string
  size: number
  content_type: 'text' | 'table' | 'binary'
  content?: string
  is_indexed: boolean
  indexed_summary?: string
  // Processing workflow fields
  doc_id?: string
  processing_status?: 'pending' | 'layout_detected' | 'text_extracted' | 'chunked' | 'enriched' | 'reviewed' | 'indexed'
  page_count?: number
}

// Processing Types
export type ProcessingStatus = 'pending' | 'layout_detected' | 'text_extracted' | 'chunked' | 'enriched' | 'reviewed' | 'indexed'

export interface LayoutDetectionResponse {
  document_id: string
  pages: number
  status: string
}

export interface PageInfo {
  page_number: number
  has_image: boolean
  has_annotated_image: boolean
  has_unfiltered_annotated_image: boolean
  has_layout: boolean
  detection_count: number
  unfiltered_detection_count: number
  boxes_removed_by_filter: number
}

export interface PagesListResponse {
  document_id: string
  total_pages: number
  pages: PageInfo[]
}

export interface Detection {
  bbox: [number, number, number, number]
  label: string
  confidence: number
}

export interface PageLayoutResponse {
  page_number: number
  detections: Detection[]
}

export interface MarkdownResponse {
  document_id: string
  extracted_markdown?: string
  reviewed_markdown?: string
  processing_status: string
}

export interface DeleteResponse {
  path: string
  was_indexed: boolean
  message: string
}

// Chunking Types
export interface ChunkResponse {
  id: string
  document_id: string
  text: string
  content_type: string
  hierarchy_level: number
  parent_chunk_id?: string
  heading_path?: string
  chunk_index: number
  is_semantic_boundary: boolean
}

export interface ChunkMetadata {
  chunk_id: string
  title?: string
  summary?: string
  keywords: string[]
  entities: Record<string, string[]>
  category?: string
  contextual_description?: string
  enriched_at?: string
}

export interface ChunkQuestion {
  id?: number
  chunk_id: string
  question: string
  vector_id?: string
}

export interface ChunkDetailResponse {
  chunk: ChunkResponse
  metadata?: ChunkMetadata
  questions: ChunkQuestion[]
}

export interface ChunkListResponse {
  document_id: string
  total_chunks: number
  chunks: ChunkResponse[]
}

export interface ChunkTreeNode {
  id: string
  text: string
  content_type: string
  hierarchy_level: number
  title?: string
  summary?: string
  category?: string
  children: ChunkTreeNode[]
}

export interface ChunkTreeResponse {
  document_id: string
  total_chunks: number
  tree: ChunkTreeNode[]
}

export interface ChunkingResponse {
  document_id: string
  chunks_created: number
  status: string
}

export interface EnrichmentResponse {
  document_id: string
  chunks_enriched: number
  questions_generated: number
  status: string
}

export interface IndexingResponse {
  document_id: string
  main_vectors: number
  summary_vectors: number
  question_vectors: number
  status: string
}

export interface RetrievalDebugResult {
  chunk_id: string
  score: number
  matched_keywords?: string[]
}

export interface RRFScoreDetail {
  rank: number
  original_score: number
  rrf_contribution: number
}

export interface RetrievalDebugInfo {
  main_vector_results: RetrievalDebugResult[]
  summary_vector_results: RetrievalDebugResult[]
  question_vector_results: RetrievalDebugResult[]
  bm25_results: RetrievalDebugResult[]
  rrf_scores: Record<string, Record<string, RRFScoreDetail>>
  source_attribution: Record<string, string[]>
}

export interface RetrievalDebugResponse {
  query: string
  results: SearchResult[]
  debug?: RetrievalDebugInfo
}

// API Base URL
const API_BASE = import.meta.env.DEV ? '/api' : ''

// API Client
class APIClient {
  private async fetch<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Search
  async search(
    query: string,
    options?: { limit?: number; mode?: 'auto' | 'retrieval' | 'synthesis'; filters?: Record<string, unknown> }
  ): Promise<SearchResponse> {
    return this.fetch<SearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({
        query,
        limit: options?.limit ?? 10,
        mode: options?.mode ?? 'auto',
        filters: options?.filters,
      }),
    })
  }

  // Documents
  async getDocuments(skip = 0, limit = 100): Promise<DocumentSummary[]> {
    return this.fetch<DocumentSummary[]>(`/documents?skip=${skip}&limit=${limit}`)
  }

  async getDocument(id: string): Promise<Document> {
    return this.fetch<Document>(`/documents/${id}`)
  }

  // Stats
  async getStats(): Promise<Stats> {
    return this.fetch<Stats>('/stats')
  }

  // Admin
  async triggerReindex(): Promise<ReindexStatus> {
    return this.fetch<ReindexStatus>('/admin/reindex', { method: 'POST' })
  }

  async getReindexStatus(): Promise<ReindexStatus> {
    return this.fetch<ReindexStatus>('/admin/reindex/status')
  }

  async clearCache(): Promise<{ status: string; entries_cleared: number; message: string }> {
    return this.fetch('/admin/clear-cache', { method: 'POST' })
  }

  // Health
  async healthCheck(): Promise<{ status: string; version: string }> {
    return this.fetch('/health')
  }

  // File Browser
  async browseFolder(path = ''): Promise<FolderContents> {
    const encodedPath = path ? encodeURIComponent(path) : ''
    return this.fetch<FolderContents>(`/files/browse${encodedPath ? '/' + encodedPath : ''}`)
  }

  async createFolder(parentPath: string, name: string): Promise<{ path: string; message: string }> {
    return this.fetch('/files/folder', {
      method: 'POST',
      body: JSON.stringify({ parent_path: parentPath, name }),
    })
  }

  async uploadFiles(files: FileList, targetPath: string): Promise<UploadResponse> {
    const formData = new FormData()
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i])
    }
    formData.append('target_path', targetPath)

    const response = await fetch(`${API_BASE}/files/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  async previewFile(path: string): Promise<FilePreview> {
    return this.fetch<FilePreview>(`/files/preview/${encodeURIComponent(path)}`)
  }

  async deleteFile(path: string): Promise<DeleteResponse> {
    return this.fetch<DeleteResponse>(`/files/delete/${encodeURIComponent(path)}`, {
      method: 'DELETE',
    })
  }

  async deleteFolder(path: string, force = false): Promise<DeleteResponse> {
    return this.fetch<DeleteResponse>(`/files/folder/${encodeURIComponent(path)}?force=${force}`, {
      method: 'DELETE',
    })
  }

  getDownloadUrl(path: string): string {
    return `${API_BASE}/files/download/${encodeURIComponent(path)}`
  }

  // Processing API
  async detectLayout(docId: string, conf = 0.2): Promise<LayoutDetectionResponse> {
    return this.fetch<LayoutDetectionResponse>(
      `/processing/${docId}/detect-layout?conf=${conf}`,
      { method: 'POST' }
    )
  }

  async getPages(docId: string): Promise<PagesListResponse> {
    return this.fetch<PagesListResponse>(`/processing/${docId}/pages`)
  }

  getPageImageUrl(docId: string, pageNum: number): string {
    return `${API_BASE}/processing/${docId}/pages/${pageNum}/image`
  }

  getAnnotatedImageUrl(docId: string, pageNum: number): string {
    return `${API_BASE}/processing/${docId}/pages/${pageNum}/annotated`
  }

  getUnfilteredAnnotatedImageUrl(docId: string, pageNum: number): string {
    return `${API_BASE}/processing/${docId}/pages/${pageNum}/annotated-unfiltered`
  }

  async getPageLayout(docId: string, pageNum: number): Promise<PageLayoutResponse> {
    return this.fetch<PageLayoutResponse>(`/processing/${docId}/pages/${pageNum}/layout`)
  }

  async getMarkdown(docId: string): Promise<MarkdownResponse> {
    return this.fetch<MarkdownResponse>(`/processing/${docId}/markdown`)
  }

  async updateMarkdown(docId: string, markdown: string): Promise<{ status: string; message: string }> {
    return this.fetch(`/processing/${docId}/markdown`, {
      method: 'PUT',
      body: JSON.stringify({ markdown }),
    })
  }

  async extractText(docId: string): Promise<{ markdown: string; status: string }> {
    return this.fetch(`/processing/${docId}/extract-text`, { method: 'POST' })
  }

  // Chunking API
  async chunkDocument(docId: string): Promise<ChunkingResponse> {
    return this.fetch<ChunkingResponse>(`/chunking/${docId}/chunk`, { method: 'POST' })
  }

  async enrichChunks(docId: string): Promise<EnrichmentResponse> {
    return this.fetch<EnrichmentResponse>(`/chunking/${docId}/enrich`, { method: 'POST' })
  }

  async indexVectors(docId: string): Promise<IndexingResponse> {
    return this.fetch<IndexingResponse>(`/chunking/${docId}/index-vectors`, { method: 'POST' })
  }

  async getChunks(docId: string): Promise<ChunkListResponse> {
    return this.fetch<ChunkListResponse>(`/chunking/${docId}/chunks`)
  }

  async getChunkDetail(docId: string, chunkId: string): Promise<ChunkDetailResponse> {
    return this.fetch<ChunkDetailResponse>(`/chunking/${docId}/chunks/${chunkId}`)
  }

  async getChunkTree(docId: string): Promise<ChunkTreeResponse> {
    return this.fetch<ChunkTreeResponse>(`/chunking/${docId}/chunk-tree`)
  }

  async testRetrieval(docId: string, query: string, k = 10): Promise<RetrievalDebugResponse> {
    return this.fetch<RetrievalDebugResponse>(
      `/chunking/${docId}/test-retrieval?query=${encodeURIComponent(query)}&k=${k}`,
      { method: 'POST' }
    )
  }
}

export const api = new APIClient()
