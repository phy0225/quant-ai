import apiClient from './client'
import type { PortfolioHolding, PortfolioListResponse, PortfolioSnapshot, PortfolioSummary } from '@/types/portfolio'

export const portfolioApi = {
  list(): Promise<PortfolioListResponse> {
    return apiClient.get('/api/v1/portfolio/')
  },

  summary(): Promise<PortfolioSummary> {
    return apiClient.get('/api/v1/portfolio/summary')
  },

  snapshots(limit = 20): Promise<{ snapshots: PortfolioSnapshot[] }> {
    return apiClient.get('/api/v1/portfolio/snapshots', { params: { limit } })
  },

  create(payload: Partial<PortfolioHolding> & { symbol: string; weight: number }): Promise<PortfolioHolding> {
    return apiClient.post('/api/v1/portfolio/', payload)
  },

  update(id: string, payload: Partial<PortfolioHolding>): Promise<PortfolioHolding> {
    return apiClient.put(`/api/v1/portfolio/${id}`, payload)
  },

  remove(id: string): Promise<{ ok: boolean }> {
    return apiClient.delete(`/api/v1/portfolio/${id}`)
  },

  refreshPrices(): Promise<{ refreshed: number; updated_at?: string }> {
    return apiClient.post('/api/v1/portfolio/refresh-prices')
  },
}

