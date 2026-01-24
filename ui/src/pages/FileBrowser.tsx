import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, FolderItem } from '../api/client'
import FolderBreadcrumb from '../components/FolderBreadcrumb'
import FileTableRow from '../components/FileTableRow'
import FileUploadZone from '../components/FileUploadZone'
import CreateFolderModal from '../components/CreateFolderModal'
import InlineFilePreview from '../components/InlineFilePreview'

export default function FileBrowser() {
  const [currentPath, setCurrentPath] = useState('')
  const [showCreateFolder, setShowCreateFolder] = useState(false)
  const [viewingFile, setViewingFile] = useState<FolderItem | null>(null)
  const [uploadKey, setUploadKey] = useState(0)
  const queryClient = useQueryClient()

  // Fetch folder contents
  const { data: folderContents, isLoading, error, refetch } = useQuery({
    queryKey: ['folder', currentPath],
    queryFn: () => api.browseFolder(currentPath),
    refetchInterval: 10000,
  })

  // Create folder mutation
  const createFolderMutation = useMutation({
    mutationFn: (name: string) => api.createFolder(currentPath, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folder', currentPath] })
      setShowCreateFolder(false)
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (item: FolderItem) => {
      if (item.type === 'folder') {
        return api.deleteFolder(item.path, true)
      }
      return api.deleteFile(item.path)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folder', currentPath] })
      setViewingFile(null)
    },
    onError: (error) => {
      alert(`Delete failed: ${(error as Error).message}`)
    },
  })

  // Navigate to folder
  const handleNavigate = useCallback((path: string) => {
    setCurrentPath(path)
    setViewingFile(null)
  }, [])

  // Handle item click
  const handleItemClick = useCallback((item: FolderItem) => {
    if (item.type === 'folder') {
      setCurrentPath(item.path)
      setViewingFile(null)
    } else {
      setViewingFile(item)
    }
  }, [])

  // Handle delete
  const handleDelete = useCallback((item: FolderItem) => {
    const confirmMsg = item.type === 'folder'
      ? `Delete folder "${item.name}" and all its contents?`
      : `Delete file "${item.name}"?`

    if (window.confirm(confirmMsg)) {
      deleteMutation.mutate(item)
    }
  }, [deleteMutation])

  // Handle upload success
  const handleUploadSuccess = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['folder', currentPath] })
    setUploadKey(k => k + 1)
  }, [queryClient, currentPath])

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">File Browser</h1>
          <p className="text-gray-600 mt-1">Browse, upload, and manage your documents</p>
        </div>
        {!viewingFile && (
          <div className="flex gap-3">
            <button
              onClick={() => setShowCreateFolder(true)}
              className="btn-secondary flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
              </svg>
              New Folder
            </button>
          </div>
        )}
      </div>

      {/* Breadcrumb */}
      <FolderBreadcrumb
        currentPath={currentPath}
        fileName={viewingFile?.name}
        onNavigate={handleNavigate}
      />

      {/* File Preview View */}
      {viewingFile ? (
        <InlineFilePreview
          file={viewingFile}
          onDelete={() => handleDelete(viewingFile)}
        />
      ) : (
        <>
          {/* Upload Zone */}
          <FileUploadZone
            key={uploadKey}
            targetPath={currentPath}
            onUploadSuccess={handleUploadSuccess}
          />

          {/* Table Header */}
          <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
            <div className="flex items-center px-4 py-3 bg-gray-50 border-b text-sm font-medium text-gray-500">
              <div className="flex-1">Name</div>
              <div className="w-32 hidden sm:block">Modified</div>
              <div className="w-20 text-right hidden md:block">Size</div>
              <div className="w-24 hidden lg:block">Status</div>
              <div className="w-20"></div>
            </div>

            {/* Loading State */}
            {isLoading && (
              <div className="divide-y divide-gray-100">
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="flex items-center px-4 py-3 animate-pulse">
                    <div className="flex items-center flex-1">
                      <div className="w-5 h-5 bg-gray-200 rounded mr-3" />
                      <div className="h-4 bg-gray-200 rounded w-48" />
                    </div>
                    <div className="w-32 hidden sm:block">
                      <div className="h-4 bg-gray-200 rounded w-24" />
                    </div>
                    <div className="w-20 hidden md:block">
                      <div className="h-4 bg-gray-200 rounded w-16 ml-auto" />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="p-6">
                <div className="bg-red-50 text-red-700 p-4 rounded-lg">
                  Failed to load folder: {(error as Error).message}
                  <button onClick={() => refetch()} className="ml-4 underline">
                    Retry
                  </button>
                </div>
              </div>
            )}

            {/* Content */}
            {folderContents && (
              <>
                {folderContents.items.length === 0 ? (
                  <div className="text-center py-16">
                    <svg className="mx-auto h-16 w-16 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                    </svg>
                    <h3 className="mt-4 text-lg font-medium text-gray-900">This folder is empty</h3>
                    <p className="mt-2 text-gray-500">
                      Upload files or create a new folder to get started.
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {folderContents.items.map((item) => (
                      <FileTableRow
                        key={item.path}
                        item={item}
                        onClick={() => handleItemClick(item)}
                        onDelete={() => handleDelete(item)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}

      {/* Create Folder Modal */}
      {showCreateFolder && (
        <CreateFolderModal
          onClose={() => setShowCreateFolder(false)}
          onCreate={(name) => createFolderMutation.mutate(name)}
          isLoading={createFolderMutation.isPending}
          error={createFolderMutation.error?.message}
        />
      )}
    </div>
  )
}
