import { useState, useCallback, useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api } from '../api/client'

interface FileUploadZoneProps {
  targetPath: string
  onUploadSuccess: () => void
}

export default function FileUploadZone({ targetPath, onUploadSuccess }: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploadMutation = useMutation({
    mutationFn: async (files: FileList) => {
      setUploadProgress([`Uploading ${files.length} file(s)...`])
      return api.uploadFiles(files, targetPath)
    },
    onSuccess: (data) => {
      const messages: string[] = []
      if (data.uploaded.length > 0) {
        messages.push(`Uploaded: ${data.uploaded.join(', ')}`)
      }
      if (data.failed.length > 0) {
        messages.push(`Failed: ${data.failed.join(', ')}`)
      }
      setUploadProgress(messages)
      onUploadSuccess()

      // Clear progress after a delay
      setTimeout(() => setUploadProgress([]), 5000)
    },
    onError: (error) => {
      setUploadProgress([`Error: ${(error as Error).message}`])
      setTimeout(() => setUploadProgress([]), 5000)
    },
  })

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      uploadMutation.mutate(files)
    }
  }, [uploadMutation])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files && files.length > 0) {
      uploadMutation.mutate(files)
    }
  }, [uploadMutation])

  const handleClick = useCallback(() => {
    fileInputRef.current?.click()
  }, [])

  return (
    <div className="mb-6">
      <div
        className={`
          border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer
          ${isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
          }
          ${uploadMutation.isPending ? 'opacity-50 pointer-events-none' : ''}
        `}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.xlsx,.xls,.csv,.pptx"
          onChange={handleFileSelect}
          className="hidden"
        />

        <div className="flex flex-col items-center">
          {uploadMutation.isPending ? (
            <>
              <svg className="w-10 h-10 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <p className="mt-2 text-sm text-gray-600">Uploading...</p>
            </>
          ) : (
            <>
              <svg className="w-10 h-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="mt-2 text-sm text-gray-600">
                <span className="font-medium text-blue-600">Click to upload</span> or drag and drop
              </p>
              <p className="mt-1 text-xs text-gray-500">
                PDF, DOCX, XLSX, XLS, CSV, PPTX (max 100MB)
              </p>
              <p className="mt-2 text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded">
                Uploading to: <span className="font-medium">{targetPath || 'Documents (root)'}</span>
              </p>
            </>
          )}
        </div>
      </div>

      {/* Upload progress/results */}
      {uploadProgress.length > 0 && (
        <div className="mt-3 space-y-1">
          {uploadProgress.map((msg, i) => (
            <p
              key={i}
              className={`text-sm ${
                msg.startsWith('Error') || msg.startsWith('Failed')
                  ? 'text-red-600'
                  : 'text-green-600'
              }`}
            >
              {msg}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
