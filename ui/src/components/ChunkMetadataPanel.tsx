import { useState, useEffect } from 'react'
import {
  Tag,
  MessageCircle,
  User,
  Building,
  Calendar,
  DollarSign,
  MapPin,
  Info,
  FileText,
} from 'lucide-react'
import { api, ChunkDetailResponse } from '../api/client'
import { categoryColors } from '../utils/constants'

interface ChunkMetadataPanelProps {
  documentId: string
  chunkId: string | null
}

const entityIcons: Record<string, React.ReactNode> = {
  people: <User className="w-4 h-4" />,
  organizations: <Building className="w-4 h-4" />,
  dates: <Calendar className="w-4 h-4" />,
  amounts: <DollarSign className="w-4 h-4" />,
  locations: <MapPin className="w-4 h-4" />,
}

export function ChunkMetadataPanel({ documentId, chunkId }: ChunkMetadataPanelProps) {
  const [data, setData] = useState<ChunkDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (chunkId) {
      loadChunkDetail()
    } else {
      setData(null)
    }
  }, [documentId, chunkId])

  const loadChunkDetail = async () => {
    if (!chunkId) return

    setLoading(true)
    setError(null)
    try {
      const result = await api.getChunkDetail(documentId, chunkId)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chunk details')
    } finally {
      setLoading(false)
    }
  }

  if (!chunkId) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="text-center">
          <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>Select a chunk to view details</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded m-4">
        <p className="font-medium">Error loading chunk details</p>
        <p className="text-sm">{error}</p>
      </div>
    )
  }

  if (!data) {
    return null
  }

  const { chunk, metadata, questions } = data

  return (
    <div className="p-4 space-y-4 overflow-auto h-full">
      {/* Title & Category */}
      <div className="border-b pb-3">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-lg">
            {metadata?.title || 'Untitled Chunk'}
          </h3>
          {metadata?.category && (
            <span
              className={`px-2 py-1 text-xs font-medium rounded border ${
                categoryColors[metadata.category] || 'bg-gray-100 text-gray-600'
              }`}
            >
              {metadata.category}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mt-1">
          {chunk.content_type} | Level {chunk.hierarchy_level}
          {chunk.heading_path && ` | ${chunk.heading_path}`}
        </p>
      </div>

      {/* Summary */}
      {metadata?.summary && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-1 flex items-center gap-1">
            <Info className="w-4 h-4" /> Summary
          </h4>
          <p className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
            {metadata.summary}
          </p>
        </div>
      )}

      {/* Original Text */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-1 flex items-center gap-1">
          <FileText className="w-4 h-4" /> Content
        </h4>
        <div className="text-sm text-gray-600 bg-gray-50 p-2 rounded max-h-40 overflow-auto">
          {chunk.text}
        </div>
      </div>

      {/* Keywords */}
      {metadata?.keywords && metadata.keywords.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-1 flex items-center gap-1">
            <Tag className="w-4 h-4" /> Keywords
          </h4>
          <div className="flex flex-wrap gap-1">
            {metadata.keywords.map((keyword, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded-full"
              >
                {keyword}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Entities */}
      {metadata?.entities && Object.keys(metadata.entities).length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Entities</h4>
          <div className="space-y-2">
            {Object.entries(metadata.entities).map(([type, values]) => {
              if (!values || values.length === 0) return null
              return (
                <div key={type} className="flex items-start gap-2">
                  <span className="text-gray-400 mt-0.5">
                    {entityIcons[type] || <Tag className="w-4 h-4" />}
                  </span>
                  <div className="flex-1">
                    <span className="text-xs text-gray-500 capitalize">{type}</span>
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {values.map((value: string, idx: number) => (
                        <span
                          key={idx}
                          className="px-1.5 py-0.5 text-xs bg-gray-100 text-gray-700 rounded"
                        >
                          {value}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Hypothetical Questions */}
      {questions && questions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-1 flex items-center gap-1">
            <MessageCircle className="w-4 h-4" /> Questions This Answers
          </h4>
          <ul className="space-y-1">
            {questions.map((q, idx) => (
              <li
                key={q.id || idx}
                className="text-sm text-gray-600 bg-green-50 p-2 rounded border-l-2 border-green-400"
              >
                {q.question}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Contextual Description */}
      {metadata?.contextual_description && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-1">Context</h4>
          <p className="text-sm text-gray-600 italic">
            {metadata.contextual_description}
          </p>
        </div>
      )}

      {/* Chunk Info */}
      <div className="text-xs text-gray-400 border-t pt-2">
        <p>Chunk ID: {chunk.id}</p>
        <p>Index: {chunk.chunk_index}</p>
        {chunk.is_semantic_boundary && (
          <p className="text-orange-500">Semantic boundary</p>
        )}
        {metadata?.enriched_at && (
          <p>Enriched: {new Date(metadata.enriched_at).toLocaleString()}</p>
        )}
      </div>
    </div>
  )
}
