import apiClient from './client'

export interface AgentWeightDetail {
  agent_type: string
  weight: number
  weight_source: string
  locked: boolean
  rl_model_version: string | null
  last_updated_at: string | null
}

export interface RlStatus {
  settled_count: number
  min_settled_for_rl: number
  progress_pct: number
  last_trained_at: string | null
  model_version: string | null
  rl_ready: boolean
  weights: AgentWeightDetail[]
}

export interface WeightsResponse {
  weights: AgentWeightDetail[]
  current_weights: Record<string, number>
  rl_status: RlStatus
  generated_at: string
}

export const weightsApi = {
  getWeights: (): Promise<WeightsResponse> =>
    apiClient.get('/api/v1/weights/'),

  lockAgent: (agentType: string, locked: boolean): Promise<AgentWeightDetail> =>
    apiClient.put(`/api/v1/weights/${agentType}/lock`, { locked }),

  setAgentWeight: (agentType: string, weight: number): Promise<AgentWeightDetail> =>
    apiClient.put(`/api/v1/weights/${agentType}`, { weight }),

  triggerSettlement: (): Promise<{ settled_count: number; triggered_at: string }> =>
    apiClient.post('/api/v1/weights/settle'),
}
