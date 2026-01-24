import { useState, useEffect } from 'react'
import { Download, FileText, X } from 'lucide-react'
import { api, SourceInfo, Document } from '../api/client'
import { Modal } from './Modal'
import { ChunkTreeView } from './ChunkTreeView'
import { ChunkMetadataPanel } from './ChunkMetadataPanel'

interface SourcePreviewModalProps {
  isOpen: boolean
  onClose: () => void
  source: SourceInfo
}

export function SourcePreviewModal({ isOpen, onClose, source }: SourcePreviewModalProps) {
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)
  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch document details on open (to get file_path for download)
  useEffect(() => {
    if (isOpen && source.document_id) {
      loadDocument()
    }
  }, [isOpen, source.document_id])

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setSelectedChunkId(null)
      setDocument(null)
      setLoading(true)
      setError(null)
    }
  }, [isOpen])

  const loadDocument = async () => {
    setLoading(true)
    setError(null)
    try {
      const doc = await api.getDocument(source.document_id)
      setDocument(doc)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (document?.file_path) {
      window.open(api.getDownloadUrl(document.file_path), '_blank')
    }
  }

  // First matched chunk for auto-selection
  const initialChunkId = source.chunk_ids[0]

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="full" hideCloseButton>
      <div className="flex flex-col h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
          <div className="flex items-center gap-3">
            <FileText className="w-6 h-6 text-gray-400" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">{source.file_name}</h2>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
                  {source.detected_doc_type}
                </span>
                <span className="text-yellow-600">
                  {source.chunks_used} chunk{source.chunks_used !== 1 ? 's' : ''} matched
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              disabled={!document?.file_path}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="w-4 h-4" />
              Download
            </button>
            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center p-8">
              <p className="text-red-600 font-medium">Error loading document</p>
              <p className="text-sm text-gray-500 mt-1">{error}</p>
              <button
                onClick={loadDocument}
                className="mt-4 text-blue-600 hover:underline text-sm"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex min-h-0">
            {/* Left panel - Chunk Tree */}
            <div className="w-2/5 border-r overflow-hidden flex flex-col">
              <ChunkTreeView
                documentId={source.document_id}
                selectedChunkId={selectedChunkId || undefined}
                highlightedChunkIds={source.chunk_ids}
                initialChunkId={initialChunkId}
                onSelectChunk={setSelectedChunkId}
              />
            </div>

            {/* Right panel - Chunk Metadata */}
            <div className="w-3/5 overflow-hidden">
              <ChunkMetadataPanel
                documentId={source.document_id}
                chunkId={selectedChunkId}
              />
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}
