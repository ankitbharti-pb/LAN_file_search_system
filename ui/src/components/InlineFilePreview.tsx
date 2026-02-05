import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, FolderItem, ProcessingStatus as ProcessingStatusType } from '../api/client'
import ProcessingStatus from './ProcessingStatus'
import LayoutPreview from './LayoutPreview'
import MarkdownEditor from './MarkdownEditor'
import { ChunkTreeView } from './ChunkTreeView'
import { ChunkMetadataPanel } from './ChunkMetadataPanel'
import { RetrievalDebugPanel } from './RetrievalDebugPanel'
import { formatFileSize } from '../utils/constants'
import { Layers, Bug, Loader2 } from 'lucide-react'

interface InlineFilePreviewProps {
  file: FolderItem
  onDelete: () => void
  onStatusChange?: () => void
}

interface TableData {
  columns: string[]
  data: (string | number | null)[][]
}

function parseTableContent(content: string): TableData | null {
  try {
    const parsed = JSON.parse(content)
    return {
      columns: parsed.columns || [],
      data: parsed.data || [],
    }
  } catch {
    return null
  }
}

type PreviewTab = 'layout' | 'markdown' | 'chunks' | 'debug'

export default function InlineFilePreview({ file, onDelete, onStatusChange }: InlineFilePreviewProps) {
  const [activeTab, setActiveTab] = useState<PreviewTab>('layout')
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: preview, isLoading, error, refetch } = useQuery({
    queryKey: ['preview', file.path],
    queryFn: () => api.previewFile(file.path),
  })

  // Get current processing status from preview or file
  const processingStatus = preview?.processing_status || file.processing_status
  const docId = preview?.doc_id || file.doc_id
  const isPdf = file.file_type === 'pdf'
  const isDocument = ['pdf', 'docx', 'pptx'].includes(file.file_type || '')
  const isTabular = ['csv', 'xlsx', 'xls'].includes(file.file_type || '')

  // Layout detection mutation
  const detectLayoutMutation = useMutation({
    mutationFn: () => {
      if (!docId) throw new Error('No document ID')
      return api.detectLayout(docId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preview', file.path] })
      queryClient.invalidateQueries({ queryKey: ['folder'] })
      onStatusChange?.()
    },
  })

  // Text extraction mutation
  const extractTextMutation = useMutation({
    mutationFn: () => {
      if (!docId) throw new Error('No document ID')
      return api.extractText(docId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preview', file.path] })
      queryClient.invalidateQueries({ queryKey: ['folder'] })
      onStatusChange?.()
    },
  })

  // Enrich chunks mutation
  const enrichMutation = useMutation({
    mutationFn: () => {
      if (!docId) throw new Error('No document ID')
      return api.enrichChunks(docId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preview', file.path] })
      queryClient.invalidateQueries({ queryKey: ['folder'] })
      onStatusChange?.()
    },
  })

  // Index vectors mutation (for tabular flow)
  const indexVectorsMutation = useMutation({
    mutationFn: () => {
      if (!docId) throw new Error('No document ID')
      return api.indexVectors(docId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preview', file.path] })
      queryClient.invalidateQueries({ queryKey: ['folder'] })
      onStatusChange?.()
    },
  })

  // Chunk document mutation (for document flow)
  const chunkDocumentMutation = useMutation({
    mutationFn: () => {
      if (!docId) throw new Error('No document ID')
      return api.chunkDocument(docId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preview', file.path] })
      queryClient.invalidateQueries({ queryKey: ['folder'] })
      onStatusChange?.()
    },
  })

  const handleDownload = () => {
    window.open(api.getDownloadUrl(file.path), '_blank')
  }

  // Processing button states
  const canDetectLayout = isPdf && processingStatus === 'pending'
  const canExtractText = isDocument && (processingStatus === 'layout_detected' || (!isPdf && processingStatus === 'pending'))
  const canChunk = docId && (
    (isTabular && processingStatus === 'pending') ||
    (isDocument && (processingStatus === 'text_extracted' || processingStatus === 'reviewed'))
  )
  const canEnrich = processingStatus === 'chunked'
  const canIndex = processingStatus === 'enriched'

  // Completed states
  const layoutCompleted = ['layout_detected', 'text_extracted', 'reviewed', 'chunked', 'enriched', 'indexed'].includes(processingStatus || '')
  const extractCompleted = ['text_extracted', 'reviewed', 'chunked', 'enriched', 'indexed'].includes(processingStatus || '')
  const chunkCompleted = ['chunked', 'enriched', 'indexed'].includes(processingStatus || '')
  const enrichCompleted = ['enriched', 'indexed'].includes(processingStatus || '')
  const indexCompleted = processingStatus === 'indexed'

  // Tab visibility
  const showLayoutTab = isPdf && !isTabular && ['layout_detected', 'text_extracted', 'reviewed', 'chunked', 'enriched', 'indexed'].includes(processingStatus || '')
  const showMarkdownTab = !isTabular && ['text_extracted', 'reviewed', 'chunked', 'enriched', 'indexed'].includes(processingStatus || '')
  const showChunksTab = ['chunked', 'enriched', 'indexed'].includes(processingStatus || '')
  const showDebugTab = processingStatus === 'indexed'

  // Auto-switch to first available tab when visibility changes
  useEffect(() => {
    const isCurrentTabVisible =
      (activeTab === 'layout' && showLayoutTab) ||
      (activeTab === 'markdown' && showMarkdownTab) ||
      (activeTab === 'chunks' && showChunksTab) ||
      (activeTab === 'debug' && showDebugTab)

    if (!isCurrentTabVisible) {
      // Switch to first available tab
      if (showLayoutTab) setActiveTab('layout')
      else if (showMarkdownTab) setActiveTab('markdown')
      else if (showChunksTab) setActiveTab('chunks')
      else if (showDebugTab) setActiveTab('debug')
    }
  }, [showLayoutTab, showMarkdownTab, showChunksTab, showDebugTab, activeTab])

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* File Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-gray-50 border-b">
        <div className="flex items-center gap-3">
          <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{file.name}</h2>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span>{file.file_type?.toUpperCase() || 'FILE'}</span>
              {file.size && <span>&bull; {formatFileSize(file.size)}</span>}
              {preview?.page_count && <span>&bull; {preview.page_count} pages</span>}
              <ProcessingStatus status={processingStatus as ProcessingStatusType} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Processing action buttons */}
          {docId && (
            <>
              {/* Detect Layout - PDF only */}
              {isPdf && (
                <button
                  onClick={() => detectLayoutMutation.mutate()}
                  disabled={!canDetectLayout || detectLayoutMutation.isPending}
                  className={`px-3 py-1.5 text-sm rounded transition-colors flex items-center gap-1 ${
                    layoutCompleted
                      ? 'bg-green-100 text-green-700'
                      : canDetectLayout
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  {detectLayoutMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : layoutCompleted ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                    </svg>
                  )}
                  Layout
                </button>
              )}

              {/* Extract Text - Documents only */}
              {isDocument && (
                <button
                  onClick={() => extractTextMutation.mutate()}
                  disabled={!canExtractText || extractTextMutation.isPending}
                  className={`px-3 py-1.5 text-sm rounded transition-colors flex items-center gap-1 ${
                    extractCompleted
                      ? 'bg-green-100 text-green-700'
                      : canExtractText
                      ? 'bg-yellow-500 text-white hover:bg-yellow-600'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  {extractTextMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : extractCompleted ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  )}
                  Extract
                </button>
              )}

              {/* Chunk */}
              <button
                onClick={() => chunkDocumentMutation.mutate()}
                disabled={!canChunk || chunkDocumentMutation.isPending}
                className={`px-3 py-1.5 text-sm rounded transition-colors flex items-center gap-1 ${
                  chunkCompleted
                    ? 'bg-green-100 text-green-700'
                    : canChunk
                    ? 'bg-cyan-600 text-white hover:bg-cyan-700'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {chunkDocumentMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : chunkCompleted ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <Layers className="w-4 h-4" />
                )}
                Chunk
              </button>

              {/* Enrich */}
              <button
                onClick={() => enrichMutation.mutate()}
                disabled={!canEnrich || enrichMutation.isPending}
                className={`px-3 py-1.5 text-sm rounded transition-colors flex items-center gap-1 ${
                  enrichCompleted
                    ? 'bg-green-100 text-green-700'
                    : canEnrich
                    ? 'bg-purple-600 text-white hover:bg-purple-700'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {enrichMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : enrichCompleted ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                )}
                Enrich
              </button>

              {/* Index */}
              <button
                onClick={() => indexVectorsMutation.mutate()}
                disabled={!canIndex || indexVectorsMutation.isPending}
                className={`px-3 py-1.5 text-sm rounded transition-colors flex items-center gap-1 ${
                  indexCompleted
                    ? 'bg-green-100 text-green-700'
                    : canIndex
                    ? 'bg-green-600 text-white hover:bg-green-700'
                    : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                }`}
              >
                {indexVectorsMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : indexCompleted ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                )}
                Index
              </button>
            </>
          )}

          <div className="w-px h-6 bg-gray-300 mx-1" />

          <button
            onClick={handleDownload}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download
          </button>
          <button
            onClick={onDelete}
            className="px-3 py-1.5 text-sm bg-red-600 text-white rounded hover:bg-red-700 transition-colors flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Delete
          </button>
        </div>
      </div>

      {/* Processing workflow tabs */}
      {docId && (showLayoutTab || showMarkdownTab || showChunksTab || showDebugTab) && (
        <div className="border-b">
          <div className="flex">
            {/* Layout tab - only for PDFs with layout detection */}
            {showLayoutTab && (
              <button
                onClick={() => setActiveTab('layout')}
                className={`px-4 py-2 text-sm font-medium border-b-2 flex items-center gap-2 ${
                  activeTab === 'layout'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                </svg>
                Layout
              </button>
            )}

            {/* Markdown tab - when text is extracted (not for tabular) */}
            {showMarkdownTab && (
              <button
                onClick={() => setActiveTab('markdown')}
                className={`px-4 py-2 text-sm font-medium border-b-2 flex items-center gap-2 ${
                  activeTab === 'markdown'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Markdown
              </button>
            )}

            {/* Chunks tab - after chunking */}
            {showChunksTab && (
              <button
                onClick={() => setActiveTab('chunks')}
                className={`px-4 py-2 text-sm font-medium border-b-2 flex items-center gap-2 ${
                  activeTab === 'chunks'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <Layers className="w-4 h-4" />
                Chunks
              </button>
            )}

            {/* Debug tab - after indexing */}
            {showDebugTab && (
              <button
                onClick={() => setActiveTab('debug')}
                className={`px-4 py-2 text-sm font-medium border-b-2 flex items-center gap-2 ${
                  activeTab === 'debug'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                <Bug className="w-4 h-4" />
                Debug
              </button>
            )}
          </div>
        </div>
      )}

      {/* Layout Preview */}
      {activeTab === 'layout' && docId && showLayoutTab && (
        <div className="p-4">
          <LayoutPreview docId={docId} />
        </div>
      )}

      {/* Markdown Editor */}
      {activeTab === 'markdown' && docId && showMarkdownTab && (
        <div className="p-6">
          <MarkdownEditor
            docId={docId}
            onSave={() => {
              queryClient.invalidateQueries({ queryKey: ['preview', file.path] })
              queryClient.invalidateQueries({ queryKey: ['folder'] })
              onStatusChange?.()
            }}
          />
        </div>
      )}

      {/* Chunks Tab */}
      {activeTab === 'chunks' && docId && showChunksTab && (
        <div className="flex h-[500px]">
          <div className="w-1/2 border-r bg-white overflow-hidden">
            <ChunkTreeView
              documentId={docId}
              selectedChunkId={selectedChunkId || undefined}
              onSelectChunk={setSelectedChunkId}
            />
          </div>
          <div className="w-1/2 bg-white overflow-hidden">
            <ChunkMetadataPanel documentId={docId} chunkId={selectedChunkId} />
          </div>
        </div>
      )}

      {/* Debug Tab */}
      {activeTab === 'debug' && docId && showDebugTab && (
        <div className="h-[500px] bg-white">
          <RetrievalDebugPanel
            documentId={docId}
            onSelectChunk={(chunkId) => {
              setSelectedChunkId(chunkId)
              setActiveTab('chunks')
            }}
          />
        </div>
      )}

      {/* Default content area - shown when no tabs are visible or for status messages */}
      {(!showLayoutTab && !showMarkdownTab && !showChunksTab && !showDebugTab) && (
        <div className="p-6">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            </div>
          )}

          {error && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg">
              Failed to load preview: {(error as Error).message}
            </div>
          )}

          {preview && (
            <>
              {/* Indexed summary */}
              {preview.indexed_summary && (
                <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
                  <h3 className="text-sm font-medium text-blue-900 mb-2">Document Summary</h3>
                  <p className="text-sm text-blue-800">{preview.indexed_summary}</p>
                </div>
              )}

              {/* Processing status message for pending documents */}
              {processingStatus === 'pending' && isDocument && (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
                  <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="mt-4 text-lg font-medium text-gray-900">Ready for Processing</h3>
                  <p className="mt-2 text-gray-500">
                    {isPdf
                      ? 'Click "Layout" to analyze the document structure.'
                      : 'Click "Extract" to process this document.'}
                  </p>
                </div>
              )}

              {/* Tabular file - show table preview */}
              {isTabular && preview.content_type === 'table' && preview.content && (
                <div className="overflow-x-auto">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">Table Preview (first 50 rows)</h3>
                  {(() => {
                    const tableData = parseTableContent(preview.content)
                    if (!tableData) {
                      return <p className="text-gray-500">Unable to parse table data</p>
                    }
                    return (
                      <table className="min-w-full divide-y divide-gray-200 border rounded-lg overflow-hidden">
                        <thead className="bg-gray-50">
                          <tr>
                            {tableData.columns.map((col, i) => (
                              <th
                                key={i}
                                className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-r last:border-r-0"
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {tableData.data.map((row, i) => (
                            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                              {row.map((cell, j) => (
                                <td
                                  key={j}
                                  className="px-3 py-2 text-sm text-gray-900 border-r last:border-r-0 whitespace-nowrap"
                                >
                                  {cell !== null ? String(cell) : ''}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )
                  })()}
                  <p className="mt-4 text-sm text-gray-500">
                    Click "Chunk" to parse and prepare this data for AI enrichment.
                  </p>
                </div>
              )}

              {/* Unsupported file type */}
              {!isDocument && !isTabular && (
                <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
                  <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="mt-4 text-lg font-medium text-gray-900">File Preview</h3>
                  <p className="mt-2 text-gray-500">
                    Download the file to view its contents.
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Mutation errors - shown at the bottom */}
      {(detectLayoutMutation.error || extractTextMutation.error ||
        chunkDocumentMutation.error || enrichMutation.error || indexVectorsMutation.error) && (
        <div className="p-4 border-t bg-red-50">
          {detectLayoutMutation.error && (
            <div className="text-red-700 text-sm mb-2">
              Layout detection failed: {(detectLayoutMutation.error as Error).message}
            </div>
          )}
          {extractTextMutation.error && (
            <div className="text-red-700 text-sm mb-2">
              Text extraction failed: {(extractTextMutation.error as Error).message}
            </div>
          )}
          {chunkDocumentMutation.error && (
            <div className="text-red-700 text-sm mb-2">
              Chunking failed: {(chunkDocumentMutation.error as Error).message}
            </div>
          )}
          {enrichMutation.error && (
            <div className="text-red-700 text-sm mb-2">
              Enrichment failed: {(enrichMutation.error as Error).message}
            </div>
          )}
          {indexVectorsMutation.error && (
            <div className="text-red-700 text-sm">
              Vector indexing failed: {(indexVectorsMutation.error as Error).message}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
