import apiClient from './client'
import type { RiskStatus, RiskEvent, CircuitBreakerStatus, RiskParams } from '@/types/risk'

export const riskApi = {
  getStatus(): Promise<RiskStatus> {
    return apiClient.get('/api/v1/risk/status')
  },

  listEvents(params?: { limit?: number; event_type?: string }): Promise<RiskEvent[]> {
    return apiClient.get('/api/v1/risk/events', { params })
  },

  resetCircuitBreaker(target_level: number, authorized_by: string): Promise<CircuitBreakerStatus> {
    return apiClient.post('/api/v1/risk/circuit-breaker/reset', { target_level, authorized_by })
  },

  activateEmergencyStop(payload: { reason: string; activated_by: string }): Promise<void> {
    return apiClient.post('/api/v1/risk/emergency-stop/activate', payload)
  },

  deactivateEmergencyStop(payload: { password: string; deactivated_by: string }): Promise<{ success: boolean }> {
    return apiClient.post('/api/v1/risk/emergency-stop/deactivate', payload)
  },

  getRiskParams(): Promise<RiskParams> {
    return apiClient.get('/api/v1/risk/params')
  },

  updateRiskParams(payload: Partial<RiskParams>): Promise<RiskParams> {
    return apiClient.put('/api/v1/risk/params', payload)
  },
}
