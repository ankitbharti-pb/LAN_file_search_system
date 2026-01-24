import { Stats } from '../api/client'

interface StatsPanelProps {
  stats: Stats
}

export default function StatsPanel({ stats }: StatsPanelProps) {
  return (
    <div className="card mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">System Statistics</h2>

      {/* Main Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard label="Documents" value={stats.total_documents} />
        <StatCard label="Chunks" value={stats.total_chunks} />
        <StatCard label="Vector Index" value={stats.vector_index_size} />
        <StatCard label="Cache Entries" value={stats.cache_entries} />
      </div>

      {/* Breakdown */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* By Document Type */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">By Document Type</h3>
          <div className="space-y-2">
            {Object.entries(stats.documents_by_detected_type).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between">
                <span className="text-sm text-gray-600 capitalize">{type}</span>
                <span className="text-sm font-medium text-gray-900">{count}</span>
              </div>
            ))}
            {Object.keys(stats.documents_by_detected_type).length === 0 && (
              <p className="text-sm text-gray-500">No documents indexed</p>
            )}
          </div>
        </div>

        {/* By File Type */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">By File Format</h3>
          <div className="space-y-2">
            {Object.entries(stats.documents_by_file_type).map(([type, count]) => (
              <div key={type} className="flex items-center justify-between">
                <span className="text-sm text-gray-600 uppercase">{type}</span>
                <span className="text-sm font-medium text-gray-900">{count}</span>
              </div>
            ))}
            {Object.keys(stats.documents_by_file_type).length === 0 && (
              <p className="text-sm text-gray-500">No documents indexed</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value.toLocaleString()}</p>
    </div>
  )
}
