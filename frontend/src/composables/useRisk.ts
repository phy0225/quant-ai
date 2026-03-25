import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { riskApi } from '@/api/risk'

export function useRiskStatus() {
  return useQuery({
    queryKey: ['risk-status'],
    queryFn: () => riskApi.getStatus(),
    refetchInterval: 5000,
  })
}

export function useRiskEvents(params?: { limit?: number; event_type?: string }) {
  return useQuery({
    queryKey: ['risk-events', params],
    queryFn: () => riskApi.listEvents(params),
  })
}

export function useEmergencyStop() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { reason: string; activated_by: string }) =>
      riskApi.activateEmergencyStop(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk-status'] })
    },
  })
}

export function useDeactivateEmergency() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { password: string; deactivated_by: string }) =>
      riskApi.deactivateEmergencyStop(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk-status'] })
    },
  })
}

export function useResetCircuitBreaker() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ target_level, authorized_by }: { target_level: number; authorized_by: string }) =>
      riskApi.resetCircuitBreaker(target_level, authorized_by),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['risk-status'] })
    },
  })
}
