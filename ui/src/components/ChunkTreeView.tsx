import { useState, useEffect, useRef } from 'react'
import { ChevronRight, ChevronDown, FileText, Table, List, Image, Hash, Type } from 'lucide-react'
import { api, ChunkTreeNode, ChunkTreeResponse } from '../api/client'
import { categoryColors } from '../utils/constants'

interface ChunkTreeViewProps {
  documentId: string
  selectedChunkId?: string
  highlightedChunkIds?: string[]  // Chunks to highlight (e.g., matched search results)
  initialChunkId?: string         // Auto-select and scroll to this chunk on mount
  onSelectChunk: (chunkId: string) => void
}

const contentTypeIcons: Record<string, React.ReactNode> = {
  title: <Type className="w-4 h-4 text-purple-500" />,
  section_header: <Hash className="w-4 h-4 text-blue-500" />,
  heading: <Hash className="w-4 h-4 text-blue-400" />,
  paragraph: <FileText className="w-4 h-4 text-gray-500" />,
  table: <Table className="w-4 h-4 text-green-500" />,
  list: <List className="w-4 h-4 text-orange-500" />,
  figure: <Image className="w-4 h-4 text-pink-500" />,
  summary: <FileText className="w-4 h-4 text-yellow-500" />,
  schema: <Table className="w-4 h-4 text-cyan-500" />,
}

interface TreeNodeProps {
  node: ChunkTreeNode
  level: number
  selectedChunkId?: string
  highlightedChunkIds?: string[]
  onSelectChunk: (chunkId: string) => void
  expandedNodes: Set<string>
  toggleExpand: (nodeId: string) => void
}

