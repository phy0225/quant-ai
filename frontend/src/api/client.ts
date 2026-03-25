import axios from 'axios'

/**
 * Axios API 客户端
 * 开发环境通过 vite proxy 代理 /api 请求到后端
 * 生产环境使用 VITE_API_BASE_URL 环境变量
 */
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 预留：可在此处添加 auth token
    // const token = localStorage.getItem('auth_token')
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：解包 axios response，直接返回 data
apiClient.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response

      // 422 验证错误
      if (status === 422) {
        console.error('[API] Validation error:', data)
      }

      // 409 冲突（如重复审批）
      if (status === 409) {
        console.warn('[API] Conflict:', data?.detail)
      }

      // 503 服务不可用（如紧急停止）
      if (status === 503) {
        console.warn('[API] Service unavailable:', data?.detail)
      }

      // 500 服务器错误
      if (status >= 500) {
        console.error('[API] Server error:', data)
      }
    } else if (error.request) {
      console.error('[API] Network error: No response received')
    }

    return Promise.reject(error)
  }
)

export default apiClient
