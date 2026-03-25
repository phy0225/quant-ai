import { computed, type Ref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { approvalsApi } from '@/api/approvals'
import type { ApprovalActionRequest } from '@/types/approval'

export function useApprovals(params?: Ref<{ status?: string; page?: number; page_size?: number }>) {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: computed(() => ['approvals', params?.value]),
    queryFn: () => approvalsApi.list(params?.value),
    refetchInterval: 30_000,
  })

  const { mutateAsync: processAction, isPending } = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ApprovalActionRequest }) =>
      approvalsApi.processAction(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
    },
  })

  return { data, isLoading, error, processAction, isPending }
}

export function useApprovalDetail(id: Ref<string>) {
  return useQuery({
    queryKey: computed(() => ['approval', id.value]),
    queryFn: () => approvalsApi.get(id.value),
    enabled: computed(() => !!id.value),
  })
}
