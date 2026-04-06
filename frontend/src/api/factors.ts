import apiClient from './client'
import type {
  FactorDiscoveryCreateRequest,
  FactorDiscoveryListResponse,
  FactorDiscoveryTask,
  FactorSnapshotResponse,
} from '@/types/factor'

export const factorsApi = {
  daily(date: string): Promise<FactorSnapshotResponse> {
    return apiClient.get('/api/v1/factors/daily', { params: { date } })
  },

  discover(payload: FactorDiscoveryCreateRequest): Promise<FactorDiscoveryTask> {
    return apiClient.post('/api/v1/factors/discover', payload)
  },

  listDiscoveryTasks(limit = 20): Promise<FactorDiscoveryListResponse> {
    return apiClient.get('/api/v1/factors/discover', { params: { limit } })
  },

  getDiscoveryTask(taskId: string): Promise<FactorDiscoveryTask> {
    return apiClient.get(`/api/v1/factors/discover/${taskId}`)
  },
}
