import apiClient from './client'
import type {
  StrategyExperiment,
  StrategyExperimentCreateRequest,
  StrategyExperimentListResponse,
  StrategyVersionListResponse,
} from '@/types/strategy'

export const strategyApi = {
  listVersions(): Promise<StrategyVersionListResponse> {
    return apiClient.get('/api/v1/strategy/versions')
  },

  listExperiments(limit = 20): Promise<StrategyExperimentListResponse> {
    return apiClient.get('/api/v1/strategy/experiments', { params: { limit } })
  },

  createExperiment(payload: StrategyExperimentCreateRequest): Promise<StrategyExperiment> {
    return apiClient.post('/api/v1/strategy/experiment', payload)
  },

  getExperiment(experimentId: string): Promise<StrategyExperiment> {
    return apiClient.get(`/api/v1/strategy/experiment/${experimentId}`)
  },
}
