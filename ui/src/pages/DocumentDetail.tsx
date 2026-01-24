import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  FileText,
  Layers,
  Bug,
  Loader2,
  Info,
} from 'lucide-react'
import { api, Document, ProcessingStatus as ProcessingStatusType } from '../api/client'
import { ChunkTreeView } from '../components/ChunkTreeView'
import { ChunkMetadataPanel } from '../components/ChunkMetadataPanel'
import { RetrievalDebugPanel } from '../components/RetrievalDebugPanel'
import { MarkdownEditor } from '../components/MarkdownEditor'
import ProcessingStatus from '../components/ProcessingStatus'

type TabType = 'info' | 'markdown' | 'chunks' | 'debug'

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [document, setDocument] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('info')
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)

  useEffect(() => {
    if (id) loadDocument()
  }, [id])

  const loadDocument = async () => {
    if (!id) return

    setLoading(true)
    setError(null)
    try {
      const doc = await api.getDocument(id)
      setDocument(doc)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'info', label: 'Info', icon: <Info className="w-4 h-4" /> },
    { id: 'markdown', label: 'Markdown', icon: <FileText className="w-4 h-4" /> },
    { id: 'chunks', label: 'Chunks', icon: <Layers className="w-4 h-4" /> },
    { id: 'debug', label: 'Debug', icon: <Bug className="w-4 h-4" /> },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <div className="bg-red-50 text-red-600 p-4 rounded">
          <p className="font-medium">Error loading document</p>
          <p className="text-sm">{error || 'Document not found'}</p>
          <button
            onClick={() => navigate('/documents')}
            className="mt-2 text-blue-600 hover:underline text-sm"
          >
            Back to documents
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-4 py-3">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(-1)}
            className="p-2 hover:bg-gray-100 rounded"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-lg font-semibold">{document.file_name}</h1>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span>{document.detected_doc_type}</span>
              <span>|</span>
              <span>{document.file_type}</span>
              <span>|</span>
              <ProcessingStatus status={document.processing_status as ProcessingStatusType} />
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-3">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium rounded-t flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'bg-gray-100 text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden bg-gray-50">
        {activeTab === 'info' && (
          <div className="p-6 overflow-auto h-full">
            <div className="max-w-3xl space-y-6">
              {/* Summary */}
              {document.summary && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-2">Summary</h3>
                  <p className="text-gray-600 bg-white p-4 rounded border">
                    {document.summary}
                  </p>
                </div>
              )}

              {/* Key Topics */}
              {document.key_topics && document.key_topics.length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-2">Key Topics</h3>
                  <div className="flex flex-wrap gap-2">
                    {document.key_topics.map((topic, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Entities */}
              {document.entities && Object.keys(document.entities).length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-700 mb-2">Entities</h3>
                  <div className="bg-white p-4 rounded border space-y-2">
                    {Object.entries(document.entities).map(([key, value]) => (
                      <div key={key} className="flex gap-2">
                        <span className="font-medium text-gray-600 min-w-[120px]">
                          {key}:
                        </span>
                        <span className="text-gray-700">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Metadata */}
              <div>
                <h3 className="font-medium text-gray-700 mb-2">Metadata</h3>
                <div className="bg-white p-4 rounded border text-sm space-y-1">
                  <p>
                    <span className="text-gray-500">ID:</span> {document.id}
                  </p>
                  <p>
                    <span className="text-gray-500">Path:</span> {document.file_path}
                  </p>
                  <p>
                    <span className="text-gray-500">Indexed:</span>{' '}
                    {new Date(document.indexed_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'markdown' && id && (
          <div className="h-full p-4">
            <MarkdownEditor docId={id} />
          </div>
        )}

        {activeTab === 'chunks' && id && (
          <div className="flex h-full">
            <div className="w-1/2 border-r bg-white overflow-hidden">
              <ChunkTreeView
                documentId={id}
                selectedChunkId={selectedChunkId || undefined}
                onSelectChunk={setSelectedChunkId}
              />
            </div>
            <div className="w-1/2 bg-white overflow-hidden">
              <ChunkMetadataPanel documentId={id} chunkId={selectedChunkId} />
            </div>
          </div>
        )}

        {activeTab === 'debug' && id && (
          <div className="h-full bg-white">
            <RetrievalDebugPanel
              documentId={id}
              onSelectChunk={(chunkId) => {
                setSelectedChunkId(chunkId)
                setActiveTab('chunks')
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
