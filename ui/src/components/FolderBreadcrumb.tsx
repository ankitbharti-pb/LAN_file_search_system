interface FolderBreadcrumbProps {
  currentPath: string
  fileName?: string
  onNavigate: (path: string) => void
}

export default function FolderBreadcrumb({ currentPath, fileName, onNavigate }: FolderBreadcrumbProps) {
  // Split path into segments
  const segments = currentPath ? currentPath.split(/[/\\]/).filter(Boolean) : []

  // Build path for each segment
  const buildPath = (index: number) => {
    return segments.slice(0, index + 1).join('/')
  }

  return (
    <nav className="flex items-center space-x-2 text-sm mb-4 bg-gray-50 rounded-lg px-4 py-3">
      {/* Home/Root */}
      <button
        onClick={() => onNavigate('')}
        className="flex items-center text-gray-600 hover:text-blue-600 transition-colors"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
        <span className="ml-1 font-medium">Documents</span>
      </button>

      {/* Path segments - all clickable when viewing a file */}
      {segments.map((segment, index) => (
        <div key={index} className="flex items-center">
          <svg className="w-4 h-4 text-gray-400 mx-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {index === segments.length - 1 && !fileName ? (
            <span className="font-medium text-gray-900">{segment}</span>
          ) : (
            <button
              onClick={() => onNavigate(buildPath(index))}
              className="text-gray-600 hover:text-blue-600 transition-colors"
            >
              {segment}
            </button>
          )}
        </div>
      ))}

      {/* File name (when viewing a file) */}
      {fileName && (
        <div className="flex items-center">
          <svg className="w-4 h-4 text-gray-400 mx-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="font-medium text-gray-900 flex items-center gap-2">
            <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
            </svg>
            {fileName}
          </span>
        </div>
      )}
    </nav>
  )
}
