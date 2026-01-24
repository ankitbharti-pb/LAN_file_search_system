import { SearchResult } from '../api/client'
import DocumentCard from './DocumentCard'

interface SearchResultsProps {
  results: SearchResult[]
}

export default function SearchResults({ results }: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="mt-4 text-lg font-medium text-gray-900">No results found</h3>
        <p className="mt-2 text-gray-500">Try adjusting your search terms</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {results.map((result) => (
        <DocumentCard key={result.chunk_id} result={result} />
      ))}
    </div>
  )
}
