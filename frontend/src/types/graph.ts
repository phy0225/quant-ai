export interface SimilarityTrendPoint {
  month: string
  avg_similarity: number
}

export interface OutcomeDistribution {
  positive: number
  negative: number
}

export interface TopSymbolItem {
  symbol: string
  count: number
}

export interface GraphStats {
  node_count: number
  edge_count: number
  avg_accuracy: number
  approval_rate: number
  similarity_trend: SimilarityTrendPoint[]
  outcome_distribution: OutcomeDistribution
  top_symbols: TopSymbolItem[]
  generated_at: string
}

export interface GraphNode {
  node_id: string
  timestamp: string
  approved: boolean
  outcome_return: number
  outcome_sharpe: number
  symbols: string[]
}

export interface GraphNodesResponse {
  nodes: GraphNode[]
  total: number
}

export interface GraphSearchRequest {
  query_vector: number[]
  top_k: number
  approved_only: boolean
  min_similarity: number
}

export interface GraphSearchResultItem {
  node_id: string
  similarity_score: number
  node: GraphNode
}

export interface CytoscapeNodeData {
  id: string
  label: string
  approved: boolean
  outcomeReturn: number
  timestamp: string
  symbols: string[]
  nodeType: 'approved' | 'rejected' | 'positive' | 'negative'
}

export interface CytoscapeEdgeData {
  id: string
  source: string
  target: string
}
