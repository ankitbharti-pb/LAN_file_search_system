import { SearchResult } from '../api/client'
import { FILE_TYPE_ICONS } from '../utils/constants'

interface DocumentCardProps {
  result: SearchResult
}

export default function DocumentCard({ result }: DocumentCardProps) {
  const fileInfo = FILE_TYPE_ICONS[result.file_type] || { icon: '📄', color: 'bg-gray-100 text-gray-700' }

  // Calculate relevance percentage
  const relevancePercent = Math.min(Math.round(result.score * 100), 100)

  return (
    <div className="card hover:border-primary-200">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={`text-2xl p-2 rounded-lg ${fileInfo.color}`}>
            {fileInfo.icon}
          </span>
          <div>
            <h3 className="font-semibold text-gray-900">{result.file_name}</h3>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="badge-blue">{result.detected_doc_type}</span>
              {result.heading_path && (
                <span className="text-gray-400">• {result.heading_path}</span>
              )}
              {result.page && (
                <span className="text-gray-400">• Page {result.page}</span>
              )}
              {result.sheet_name && (
                <span className="text-gray-400">• Sheet: {result.sheet_name}</span>
              )}
            </div>
          </div>
        </div>

        {/* Relevance Score */}
        <div className="text-right">
          <div className="text-sm font-medium text-gray-900">{relevancePercent}%</div>
          <div className="text-xs text-gray-500">relevance</div>
        </div>
      </div>

      {/* Content Preview */}
      <div className="mb-4">
        <p className="text-gray-700 text-sm leading-relaxed line-clamp-3">
          {result.chunk_text}
        </p>
      </div>

      {/* Highlights */}
      {result.highlights.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-gray-500 uppercase mb-2">Matching excerpts</h4>
          <div className="space-y-1">
            {result.highlights.slice(0, 2).map((highlight, idx) => (
              <p key={idx} className="text-sm text-gray-600 bg-yellow-50 px-2 py-1 rounded">
                {highlight}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Entities */}
      {Object.keys(result.entities).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.entities).slice(0, 5).map(([key, value]) => (
            <span key={key} className="badge-gray text-xs">
              {key}: {String(value).slice(0, 30)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
