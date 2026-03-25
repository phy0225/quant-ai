import { computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { decisionsApi } from '@/api/decisions'
import { graphApi } from '@/api/graph'
import { riskApi } from '@/api/risk'
import type { DecisionTriggerRequest } from '@/types/decision'
import { useEmergencyStore } from '@/store/emergency'

/**
 * Dashboard 汇总数据 composable
 */
export function usePortfolioOverview() {
  const emergencyStore = useEmergencyStore()

  const { data: riskStatus, isLoading: isLoadingRisk } = useQuery({
    queryKey: ['risk-status'],
    queryFn: () => riskApi.getStatus(),
    refetchInterval: 10_000,
    select: (data) => {
      // 同步到 emergency store
      emergencyStore.setCircuitBreakerLevel(data.circuit_breaker.level)
      if (data.emergency_stop_active) {
        emergencyStore.activateEmergencyStop()
      }
      return data
    },
  })

  const { data: graphStats, isLoading: isLoadingGraph } = useQuery({
    queryKey: ['graph-stats'],
    queryFn: () => graphApi.getStats(),
    staleTime: 60_000,
  })

  return {
    riskStatus,
    graphStats,
    isLoading: computed(() => isLoadingRisk.value || isLoadingGraph.value),
  }
}

/**
 * 决策触发 composable
 */
export function useDecisionTrigger() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: DecisionTriggerRequest) => decisionsApi.trigger(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
    },
  })
}
