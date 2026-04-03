export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'auto_approved' | 'modified'

export interface SimilarCase {
  node_id: string
  similarity_score: number
  outcome_return: number
  outcome_sharpe: number
  approved: boolean
  timestamp: string
}

export interface RecommendationItem {
  symbol: string
  current_weight: number
  recommended_weight: number
  weight_delta: number
  confidence_score: number
  similar_cases: SimilarCase[]
}

export interface ApprovalRecord {
  id: string
  decision_run_id: string
  status: ApprovalStatus
  reviewed_by: string | null
  reviewed_at: string | null
  comment: string | null
  auto_rule_id: string | null
  recommendations: RecommendationItem[]
  created_at: string
}

export interface ApprovalListResponse {
  items: ApprovalRecord[]
  total: number
  page: number
  page_size: number
}

export interface ApprovalActionRequest {
  action: 'approved' | 'rejected'
  comment?: string
  reviewed_by: string
}
