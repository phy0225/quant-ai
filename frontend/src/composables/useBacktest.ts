import { computed, type Ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { backtestApi } from '@/api/backtest'
import type { BacktestRunRequest } from '@/types/backtest'

export function useBacktestList(params?: { limit?: number }) {
  return useQuery({
    queryKey: ['backtests', params],
    queryFn: () => backtestApi.list(params),
  })
}

export function useBacktestDetail(id: Ref<string>) {
  const query = useQuery({
    queryKey: computed(() => ['backtest', id.value]),
    queryFn: () => backtestApi.get(id.value),
    enabled: computed(() => !!id.value),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && status !== 'completed' && status !== 'failed') {
        return 3000
      }
      return false
    },
  })

  return query
}

export function useRunBacktest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: BacktestRunRequest) => backtestApi.run(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtests'] })
    },
  })
}
