export type BacktestMode = 'signal_based' | 'factor_based'

export interface BacktestRunRequest {
  symbols: string[]
  start_date: string
  end_date: string
  initial_capital: number
  benchmark: 'buy_and_hold' | 'equal_weight' | 'market_cap_weight'
  rebalance_frequency: 'daily' | 'weekly' | 'monthly'
  commission_rate: number
  slippage: number
  backtest_mode: BacktestMode
}

export interface NavPoint {
  date: string
  nav: number
  benchmark_nav: number
}

export interface MonthlyReturnPoint {
  year: number
  month: number
  return: number
}

export interface BacktestReport {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  symbols: string[]
  start_date: string
  end_date: string
  initial_capital: number
  benchmark: string
  backtest_mode: BacktestMode
  commission_rate: number | null
  slippage: number | null
  nav_curve: NavPoint[] | null
  monthly_returns: MonthlyReturnPoint[] | null
  created_at: string
  completed_at: string | null
  total_return: number | null
  annualized_return: number | null
  sharpe_ratio: number | null
  max_drawdown: number | null
  win_rate: number | null
  avg_holding_days: number | null
  total_commission: number | null
  total_slippage_cost: number | null
  error_message?: string | null
}

export interface BacktestListResponse {
  total: number
  items: BacktestReport[]
}
