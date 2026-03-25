import apiClient from './client'
import type { GraphStats, GraphNodesResponse, GraphSearchRequest, GraphSearchResultItem, GraphNode } from '@/types/graph'

export const graphApi = {
  getStats(): Promise<GraphStats> {
    return apiClient.get('/api/v1/graph/stats')
  },

  listNodes(params?: { limit?: number; approved_only?: boolean; offset?: number }): Promise<GraphNodesResponse> {
    return apiClient.get('/api/v1/graph/nodes', { params })
  },

  search(payload: GraphSearchRequest): Promise<GraphSearchResultItem[]> {
    return apiClient.post('/api/v1/graph/search', payload)
  },

  getNode(nodeId: string): Promise<GraphNode> {
    return apiClient.get(`/api/v1/graph/nodes/${nodeId}`)
  },
}
