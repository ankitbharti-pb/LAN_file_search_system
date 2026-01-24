import { useState, useCallback } from 'react'

interface CreateFolderModalProps {
  onClose: () => void
  onCreate: (name: string) => void
  isLoading: boolean
  error?: string
}

export default function CreateFolderModal({ onClose, onCreate, isLoading, error }: CreateFolderModalProps) {
  const [folderName, setFolderName] = useState('')
  const [validationError, setValidationError] = useState('')

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()

    // Validate folder name
    const trimmedName = folderName.trim()
    if (!trimmedName) {
      setValidationError('Folder name is required')
      return
    }

    const invalidChars = '<>:"/\\|?*'
    if ([...invalidChars].some(c => trimmedName.includes(c))) {
      setValidationError(`Folder name cannot contain: ${invalidChars}`)
      return
    }

    if (trimmedName.startsWith('.')) {
      setValidationError('Folder name cannot start with a dot')
      return
    }

    setValidationError('')
    onCreate(trimmedName)
  }, [folderName, onCreate])

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">Create New Folder</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4">
            <label htmlFor="folderName" className="block text-sm font-medium text-gray-700 mb-2">
              Folder Name
            </label>
            <input
              id="folderName"
              type="text"
              value={folderName}
              onChange={(e) => {
                setFolderName(e.target.value)
                setValidationError('')
              }}
              placeholder="Enter folder name"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              autoFocus
              disabled={isLoading}
            />

            {(validationError || error) && (
              <p className="mt-2 text-sm text-red-600">
                {validationError || error}
              </p>
            )}
          </div>

          <div className="flex justify-end gap-3 px-6 py-4 border-t bg-gray-50">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
              disabled={isLoading || !folderName.trim()}
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Creating...
                </span>
              ) : (
                'Create Folder'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
