import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'

interface MarkdownEditorProps {
  docId: string
  onSave?: () => void
}

export function MarkdownEditor({ docId, onSave }: MarkdownEditorProps) {
  const [editedMarkdown, setEditedMarkdown] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const queryClient = useQueryClient()

  // Fetch markdown content
  const { data: markdownData, isLoading, error } = useQuery({
    queryKey: ['markdown', docId],
    queryFn: () => api.getMarkdown(docId),
  })

  // Initialize edited content when data loads
  useEffect(() => {
    if (markdownData) {
      const content = markdownData.reviewed_markdown || markdownData.extracted_markdown || ''
      setEditedMarkdown(content)
      setHasChanges(false)
    }
  }, [markdownData])

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (markdown: string) => api.updateMarkdown(docId, markdown),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['markdown', docId] })
      queryClient.invalidateQueries({ queryKey: ['preview'] })
      queryClient.invalidateQueries({ queryKey: ['folder'] })
      setHasChanges(false)
      setIsEditing(false)
      onSave?.()
    },
  })

  const handleTextChange = (value: string) => {
    setEditedMarkdown(value)
    const originalContent = markdownData?.reviewed_markdown || markdownData?.extracted_markdown || ''
    setHasChanges(value !== originalContent)
  }

  const handleSave = () => {
    saveMutation.mutate(editedMarkdown)
  }

  const handleCancel = () => {
    const originalContent = markdownData?.reviewed_markdown || markdownData?.extracted_markdown || ''
    setEditedMarkdown(originalContent)
    setHasChanges(false)
    setIsEditing(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <svg className="w-8 h-8 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        Failed to load markdown: {(error as Error).message}
      </div>
    )
  }

  if (!markdownData?.extracted_markdown) {
    return (
      <div className="text-center py-12 bg-gray-50 rounded-lg border border-gray-200">
        <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 className="mt-4 text-lg font-medium text-gray-900">No markdown content</h3>
        <p className="mt-2 text-gray-500">
          Run text extraction first to generate markdown content.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-medium text-gray-700">Extracted Markdown</h3>
          {markdownData.reviewed_markdown && (
            <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">
              Reviewed
            </span>
          )}
          {hasChanges && (
            <span className="px-2 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded-full">
              Unsaved changes
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!isEditing ? (
            <button
              onClick={() => setIsEditing(true)}
              className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              Edit
            </button>
          ) : (
            <>
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={!hasChanges || saveMutation.isPending}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                {saveMutation.isPending && (
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                )}
                Save Changes
              </button>
            </>
          )}
        </div>
      </div>

      {/* Content area */}
      {isEditing ? (
        <textarea
          value={editedMarkdown}
          onChange={(e) => handleTextChange(e.target.value)}
          className="w-full h-[500px] p-4 font-mono text-sm bg-gray-50 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
          placeholder="Markdown content..."
        />
      ) : (
        <div className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden">
          {/* Simple markdown preview - render as formatted text */}
          <div className="p-4 max-h-[500px] overflow-y-auto">
            <MarkdownPreview content={editedMarkdown} />
          </div>
        </div>
      )}

      {/* Error message */}
      {saveMutation.error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          Failed to save: {(saveMutation.error as Error).message}
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-gray-500">
        <span>{editedMarkdown.length.toLocaleString()} characters</span>
        <span>{editedMarkdown.split('\n').length.toLocaleString()} lines</span>
      </div>
    </div>
  )
}

// Simple markdown preview component
function MarkdownPreview({ content }: { content: string }) {
  // Parse markdown into simple formatted output
  const lines = content.split('\n')

  return (
    <div className="prose prose-sm max-w-none">
      {lines.map((line, i) => {
        const trimmed = line.trim()

        // Images: ![alt](url) - standalone image on its own line
        const imageMatch = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/)
        if (imageMatch) {
          const [, alt, src] = imageMatch
          return (
            <div key={i} className="my-2">
              <img
                src={src}
                alt={alt || 'Figure'}
                className="max-w-full h-auto rounded border border-gray-200"
                loading="lazy"
              />
            </div>
          )
        }

        // Lines containing inline images
        if (trimmed.includes('![') && trimmed.includes('](')) {
          const parts = trimmed.split(/(!\[[^\]]*\]\([^)]+\))/)
          return (
            <p key={i} className="text-sm text-gray-700 my-1">
              {parts.map((part, j) => {
                const imgMatch = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/)
                if (imgMatch) {
                  const [, imgAlt, imgSrc] = imgMatch
                  return (
                    <img
                      key={j}
                      src={imgSrc}
                      alt={imgAlt || 'Figure'}
                      className="max-w-full h-auto rounded border border-gray-200 inline-block my-2"
                      loading="lazy"
                    />
                  )
                }
                return <span key={j}>{part}</span>
              })}
            </p>
          )
        }

        // Headers
        if (trimmed.startsWith('######')) {
          return <h6 key={i} className="text-xs font-bold text-gray-700 mt-2 mb-1">{trimmed.slice(6).trim()}</h6>
        }
        if (trimmed.startsWith('#####')) {
          return <h5 key={i} className="text-xs font-bold text-gray-800 mt-2 mb-1">{trimmed.slice(5).trim()}</h5>
        }
        if (trimmed.startsWith('####')) {
          return <h4 key={i} className="text-sm font-bold text-gray-800 mt-3 mb-1">{trimmed.slice(4).trim()}</h4>
        }
        if (trimmed.startsWith('###')) {
          return <h3 key={i} className="text-sm font-bold text-gray-900 mt-3 mb-1">{trimmed.slice(3).trim()}</h3>
        }
        if (trimmed.startsWith('##')) {
          return <h2 key={i} className="text-base font-bold text-gray-900 mt-4 mb-2">{trimmed.slice(2).trim()}</h2>
        }
        if (trimmed.startsWith('#')) {
          return <h1 key={i} className="text-lg font-bold text-gray-900 mt-4 mb-2">{trimmed.slice(1).trim()}</h1>
        }

        // Horizontal rule
        if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
          return <hr key={i} className="my-4 border-gray-300" />
        }

        // List items
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={i} className="flex items-start gap-2 ml-2">
              <span className="text-gray-400">-</span>
              <span className="text-sm text-gray-700">{trimmed.slice(2)}</span>
            </div>
          )
        }

        // Numbered list
        if (/^\d+\.\s/.test(trimmed)) {
          const [num, ...rest] = trimmed.split(/\.\s/)
          return (
            <div key={i} className="flex items-start gap-2 ml-2">
              <span className="text-gray-400">{num}.</span>
              <span className="text-sm text-gray-700">{rest.join('. ')}</span>
            </div>
          )
        }

        // Code block marker
        if (trimmed.startsWith('```')) {
          return <div key={i} className="text-xs text-gray-500 font-mono bg-gray-100 px-2 py-0.5 rounded">{trimmed}</div>
        }

        // Table rows
        if (trimmed.startsWith('|')) {
          return (
            <div key={i} className="font-mono text-xs text-gray-700 bg-gray-50 px-2 overflow-x-auto">
              {trimmed}
            </div>
          )
        }

        // Bold text (simple)
        if (trimmed.includes('**')) {
          const parts = trimmed.split(/\*\*/)
          return (
            <p key={i} className="text-sm text-gray-700 my-1">
              {parts.map((part, j) =>
                j % 2 === 1 ? <strong key={j}>{part}</strong> : part
              )}
            </p>
          )
        }

        // Italic text
        if (trimmed.startsWith('*') && trimmed.endsWith('*') && !trimmed.startsWith('**')) {
          return <em key={i} className="text-sm text-gray-600 my-1 block">{trimmed.slice(1, -1)}</em>
        }

        // Empty line
        if (!trimmed) {
          return <div key={i} className="h-2" />
        }

        // Regular paragraph
        return <p key={i} className="text-sm text-gray-700 my-1">{line}</p>
      })}
    </div>
  )
}

export default MarkdownEditor
