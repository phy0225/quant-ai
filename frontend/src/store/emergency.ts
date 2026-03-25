import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * 紧急停止 Store
 * 管理全局紧急停止状态和熔断等级
 * 由 WebSocket 消息驱动更新（task-015）
 */
export const useEmergencyStore = defineStore('emergency', () => {
  // 是否已激活紧急停止
  const isActive = ref(false)
  // 激活时间（ISO 字符串）
  const activatedAt = ref<string | null>(null)
  // 激活操作人
  const activatedBy = ref<string | null>(null)
  // 熔断等级：0=正常，1=警告，2=暂停，3=紧急
  const circuitBreakerLevel = ref<0 | 1 | 2 | 3>(0)

  /**
   * 熔断等级名称
   */
  const circuitBreakerLevelName = computed(() => {
    const names: Record<number, string> = {
      0: 'NORMAL',
      1: 'WARNING',
      2: 'SUSPENDED',
      3: 'EMERGENCY',
    }
    return names[circuitBreakerLevel.value] as 'NORMAL' | 'WARNING' | 'SUSPENDED' | 'EMERGENCY'
  })

  /**
   * 是否可以执行审批操作
   * 熔断三级或紧急停止激活时，所有操作均被禁止
   */
  const canExecuteApproval = computed(() => {
    return !isActive.value && circuitBreakerLevel.value < 3
  })

  /**
   * 激活紧急停止
   */
  function activate(by?: string) {
    isActive.value = true
    activatedAt.value = new Date().toISOString()
    activatedBy.value = by ?? null
  }

  /**
   * 解除紧急停止
   */
  function restore() {
    isActive.value = false
    activatedAt.value = null
    activatedBy.value = null
  }

  /**
   * 设置熔断等级（由 WebSocket 或 API 响应驱动）
   */
  function setCircuitBreakerLevel(level: 0 | 1 | 2 | 3) {
    circuitBreakerLevel.value = level
    // 三级熔断时自动激活紧急状态标记
    if (level === 3 && !isActive.value) {
      isActive.value = true
      activatedAt.value = new Date().toISOString()
    }
    // 恢复正常时清除紧急状态
    if (level === 0) {
      isActive.value = false
      activatedAt.value = null
    }
  }

  /**
   * 从 API 同步完整状态
   */
  function syncFromApi(data: {
    emergency_stop_active: boolean
    circuit_breaker_level: 0 | 1 | 2 | 3
  }) {
    isActive.value = data.emergency_stop_active
    circuitBreakerLevel.value = data.circuit_breaker_level
  }

  // 兼容旧接口命名
  const activateEmergencyStop = activate
  const deactivateEmergencyStop = restore
  const isEmergencyActive = isActive

  return {
    isActive,
    isEmergencyActive,
    activatedAt,
    activatedBy,
    circuitBreakerLevel,
    circuitBreakerLevelName,
    canExecuteApproval,
    activate,
    restore,
    activateEmergencyStop,
    deactivateEmergencyStop,
    setCircuitBreakerLevel,
    syncFromApi,
  }
})
