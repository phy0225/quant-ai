import apiClient from './client'

export interface SettlementRunRequest {
  settle_date?: string
}

export interface SettlementRunResponse {
  settle_date: string
  settled_count: number
  updated_weights: number
}

export interface SettlementPendingResponse {
  total: number
}

export const settlementApi = {
  run(payload: SettlementRunRequest): Promise<SettlementRunResponse> {
    return apiClient.post('/api/v1/settlement/run', payload)
  },

  pending(settleDate: string): Promise<SettlementPendingResponse> {
    return apiClient.get('/api/v1/settlement/pending', { params: { settle_date: settleDate } })
  },
}
