import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api, DocumentSummary } from '../api/client'
import { getFileTypeIcon } from '../utils/constants'

export default function Documents() {
  const { data: documents, isLoading, error } = useQuery({
    queryKey: ['documents'],
    queryFn: () => api.getDocuments(),
  })

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((n) => (
            <div key={n} className="card">
              <div className="h-6 bg-gray-200 rounded w-1/3 mb-2"></div>
              <div className="h-4 bg-gray-200 rounded w-2/3"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700">Failed to load documents: {(error as Error).message}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Indexed Documents</h1>
        <p className="text-gray-600 mt-1">
          {documents?.length || 0} documents in the index
        </p>
      </div>

      {documents && documents.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {documents.map((doc) => (
            <DocumentItem key={doc.id} document={doc} />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 card">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No documents indexed</h3>
          <p className="mt-2 text-gray-500">Add documents to the watched folder to start indexing</p>
        </div>
      )}
    </div>
  )
}

function DocumentItem({ document }: { document: DocumentSummary }) {
  const navigate = useNavigate()
  const icon = getFileTypeIcon(document.file_type)
  const date = new Date(document.indexed_at).toLocaleDateString()

  return (
    <div
      className="card cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => navigate(`/documents/${document.id}`)}
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{document.file_name}</h3>
          <div className="flex items-center gap-2 mt-1">
            <span className="badge-blue text-xs">{document.detected_doc_type}</span>
            <span className="text-xs text-gray-500">Indexed {date}</span>
          </div>
          {document.summary && (
            <p className="mt-2 text-sm text-gray-600 line-clamp-2">{document.summary}</p>
          )}
        </div>
      </div>
    </div>
  )
}