function TreeNode({
  node,
  level,
  selectedChunkId,
  highlightedChunkIds,
  onSelectChunk,
  expandedNodes,
  toggleExpand,
}: TreeNodeProps) {
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expandedNodes.has(node.id)
  const isSelected = selectedChunkId === node.id
  const isHighlighted = highlightedChunkIds?.includes(node.id)

  return (
    <div>
      <div
        id={`chunk-${node.id}`}
        className={`flex items-center gap-1 py-1.5 px-2 cursor-pointer hover:bg-gray-100 rounded transition-all ${
          isSelected ? 'bg-blue-50 border-l-2 border-blue-500' : ''
        } ${isHighlighted && !isSelected ? 'ring-2 ring-yellow-400 bg-yellow-50' : ''}`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => onSelectChunk(node.id)}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              toggleExpand(node.id)
            }}
            className="p-0.5 hover:bg-gray-200 rounded"
          >
            {isExpanded ? (
              <ChevronDown className="w-4 h-4 text-gray-500" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-500" />
            )}
          </button>
        ) : (
          <span className="w-5" />
        )}

        {contentTypeIcons[node.content_type] || <FileText className="w-4 h-4 text-gray-400" />}

        <span className="flex-1 truncate text-sm">
          {node.title || node.text}
        </span>

        {/* Matched badge for highlighted chunks */}
        {isHighlighted && (
          <span className="px-1.5 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded-full mr-1">
            matched
          </span>
        )}

        {node.category && (
          <span
            className={`text-xs px-1.5 py-0.5 rounded ${
              categoryColors[node.category] || 'bg-gray-100 text-gray-600'
            }`}
          >
            {node.category}
          </span>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              selectedChunkId={selectedChunkId}
              highlightedChunkIds={highlightedChunkIds}
              onSelectChunk={onSelectChunk}
              expandedNodes={expandedNodes}
              toggleExpand={toggleExpand}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// Helper to find ancestors of a chunk in the tree
function findAncestors(nodes: ChunkTreeNode[], targetId: string, path: string[] = []): string[] | null {
  for (const node of nodes) {
    if (node.id === targetId) {
      return path
    }
    if (node.children && node.children.length > 0) {
      const result = findAncestors(node.children, targetId, [...path, node.id])
      if (result) return result
    }
  }
  return null
}

export function ChunkTreeView({
  documentId,
  selectedChunkId,
  highlightedChunkIds,
  initialChunkId,
  onSelectChunk,
}: ChunkTreeViewProps) {
  const [treeData, setTreeData] = useState<ChunkTreeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const hasAutoSelectedRef = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadTree()
    hasAutoSelectedRef.current = false
  }, [documentId])

  // Auto-expand and select initial chunk when tree loads
  useEffect(() => {
    if (treeData && initialChunkId && !hasAutoSelectedRef.current) {
      hasAutoSelectedRef.current = true

      // Find ancestors and expand them
      const ancestors = findAncestors(treeData.tree, initialChunkId)
      if (ancestors) {
        setExpandedNodes((prev) => {
          const next = new Set(prev)
          ancestors.forEach((id) => next.add(id))
          return next
        })
      }

      // Select the chunk
      onSelectChunk(initialChunkId)

      // Scroll into view after a short delay to allow render
      setTimeout(() => {
        const element = document.getElementById(`chunk-${initialChunkId}`)
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 100)
    }
  }, [treeData, initialChunkId, onSelectChunk])

  const loadTree = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.getChunkTree(documentId)
      setTreeData(data)

      // Auto-expand first level
      const firstLevel = new Set<string>()
      data.tree.forEach((node) => firstLevel.add(node.id))
      setExpandedNodes(firstLevel)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chunk tree')
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev)
      if (next.has(nodeId)) {
        next.delete(nodeId)
      } else {
        next.add(nodeId)
      }
      return next
    })
  }

  const expandAll = () => {
    const allIds = new Set<string>()
    const collectIds = (nodes: ChunkTreeNode[]) => {
      nodes.forEach((node) => {
        allIds.add(node.id)
        if (node.children) collectIds(node.children)
      })
    }
    if (treeData) collectIds(treeData.tree)
    setExpandedNodes(allIds)
  }

  const collapseAll = () => {
    setExpandedNodes(new Set())
  }

  // Filter nodes based on search
  const filterNodes = (nodes: ChunkTreeNode[], query: string): ChunkTreeNode[] => {
    if (!query) return nodes

    const lowerQuery = query.toLowerCase()
    return nodes
      .map((node) => {
        const matchesSearch =
          (node.title?.toLowerCase().includes(lowerQuery) ||
            node.text.toLowerCase().includes(lowerQuery) ||
            node.summary?.toLowerCase().includes(lowerQuery))

        const filteredChildren = node.children ? filterNodes(node.children, query) : []

        if (matchesSearch || filteredChildren.length > 0) {
          return { ...node, children: filteredChildren }
        }
        return null
      })
      .filter((node): node is ChunkTreeNode => node !== null)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-red-600 bg-red-50 rounded">
        <p className="font-medium">Error loading chunk tree</p>
        <p className="text-sm">{error}</p>
        <button
          onClick={loadTree}
          className="mt-2 text-sm text-blue-600 hover:underline"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!treeData || treeData.tree.length === 0) {
    return (
      <div className="p-4 text-gray-500 text-center">
        <p>No chunks found</p>
        <p className="text-sm mt-1">Run chunking first to generate chunks</p>
      </div>
    )
  }

  const filteredTree = filterNodes(treeData.tree, searchQuery)
  const highlightedCount = highlightedChunkIds?.length || 0

  return (
    <div className="flex flex-col h-full">
      <div className="p-2 border-b bg-gray-50">
        <input
          type="text"
          placeholder="Search chunks..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-1.5 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        <div className="flex gap-2 mt-2 text-xs">
          <span className="text-gray-500">{treeData.total_chunks} chunks</span>
          {highlightedCount > 0 && (
            <span className="text-yellow-600">
              {highlightedCount} matched
            </span>
          )}
          <button onClick={expandAll} className="text-blue-600 hover:underline">
            Expand all
          </button>
          <button onClick={collapseAll} className="text-blue-600 hover:underline">
            Collapse all
          </button>
        </div>
      </div>

      <div ref={containerRef} className="flex-1 overflow-auto p-2">
        {filteredTree.length === 0 ? (
          <p className="text-gray-500 text-sm text-center py-4">
            No matching chunks found
          </p>
        ) : (
          filteredTree.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              level={0}
              selectedChunkId={selectedChunkId}
              highlightedChunkIds={highlightedChunkIds}
              onSelectChunk={onSelectChunk}
              expandedNodes={expandedNodes}
              toggleExpand={toggleExpand}
            />
          ))
        )}
      </div>
    </div>
  )
}
