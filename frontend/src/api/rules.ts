import apiClient from './client'
import type { AutoApprovalRule } from '@/types/risk'

export const rulesApi = {
  list(params?: { active_only?: boolean }): Promise<AutoApprovalRule[]> {
    return apiClient.get('/api/v1/rules/', { params })
  },

  create(payload: Omit<AutoApprovalRule, 'id' | 'trigger_count' | 'last_triggered_at' | 'created_at' | 'updated_at' | 'action'>): Promise<AutoApprovalRule> {
    return apiClient.post('/api/v1/rules/', payload)
  },

  update(id: string, payload: Partial<AutoApprovalRule>): Promise<AutoApprovalRule> {
    return apiClient.put(`/api/v1/rules/${id}`, payload)
  },

  delete(id: string): Promise<void> {
    return apiClient.delete(`/api/v1/rules/${id}`)
  },

  toggle(id: string): Promise<AutoApprovalRule> {
    return apiClient.post(`/api/v1/rules/${id}/toggle`)
  },
}
