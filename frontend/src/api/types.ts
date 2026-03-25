/**
 * API 通用响应类型定义
 */

/** 分页响应包装 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** API 错误响应 */
export interface ApiError {
  detail: string
  status_code: number
  errors?: Record<string, string[]>
}

/** 健康检查响应 */
export interface HealthCheckResponse {
  status: string
  version: string
  timestamp: string
}
