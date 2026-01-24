import { useState } from 'react'
import { Search, Loader2, Zap, Hash, MessageCircle, FileText } from 'lucide-react'
import { api, RetrievalDebugResponse, RetrievalDebugResult } from '../api/client'

interface RetrievalDebugPanelProps {
  documentId: string
  onSelectChunk?: (chunkId: string) => void
}

const sourceColors: Record<string, string> = {
  main_vector: 'bg-blue-100 text-blue-700',
  summary_vector: 'bg-purple-100 text-purple-700',
  question_vector: 'bg-green-100 text-green-700',
  bm25: 'bg-orange-100 text-orange-700',
}

const sourceIcons: Record<string, React.ReactNode> = {
  main_vector: <Zap className="w-4 h-4" />,
  summary_vector: <FileText className="w-4 h-4" />,
  question_vector: <MessageCircle className="w-4 h-4" />,
  bm25: <Hash className="w-4 h-4" />,
}

function ResultColumn({
  title,
  results,
  icon,
  onSelectChunk,
  showKeywords = false,
}: {
  title: string
  results: RetrievalDebugResult[]
  icon: React.ReactNode
  onSelectChunk?: (chunkId: string) => void
  showKeywords?: boolean
}) {
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-2">
        {icon}
        <span>{title}</span>
        <span className="text-gray-400 text-xs">({results.length})</span>
      </div>
      <div className="space-y-1 max-h-64 overflow-auto">
        {results.length === 0 ? (
          <p className="text-xs text-gray-400 italic">No results</p>
        ) : (
          results.slice(0, 10).map((r, idx) => (
            <div
              key={r.chunk_id}
              className="text-xs p-1.5 bg-gray-50 rounded cursor-pointer hover:bg-gray-100"
              onClick={() => onSelectChunk?.(r.chunk_id)}
            >
              <div className="flex justify-between items-center">
                <span className="font-mono truncate text-gray-600">
                  #{idx + 1} {r.chunk_id.slice(0, 8)}
                </span>
                <span className="text-gray-500">{r.score.toFixed(3)}</span>
              </div>
              {showKeywords && r.matched_keywords && r.matched_keywords.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {r.matched_keywords.map((kw, i) => (
                    <span
                      key={i}
                      className="px-1 py-0.5 bg-orange-50 text-orange-600 rounded text-[10px]"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export function RetrievalDebugPanel({ documentId, onSelectChunk }: RetrievalDebugPanelProps) {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RetrievalDebugResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    try {
      const data = await api.testRetrieval(documentId, query.trim(), 10)
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !loading) {
      handleSearch()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search Input */}
      <div className="p-4 border-b bg-gray-50">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Enter query to test retrieval..."
            className="flex-1 px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
            Search
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 text-red-600 text-sm">{error}</div>
      )}

      {/* Results */}
      {result && (
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Retrieval Sources */}
          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">
              Retrieval Sources
            </h3>
            <div className="grid grid-cols-4 gap-3">
              <ResultColumn
                title="Main Vector"
                results={result.debug?.main_vector_results || []}
                icon={sourceIcons.main_vector}
                onSelectChunk={onSelectChunk}
              />
              <ResultColumn
                title="Question"
                results={result.debug?.question_vector_results || []}
                icon={sourceIcons.question_vector}
                onSelectChunk={onSelectChunk}
              />
              <ResultColumn
                title="Summary"
                results={result.debug?.summary_vector_results || []}
                icon={sourceIcons.summary_vector}
                onSelectChunk={onSelectChunk}
              />
              <ResultColumn
                title="BM25"
                results={result.debug?.bm25_results || []}
                icon={sourceIcons.bm25}
                onSelectChunk={onSelectChunk}
                showKeywords={true}
              />
            </div>
          </div>

          {/* RRF Fusion Results */}
          <div>
            <h3 className="text-sm font-semibold text-gray-800 mb-3">
              Final Ranking (RRF Fusion)
            </h3>
            <div className="space-y-2">
              {result.results.slice(0, 10).map((r, idx) => {
                const sources = result.debug?.source_attribution?.[r.chunk_id] || []
                const rrfDetails = result.debug?.rrf_scores?.[r.chunk_id] || {}

                return (
                  <div
                    key={r.chunk_id}
                    className="p-3 border rounded hover:bg-gray-50 cursor-pointer"
                    onClick={() => onSelectChunk?.(r.chunk_id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-blue-600">
                            #{idx + 1}
                          </span>
                          <span className="text-sm font-mono text-gray-500">
                            {r.chunk_id.slice(0, 12)}
                          </span>
                          <span className="text-sm font-medium">
                            Score: {r.score.toFixed(4)}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                          {r.chunk_text}
                        </p>
                      </div>
                    </div>

                    {/* Source Attribution */}
                    <div className="mt-2 flex flex-wrap gap-1">
                      {sources.map((source) => (
                        <span
                          key={source}
                          className={`text-xs px-2 py-0.5 rounded flex items-center gap-1 ${sourceColors[source]}`}
                        >
                          {sourceIcons[source]}
                          {source.replace('_', ' ')}
                          {rrfDetails[source] && (
                            <span className="opacity-70">
                              (rank {rrfDetails[source].rank}, +{rrfDetails[source].rrf_contribution.toFixed(4)})
                            </span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!result && !error && (
        <div className="flex-1 flex items-center justify-center text-gray-400">
          <div className="text-center">
            <Search className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>Enter a query to test retrieval</p>
            <p className="text-sm mt-1">
              See results from all retrieval sources
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
