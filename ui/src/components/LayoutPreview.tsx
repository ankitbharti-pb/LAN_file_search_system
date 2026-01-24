import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, PageInfo, Detection } from '../api/client'

interface LayoutPreviewProps {
  docId: string
  onClose?: () => void
}

export default function LayoutPreview({ docId, onClose }: LayoutPreviewProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [showAnnotated, setShowAnnotated] = useState(true)
  const [showFiltered, setShowFiltered] = useState(true) // true = filtered, false = unfiltered (original)

  // Fetch pages list
  const { data: pagesData, isLoading: loadingPages } = useQuery({
    queryKey: ['pages', docId],
    queryFn: () => api.getPages(docId),
  })

  // Fetch layout for current page
  const { data: layoutData } = useQuery({
    queryKey: ['pageLayout', docId, currentPage],
    queryFn: () => api.getPageLayout(docId, currentPage),
    enabled: !!pagesData && pagesData.total_pages > 0,
  })

  const totalPages = pagesData?.total_pages || 0
  const currentPageInfo = pagesData?.pages.find(p => p.page_number === currentPage)

  const goToPage = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page)
    }
  }

  if (loadingPages) {
    return (
      <div className="flex items-center justify-center py-12">
        <svg className="w-8 h-8 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
    )
  }

  if (!pagesData || totalPages === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No pages available. Run layout detection first.
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
        <div className="flex items-center gap-4">
          <h3 className="font-medium text-gray-900">Layout Preview</h3>
          <span className="text-sm text-gray-500">
            Page {currentPage} of {totalPages}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Toggle annotated view */}
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={showAnnotated}
              onChange={e => setShowAnnotated(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Show annotations
          </label>

          {/* Filter toggle - only show if unfiltered image is available */}
          {currentPageInfo?.has_unfiltered_annotated_image && showAnnotated && (
            <div className="flex items-center gap-1 border-l border-gray-200 pl-3 ml-1">
              <span className="text-xs text-gray-500 mr-1">View:</span>
              <button
                onClick={() => setShowFiltered(true)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  showFiltered
                    ? 'bg-blue-100 text-blue-800 font-medium'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Filtered
              </button>
              <button
                onClick={() => setShowFiltered(false)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  !showFiltered
                    ? 'bg-blue-100 text-blue-800 font-medium'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Original
              </button>
            </div>
          )}

          {/* Filter stats badge */}
          {currentPageInfo && currentPageInfo.boxes_removed_by_filter > 0 && (
            <span className="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded">
              {currentPageInfo.boxes_removed_by_filter} boxes filtered
            </span>
          )}

          {onClose && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Page navigation */}
      <div className="flex items-center justify-center gap-2 py-2 border-b bg-gray-50">
        <button
          onClick={() => goToPage(1)}
          disabled={currentPage === 1}
          className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          title="First page"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>

        <button
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Previous page"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <div className="flex items-center gap-1">
          <input
            type="number"
            min={1}
            max={totalPages}
            value={currentPage}
            onChange={e => goToPage(parseInt(e.target.value) || 1)}
            className="w-14 px-2 py-1 text-center border rounded text-sm"
          />
          <span className="text-sm text-gray-500">/ {totalPages}</span>
        </div>

        <button
          onClick={() => goToPage(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Next page"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>

        <button
          onClick={() => goToPage(totalPages)}
          disabled={currentPage === totalPages}
          className="p-1 rounded hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
          title="Last page"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Side-by-side view */}
      <div className="grid grid-cols-2 gap-4 p-4">
        {/* Original page */}
        <div className="flex flex-col">
          <div className="text-sm font-medium text-gray-600 mb-2">Original</div>
          <div className="border rounded-lg overflow-hidden bg-gray-100 flex items-center justify-center min-h-[400px]">
            <img
              src={api.getPageImageUrl(docId, currentPage)}
              alt={`Page ${currentPage}`}
              className="max-w-full max-h-[600px] object-contain"
            />
          </div>
        </div>

        {/* Annotated page */}
        <div className="flex flex-col">
          <div className="text-sm font-medium text-gray-600 mb-2">
            Detected Layout
            {currentPageInfo && (
              <span className="ml-2 text-gray-400 font-normal">
                ({showFiltered ? currentPageInfo.detection_count : currentPageInfo.unfiltered_detection_count} elements
                {!showFiltered && currentPageInfo.boxes_removed_by_filter > 0 && (
                  <span className="text-amber-600 ml-1">before filtering</span>
                )})
              </span>
            )}
          </div>
          <div className="border rounded-lg overflow-hidden bg-gray-100 flex items-center justify-center min-h-[400px]">
            {showAnnotated && currentPageInfo?.has_annotated_image ? (
              <img
                src={
                  showFiltered
                    ? api.getAnnotatedImageUrl(docId, currentPage)
                    : currentPageInfo.has_unfiltered_annotated_image
                      ? api.getUnfilteredAnnotatedImageUrl(docId, currentPage)
                      : api.getAnnotatedImageUrl(docId, currentPage)
                }
                alt={`Page ${currentPage} ${showFiltered ? 'filtered' : 'unfiltered'}`}
                className="max-w-full max-h-[600px] object-contain"
              />
            ) : (
              <img
                src={api.getPageImageUrl(docId, currentPage)}
                alt={`Page ${currentPage}`}
                className="max-w-full max-h-[600px] object-contain"
              />
            )}
          </div>
        </div>
      </div>

      {/* Detection details */}
      {layoutData && layoutData.detections.length > 0 && (
        <div className="px-4 pb-4">
          <div className="text-sm font-medium text-gray-600 mb-2">
            Detected Elements ({layoutData.detections.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {layoutData.detections.map((det, i) => (
              <DetectionBadge key={i} detection={det} />
            ))}
          </div>
        </div>
      )}

      {/* Page thumbnails */}
      {totalPages > 1 && (
        <div className="px-4 pb-4">
          <div className="text-sm font-medium text-gray-600 mb-2">All Pages</div>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {pagesData.pages.map(page => (
              <button
                key={page.page_number}
                onClick={() => setCurrentPage(page.page_number)}
                className={`flex-shrink-0 w-16 h-20 border-2 rounded overflow-hidden ${
                  page.page_number === currentPage
                    ? 'border-blue-500'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <img
                  src={api.getPageImageUrl(docId, page.page_number)}
                  alt={`Page ${page.page_number}`}
                  className="w-full h-full object-cover"
                />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Detection badge component
function DetectionBadge({ detection }: { detection: Detection }) {
  const labelColors: Record<string, string> = {
    'Title': 'bg-blue-100 text-blue-800',
    'Section-header': 'bg-indigo-100 text-indigo-800',
    'Text': 'bg-green-100 text-green-800',
    'Table': 'bg-red-100 text-red-800',
    'Picture': 'bg-pink-100 text-pink-800',
    'Formula': 'bg-orange-100 text-orange-800',
    'List-item': 'bg-teal-100 text-teal-800',
    'Caption': 'bg-gray-100 text-gray-800',
    'Footnote': 'bg-gray-100 text-gray-600',
    'Page-header': 'bg-gray-100 text-gray-500',
    'Page-footer': 'bg-gray-100 text-gray-500',
  }

  const colorClass = labelColors[detection.label] || 'bg-gray-100 text-gray-800'

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}>
      {detection.label}
      <span className="ml-1 opacity-60">
        {Math.round(detection.confidence * 100)}%
      </span>
    </span>
  )
}
