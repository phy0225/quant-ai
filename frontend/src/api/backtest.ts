import apiClient from './client'
import type { BacktestRunRequest, BacktestReport, BacktestListResponse } from '@/types/backtest'

export const backtestApi = {
  run(payload: BacktestRunRequest): Promise<BacktestReport> {
    return apiClient.post('/api/v1/backtest/', payload)
  },

  get(id: string): Promise<BacktestReport> {
    return apiClient.get(`/api/v1/backtest/${id}`)
  },

  list(params?: { limit?: number }): Promise<BacktestListResponse> {
    return apiClient.get('/api/v1/backtest/', { params })
  },
}
