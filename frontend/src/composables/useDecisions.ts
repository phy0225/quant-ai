import { computed, type Ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { decisionsApi } from '@/api/decisions'
import type { DecisionTriggerRequest } from '@/types/decision'

export function useDecisions(params?: Ref<{ page?: number; page_size?: number }>) {
  return useQuery({
    queryKey: computed(() => ['decisions', params?.value]),
    queryFn: () => decisionsApi.list(params?.value),
    refetchInterval: 30_000,
  })
}

export function useDecisionDetail(id: Ref<string>) {
  return useQuery({
    queryKey: computed(() => ['decision', id.value]),
    queryFn: () => decisionsApi.get(id.value),
    enabled: computed(() => !!id.value),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' ? 2000 : false
    },
  })
}

export function useTriggerDecision() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: DecisionTriggerRequest) => decisionsApi.trigger(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })
}
