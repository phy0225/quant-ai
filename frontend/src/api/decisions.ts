import apiClient from './client'
import type { DecisionRun, DecisionTriggerRequest, RebalanceOrder } from '@/types/decision'

export interface SymbolStat {
  symbol: string
  decision_count: number
  direction_dist: Record<string, number>
  avg_confidence: number | null
  last_direction: string | null
  last_analyzed_at: string | null
}

export interface DecisionStatsResponse {
  total_decisions: number
  symbol_stats: SymbolStat[]
  generated_at: string
}

export interface DecisionListResponse {
  items: DecisionRun[]
  total: number
  page: number
  page_size: number
}

export const decisionsApi = {
  trigger(payload: DecisionTriggerRequest): Promise<DecisionRun> {
    return apiClient.post('/api/v1/decisions/trigger', payload)
  },

  get(id: string): Promise<DecisionRun> {
    return apiClient.get(`/api/v1/decisions/${id}`)
  },

  getOrders(id: string): Promise<RebalanceOrder[]> {
    return apiClient.get(`/api/v1/decisions/${id}/orders`)
  },

  list(params?: { page?: number; page_size?: number }): Promise<DecisionListResponse> {
    return apiClient.get('/api/v1/decisions/', { params })
  },

  stats(params?: { symbol?: string; days?: number }): Promise<DecisionStatsResponse> {
    return apiClient.get('/api/v1/decisions/stats', { params })
  },
}

