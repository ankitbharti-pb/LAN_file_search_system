import { ProcessingStatus as ProcessingStatusType } from '../api/client'

interface ProcessingStatusProps {
  status: ProcessingStatusType | undefined
  showLabel?: boolean
}

const STATUS_CONFIG: Record<ProcessingStatusType, { label: string; color: string; bgColor: string }> = {
  pending: {
    label: 'Pending',
    color: 'text-gray-700',
    bgColor: 'bg-gray-100',
  },
  layout_detected: {
    label: 'Layout Detected',
    color: 'text-blue-700',
    bgColor: 'bg-blue-100',
  },
  text_extracted: {
    label: 'Text Extracted',
    color: 'text-yellow-700',
    bgColor: 'bg-yellow-100',
  },
  chunked: {
    label: 'Chunked',
    color: 'text-cyan-700',
    bgColor: 'bg-cyan-100',
  },
  enriched: {
    label: 'Enriched',
    color: 'text-violet-700',
    bgColor: 'bg-violet-100',
  },
  reviewed: {
    label: 'Reviewed',
    color: 'text-purple-700',
    bgColor: 'bg-purple-100',
  },
  indexed: {
    label: 'Indexed',
    color: 'text-green-700',
    bgColor: 'bg-green-100',
  },
}

export default function ProcessingStatus({ status, showLabel = true }: ProcessingStatusProps) {
  if (!status) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
        Not registered
      </span>
    )
  }

  const config = STATUS_CONFIG[status]

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bgColor} ${config.color}`}>
      {/* Status dot */}
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
        status === 'indexed' ? 'bg-green-500' :
        status === 'pending' ? 'bg-gray-400' :
        'bg-current'
      }`} />
      {showLabel && config.label}
    </span>
  )
}
