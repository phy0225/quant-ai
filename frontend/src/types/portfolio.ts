export interface PortfolioHolding {
  id: string
  symbol: string
  symbol_name: string | null
  weight: number
  cost_price: number | null
  quantity: number | null
  market_value: number | null
  current_price: number | null
  pnl_pct: number | null
  note: string | null
  updated_at: string | null
  created_at: string | null
}

export interface PortfolioListResponse {
  holdings: PortfolioHolding[]
}

export interface PortfolioSummary {
  total_weight: number
  total_mv: number
  avg_pnl_pct: number
  holding_count: number
  weight_dist: Array<{ symbol: string; symbol_name: string | null; weight: number }>
}

export interface PortfolioSnapshot {
  id: string
  decision_id: string | null
  approval_id: string | null
  holdings: Record<string, number>
  total_mv: number | null
  created_at: string | null
}

export interface RebalanceOrder {
  symbol: string
  target_weight: number
  current_weight: number
  weight_delta: number
  action: 'buy' | 'sell' | 'hold'
}

