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
  mode?: 'targeted' | 'rebalance' | null
  factor_snapshot?: Record<string, unknown> | null
  market_regime?: string | null
  node_type?: 'experience' | 'symbol' | 'market_regime' | 'factor' | string | null
  display_label?: string | null
  entity_key?: string | null
}

export interface GraphNodesResponse {
  nodes: GraphNode[]
  items?: GraphNode[]
  total: number
}

export interface GraphEdge {
  edge_id: string
  source: string
  target: string
  relation_type: string
  strength: number
  shared_symbols: string[]
  shared_market_regime?: string | null
}

export interface GraphNetworkResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

export interface GraphSearchRequest {
  symbols?: string[]
  query_vector?: number[]
  top_k: number
  approved_only?: boolean
  min_similarity?: number
}

export interface GraphSearchResultItem {
  node_id: string
  similarity_score: number
  node?: GraphNode
  outcome_return?: number
  approved?: boolean
  timestamp?: string
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
