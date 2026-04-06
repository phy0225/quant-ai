export interface FactorSnapshotFactor {
  factor_key: string
  ic: number
  ic_ir: number
  direction: number
  weight: number
}

export interface FactorSnapshotResponse {
  id: string
  trade_date: string
  market_regime: string
  effective_factors: FactorSnapshotFactor[]
  stock_scores: Record<string, { composite_score: number; price?: number; change_pct?: number }>
  industry_scores: Record<string, number>
  concept_scores: Record<string, number>
  market_factors: Record<string, number>
  created_at: string
}

export interface FactorDiscoveryTask {
  task_id: string
  research_direction: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  started_at: string | null
  completed_at: string | null
  recommended_factors: Array<{
    factor_key: string
    score: number
    reason: string
  }>
}

export interface FactorDiscoveryCreateRequest {
  research_direction: string
}

export interface FactorDiscoveryListResponse {
  items: FactorDiscoveryTask[]
  total: number
}
