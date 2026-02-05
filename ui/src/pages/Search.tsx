import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Bug, Zap, FileText, MessageCircle, Hash, ChevronDown, ChevronUp, ExternalLink, Sparkles } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api, SearchResponse, SourceInfo } from '../api/client'
import SearchBar from '../components/SearchBar'
import SearchResults from '../components/SearchResults'
import { SourcePreviewModal } from '../components/SourcePreviewModal'

function getDocTypeColor(docType: string): string {
  const t = docType.toLowerCase()
  if (t.includes('policy')) return 'bg-purple-100 text-purple-700'
  if (t.includes('spreadsheet') || t.includes('excel') || t.includes('premium')) return 'bg-green-100 text-green-700'
  if (t.includes('report') || t.includes('analysis')) return 'bg-blue-100 text-blue-700'
  if (t.includes('form') || t.includes('application')) return 'bg-yellow-100 text-yellow-700'
  if (t.includes('certificate') || t.includes('compliance')) return 'bg-teal-100 text-teal-700'
  if (t.includes('claim')) return 'bg-red-100 text-red-700'
  if (t.includes('guide') || t.includes('training')) return 'bg-indigo-100 text-indigo-700'
  if (t.includes('notice') || t.includes('announcement')) return 'bg-orange-100 text-orange-700'
  return 'bg-gray-100 text-gray-600'
}

