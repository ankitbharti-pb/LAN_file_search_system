import { useQuery } from '@tanstack/react-query'
import { api, Document } from '../api/client'

interface DocumentPreviewProps {
  documentId: string
  onClose: () => void
}

export default function DocumentPreview({ documentId, onClose }: DocumentPreviewProps) {
  const { data: document, isLoading, error } = useQuery({
    queryKey: ['document', documentId],
    queryFn: () => api.getDocument(documentId),
  })

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b">
            <h2 className="text-lg font-semibold text-gray-900">Document Details</h2>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 overflow-y-auto max-h-[calc(90vh-120px)]">
            {isLoading && (
              <div className="animate-pulse space-y-4">
                <div className="h-6 bg-gray-200 rounded w-1/2"></div>
                <div className="h-4 bg-gray-200 rounded w-full"></div>
                <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              </div>
            )}

            {error && (
              <div className="text-red-600">
                Failed to load document: {(error as Error).message}
              </div>
            )}

            {document && <DocumentContent document={document} />}
          </div>
        </div>
      </div>
    </div>
  )
}

function DocumentContent({ document }: { document: Document }) {
  return (
    <div className="space-y-6">
      {/* File Info */}
      <div>
        <h3 className="text-xl font-semibold text-gray-900">{document.file_name}</h3>
        <div className="flex items-center gap-2 mt-2">
          <span className="badge-blue">{document.detected_doc_type}</span>
          <span className="badge-gray">{document.file_type.toUpperCase()}</span>
        </div>
      </div>

      {/* Summary */}
      {document.summary && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Summary</h4>
          <p className="text-gray-600">{document.summary}</p>
        </div>
      )}

      {/* Key Topics */}
      {document.key_topics.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Key Topics</h4>
          <div className="flex flex-wrap gap-2">
            {document.key_topics.map((topic, idx) => (
              <span key={idx} className="badge-gray">{topic}</span>
            ))}
          </div>
        </div>
      )}

      {/* Entities */}
      {Object.keys(document.entities).length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Extracted Information</h4>
          <div className="bg-gray-50 rounded-lg p-4">
            <dl className="space-y-2">
              {Object.entries(document.entities).map(([key, value]) => (
                <div key={key} className="flex">
                  <dt className="text-sm font-medium text-gray-600 w-1/3">{key}</dt>
                  <dd className="text-sm text-gray-900">{String(value)}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}

      {/* Table Descriptions */}
      {document.table_descriptions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Tables</h4>
          <ul className="list-disc list-inside space-y-1">
            {document.table_descriptions.map((desc, idx) => (
              <li key={idx} className="text-sm text-gray-600">{desc}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Sheet Names (for Excel) */}
      {document.sheet_names && document.sheet_names.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Sheets</h4>
          <div className="flex flex-wrap gap-2">
            {document.sheet_names.map((sheet, idx) => (
              <span key={idx} className="badge-gray">{sheet}</span>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="text-xs text-gray-500 pt-4 border-t">
        <p>Indexed: {new Date(document.indexed_at).toLocaleString()}</p>
        {document.row_count && <p>Rows: {document.row_count.toLocaleString()}</p>}
      </div>
    </div>
  )
}
