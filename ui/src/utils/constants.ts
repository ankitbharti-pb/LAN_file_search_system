/**
 * Shared constants and utilities for the LAN File Search System UI.
 */

/**
 * File type icon and color mappings.
 */
export const FILE_TYPE_ICONS: Record<string, { icon: string; color: string }> = {
  pdf: { icon: '📄', color: 'bg-red-100 text-red-700' },
  docx: { icon: '📝', color: 'bg-blue-100 text-blue-700' },
  xlsx: { icon: '📊', color: 'bg-green-100 text-green-700' },
  xls: { icon: '📊', color: 'bg-green-100 text-green-700' },
  csv: { icon: '📋', color: 'bg-yellow-100 text-yellow-700' },
  pptx: { icon: '📽️', color: 'bg-orange-100 text-orange-700' },
}

/**
 * Get just the icon for a file type.
 */
export function getFileTypeIcon(fileType: string): string {
  return FILE_TYPE_ICONS[fileType]?.icon || '📄'
}

/**
 * Format file size in human-readable format.
 */
export function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/**
 * Category color mappings for chunk visualization.
 */
export const categoryColors: Record<string, string> = {
  definition: 'bg-blue-100 text-blue-700 border-blue-200',
  procedure: 'bg-green-100 text-green-700 border-green-200',
  data: 'bg-purple-100 text-purple-700 border-purple-200',
  narrative: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  example: 'bg-orange-100 text-orange-700 border-orange-200',
  reference: 'bg-gray-100 text-gray-700 border-gray-200',
}