export default function Search() {
  const [response, setResponse] = useState<SearchResponse | null>(null)
  const [showDebugInfo, setShowDebugInfo] = useState(false)
  const [previewSource, setPreviewSource] = useState<SourceInfo | null>(null)

  const searchMutation = useMutation({
    mutationFn: (query: string) => api.search(query, { mode: 'synthesis' }),
    onSuccess: (data) => setResponse(data),
  })

  const handleSearch = (query: string) => {
    if (query.trim()) {
      searchMutation.mutate(query)
    }
  }

  const hasSources = response?.sources && response.sources.length > 0
  const hasAnswer = !!response?.answer

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Hero Search Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Search Your Documents
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          Find information across PDFs, Word docs, Excel files, and more
        </p>
        <SearchBar
          onSearch={handleSearch}
          isLoading={searchMutation.isPending}
        />

        {/* Debug Mode Toggle */}
        <button
          onClick={() => setShowDebugInfo(!showDebugInfo)}
          className="mt-4 text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 mx-auto"
        >
          <Bug className="w-4 h-4" />
          {showDebugInfo ? 'Hide' : 'Show'} retrieval info
          {showDebugInfo ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Debug Info Panel */}
      {showDebugInfo && (
        <div className="mb-8 bg-gray-50 border rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
            <Bug className="w-5 h-5" />
            Multi-Vector Retrieval System
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            This search uses advanced RAG (Retrieval Augmented Generation) with multiple retrieval sources
            combined using Reciprocal Rank Fusion (RRF).
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white p-3 rounded border">
              <div className="flex items-center gap-2 text-blue-600 font-medium text-sm mb-1">
                <Zap className="w-4 h-4" />
                Main Vector (35%)
              </div>
              <p className="text-xs text-gray-500">
                Semantic search on contextualized chunk text
              </p>
            </div>
            <div className="bg-white p-3 rounded border">
              <div className="flex items-center gap-2 text-green-600 font-medium text-sm mb-1">
                <MessageCircle className="w-4 h-4" />
                Question Vector (25%)
              </div>
              <p className="text-xs text-gray-500">
                Matches against hypothetical questions each chunk answers
              </p>
            </div>
            <div className="bg-white p-3 rounded border">
              <div className="flex items-center gap-2 text-purple-600 font-medium text-sm mb-1">
                <FileText className="w-4 h-4" />
                Summary Vector (15%)
              </div>
              <p className="text-xs text-gray-500">
                Search on LLM-generated chunk summaries
              </p>
            </div>
            <div className="bg-white p-3 rounded border">
              <div className="flex items-center gap-2 text-orange-600 font-medium text-sm mb-1">
                <Hash className="w-4 h-4" />
                BM25 Keywords (25%)
              </div>
              <p className="text-xs text-gray-500">
                Traditional keyword matching for exact terms
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-3">
            For detailed per-document retrieval debugging, open a document and use the Debug tab.
          </p>
        </div>
      )}

      {/* Error State */}
      {searchMutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-700">
            Search failed: {searchMutation.error?.message || 'Unknown error'}
          </p>
        </div>
      )}

      {/* Results */}
      {response && (
        <div>
          {/* Stats Bar */}
          <div className="flex items-center mb-5 text-sm text-gray-400">
            <span>
              Found {response.total_results} results in {response.latency_ms.toFixed(0)}ms
            </span>
          </div>

          {/* Unified AI Answer + Sources Card */}
          {hasAnswer ? (
            <div className="ai-answer-card mb-8">
              {/* Header zone */}
              <div className="px-6 pt-5 pb-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                    <Sparkles className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="font-semibold text-gray-900">AI Answer</h3>
                </div>
                <div className="flex items-center gap-2">
                  {response.cache_hit && (
                    <span className="badge-green">Cache Hit</span>
                  )}
                  <span className="badge-gray capitalize">{response.response_tier}</span>
                </div>
              </div>

              {/* Markdown content zone */}
              <div className="px-6 pb-5">
                <div className="prose prose-sm max-w-none text-gray-700 prose-headings:text-gray-900 prose-headings:text-base prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2 prose-p:my-2 prose-p:leading-relaxed prose-li:my-0.5 prose-strong:text-gray-900 prose-code:text-primary-700 prose-code:bg-primary-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-a:text-primary-600 prose-a:no-underline hover:prose-a:underline prose-ul:my-2 prose-ol:my-2">
                  <ReactMarkdown>{response.answer}</ReactMarkdown>
                </div>
              </div>

              {/* Sources footer zone */}
              {hasSources && (
                <div className="border-t border-gray-100 bg-gray-50/80 px-6 py-4">
                  <h4 className="text-xs font-semibold text-gray-500 tracking-wide uppercase mb-3">
                    Sources ({response.sources!.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {response.sources!.map((source, index) => (
                      <button
                        key={source.document_id}
                        onClick={() => setPreviewSource(source)}
                        className="group inline-flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-gray-200 text-sm hover:border-primary-400 hover:shadow-sm transition-all cursor-pointer"
                      >
                        <span className="w-5 h-5 rounded bg-primary-100 text-primary-700 text-xs font-semibold flex items-center justify-center flex-shrink-0">
                          {index + 1}
                        </span>
                        <span className="font-medium text-gray-800">{source.file_name}</span>
                        <span className="text-gray-500 text-xs">
                          ({source.chunks_used} chunk{source.chunks_used > 1 ? 's' : ''})
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${getDocTypeColor(source.detected_doc_type)}`}>
                          {source.detected_doc_type}
                        </span>
                        <ExternalLink className="w-3 h-3 text-gray-400 group-hover:text-primary-500 transition-colors" />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Standalone sources card when no AI answer */
            hasSources && (
              <div className="card mb-8 bg-gray-50 border-gray-200">
                <h4 className="text-xs font-semibold text-gray-500 tracking-wide uppercase mb-3">
                  Sources ({response.sources!.length})
                </h4>
                <div className="flex flex-wrap gap-2">
                  {response.sources!.map((source, index) => (
                    <button
                      key={source.document_id}
                      onClick={() => setPreviewSource(source)}
                      className="group inline-flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-gray-200 text-sm hover:border-primary-400 hover:shadow-sm transition-all cursor-pointer"
                    >
                      <span className="w-5 h-5 rounded bg-primary-100 text-primary-700 text-xs font-semibold flex items-center justify-center flex-shrink-0">
                        {index + 1}
                      </span>
                      <span className="font-medium text-gray-800">{source.file_name}</span>
                      <span className="text-gray-500 text-xs">
                        ({source.chunks_used} chunk{source.chunks_used > 1 ? 's' : ''})
                      </span>
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${getDocTypeColor(source.detected_doc_type)}`}>
                        {source.detected_doc_type}
                      </span>
                      <ExternalLink className="w-3 h-3 text-gray-400 group-hover:text-primary-500 transition-colors" />
                    </button>
                  ))}
                </div>
              </div>
            )
          )}

          {/* Search Results */}
          <SearchResults results={response.results} />
        </div>
      )}

      {/* Empty State */}
      {!response && !searchMutation.isPending && (
        <div className="text-center py-12">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">Start searching</h3>
          <p className="mt-2 text-gray-500">Enter a query above to search your indexed documents</p>
        </div>
      )}

      {/* Source Preview Modal */}
      {previewSource && (
        <SourcePreviewModal
          isOpen={!!previewSource}
          onClose={() => setPreviewSource(null)}
          source={previewSource}
        />
      )}
    </div>
  )
}
