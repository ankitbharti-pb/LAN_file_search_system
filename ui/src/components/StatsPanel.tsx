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
        <StatCard label="Main Vectors" value={stats.main_vectors} />
        <StatCard label="Cache Entries" value={stats.cache_entries} />
      </div>

      {/* Multi-Vector Index Stats */}
      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Multi-Vector Index</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded-lg p-3 text-center">
            <p className="text-xs text-blue-600">Main</p>
            <p className="text-lg font-bold text-blue-900">{stats.main_vectors.toLocaleString()}</p>
          </div>
          <div className="bg-green-50 rounded-lg p-3 text-center">
            <p className="text-xs text-green-600">Summary</p>
            <p className="text-lg font-bold text-green-900">{stats.summary_vectors.toLocaleString()}</p>
          </div>
          <div className="bg-purple-50 rounded-lg p-3 text-center">
            <p className="text-xs text-purple-600">Question</p>
            <p className="text-lg font-bold text-purple-900">{stats.question_vectors.toLocaleString()}</p>
          </div>
        </div>
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
