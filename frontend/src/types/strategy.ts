export interface StrategyVersion {
  version_id: string
  parent_version_id: string | null
  name: string
  description: string
  created_at: string
}

export interface StrategyExperiment {
  experiment_id: string
  base_version_id: string
  hypothesis: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  new_version_id: string | null
  expected_improvement: {
    annualized_return_lift: number
    drawdown_reduction: number
    sharpe_lift: number
  } | null
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface StrategyExperimentCreateRequest {
  base_version_id: string
  hypothesis: string
}

export interface StrategyVersionListResponse {
  items: StrategyVersion[]
  total: number
}

export interface StrategyExperimentListResponse {
  items: StrategyExperiment[]
  total: number
}
