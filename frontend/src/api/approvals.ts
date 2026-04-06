import apiClient from './client'
import type { ApprovalListResponse, ApprovalRecord, ApprovalActionRequest } from '@/types/approval'

export interface BatchActionRequest {
  approval_ids: string[]
  action: string
  reviewed_by: string
  comment?: string
}

export interface BatchActionFailed {
  id: string
  reason: string
}

export interface BatchActionResponse {
  succeeded: string[]
  failed: BatchActionFailed[]
  total: number
  success_count: number
  fail_count: number
}

export interface ModifyApprovalOrdersRequest {
  modified_weights: Record<string, number>
  reviewed_by: string
  comment?: string
}

export const approvalsApi = {
  list(params?: { status?: string; page?: number; page_size?: number }): Promise<ApprovalListResponse> {
    return apiClient.get('/api/v1/approvals/', { params })
  },

  get(id: string): Promise<ApprovalRecord> {
    return apiClient.get(`/api/v1/approvals/${id}`)
  },

  processAction(id: string, payload: ApprovalActionRequest): Promise<ApprovalRecord> {
    return apiClient.post(`/api/v1/approvals/${id}/action`, payload)
  },

  modifyWeights(id: string, payload: ModifyApprovalOrdersRequest): Promise<ApprovalRecord> {
    return apiClient.put(`/api/v1/approvals/${id}/modify`, payload)
  },

  batchAction(payload: BatchActionRequest): Promise<BatchActionResponse> {
    return apiClient.post('/api/v1/approvals/batch-action', payload)
  },
}
