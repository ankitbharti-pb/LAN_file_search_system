import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Bug, Zap, FileText, MessageCircle, Hash, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { api, SearchResponse, SourceInfo } from '../api/client'
import SearchBar from '../components/SearchBar'
import SearchResults from '../components/SearchResults'
import { SourcePreviewModal } from '../components/SourcePreviewModal'

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
          <div className="flex items-center justify-between mb-6 text-sm text-gray-500">
            <span>
              Found {response.total_results} results in {response.latency_ms.toFixed(0)}ms
            </span>
            <div className="flex items-center gap-4">
              {response.cache_hit && (
                <span className="badge-green">Cache Hit</span>
              )}
              <span className="badge-gray capitalize">{response.response_tier}</span>
            </div>
          </div>

          {/* AI Answer (if synthesis mode) */}
          {response.answer && (
            <div className="card mb-6 bg-primary-50 border-primary-200">
              <div className="flex items-center gap-2 mb-3">
                <svg className="h-5 w-5 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                <h3 className="font-semibold text-primary-700">AI Answer</h3>
              </div>
              <p className="text-gray-700 whitespace-pre-wrap">{response.answer}</p>
            </div>
          )}

          {/* Sources - Always show when available */}
          {response.sources && response.sources.length > 0 && (
            <div className="card mb-6 bg-gray-50 border-gray-200">
              <h4 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Sources ({response.sources.length} document{response.sources.length > 1 ? 's' : ''} used)
              </h4>
              <div className="flex flex-wrap gap-2">
                {response.sources.map((source) => (
                  <button
                    key={source.document_id}
                    onClick={() => setPreviewSource(source)}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-white rounded-lg border border-gray-200 text-sm hover:border-blue-400 hover:shadow-sm transition-all cursor-pointer"
                  >
                    <span className="font-medium text-gray-800">{source.file_name}</span>
                    <span className="text-gray-500 text-xs">
                      ({source.chunks_used} chunk{source.chunks_used > 1 ? 's' : ''})
                    </span>
                    <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
                      {source.detected_doc_type}
                    </span>
                    <ExternalLink className="w-3 h-3 text-gray-400" />
                  </button>
                ))}
              </div>
            </div>
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
