import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import StatsPanel from '../components/StatsPanel'

export default function Admin() {
  const queryClient = useQueryClient()

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: () => api.getStats(),
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const { data: reindexStatus } = useQuery({
    queryKey: ['reindex-status'],
    queryFn: () => api.getReindexStatus(),
    refetchInterval: 5000,
  })

  const reindexMutation = useMutation({
    mutationFn: () => api.triggerReindex(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reindex-status'] })
    },
  })

  const clearCacheMutation = useMutation({
    mutationFn: () => api.clearCache(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stats'] })
    },
  })

  const isReindexing = reindexStatus?.status === 'in_progress' || reindexStatus?.status === 'started'

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="text-gray-600 mt-1">Manage indexes and view system statistics</p>
      </div>

      {/* Stats Panel */}
      {statsLoading ? (
        <div className="animate-pulse card mb-8">
          <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="h-20 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      ) : stats ? (
        <StatsPanel stats={stats} />
      ) : null}

      {/* Actions */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Reindex */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Reindex Documents</h2>
          <p className="text-gray-600 text-sm mb-4">
            Scan the watched folder and reindex all documents. This may take several minutes.
          </p>

          {reindexStatus && reindexStatus.status !== 'idle' && (
            <div className={`mb-4 p-3 rounded-lg text-sm ${
              reindexStatus.status === 'completed' ? 'bg-green-50 text-green-700' :
              reindexStatus.status === 'failed' ? 'bg-red-50 text-red-700' :
              'bg-blue-50 text-blue-700'
            }`}>
              <p className="font-medium capitalize">{reindexStatus.status}</p>
              <p>{reindexStatus.message}</p>
              {reindexStatus.status === 'completed' && (
                <p className="mt-1">
                  Processed: {reindexStatus.processed} | Failed: {reindexStatus.failed} | Skipped: {reindexStatus.skipped}
                </p>
              )}
            </div>
          )}

          <button
            onClick={() => reindexMutation.mutate()}
            disabled={isReindexing}
            className="btn-primary w-full disabled:opacity-50"
          >
            {isReindexing ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Reindexing...
              </span>
            ) : (
              'Start Reindex'
            )}
          </button>
        </div>

        {/* Clear Cache */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Clear Cache</h2>
          <p className="text-gray-600 text-sm mb-4">
            Clear all cached search responses. New searches will be computed fresh.
          </p>

          {clearCacheMutation.isSuccess && (
            <div className="mb-4 p-3 rounded-lg bg-green-50 text-green-700 text-sm">
              Cache cleared successfully
            </div>
          )}

          <button
            onClick={() => clearCacheMutation.mutate()}
            disabled={clearCacheMutation.isPending}
            className="btn-secondary w-full"
          >
            {clearCacheMutation.isPending ? 'Clearing...' : 'Clear Cache'}
          </button>
        </div>
      </div>
    </div>
  )
}
