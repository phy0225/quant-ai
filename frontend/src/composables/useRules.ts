import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { rulesApi } from '@/api/rules'
import type { AutoApprovalRule } from '@/types/risk'

export function useRules(params?: { active_only?: boolean }) {
  return useQuery({
    queryKey: ['rules', params],
    queryFn: () => rulesApi.list(params),
  })
}

export function useCreateRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: Parameters<typeof rulesApi.create>[0]) => rulesApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useUpdateRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<AutoApprovalRule> }) =>
      rulesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useDeleteRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => rulesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useToggleRule() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => rulesApi.toggle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}
