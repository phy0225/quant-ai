import { ref, onMounted, onUnmounted } from 'vue'
import { useEmergencyStore } from '@/store/emergency'
import { useQueryClient } from '@tanstack/vue-query'

export type WSEventType =
  | 'new_decision'
  | 'approval_updated'
  | 'circuit_breaker_changed'
  | 'emergency_stop_activated'
  | 'emergency_stop_deactivated'
  | 'risk_event'
  | 'ping'

export interface WSMessage {
  type: WSEventType
  data?: Record<string, unknown>
  timestamp: string
}

export function useWebSocket() {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const lastMessage = ref<WSMessage | null>(null)
  const connectionStatus = ref<'connecting' | 'connected' | 'disconnected' | 'fallback'>('disconnected')

  const emergencyStore = useEmergencyStore()
  const queryClient = useQueryClient()

  const MAX_RECONNECT_ATTEMPTS = 5
  const BASE_RECONNECT_DELAY = 1000
  const MAX_RECONNECT_DELAY = 30000
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let fallbackPollTimer: ReturnType<typeof setInterval> | null = null

  const getReconnectDelay = (attempt: number): number => {
    const delay = Math.min(BASE_RECONNECT_DELAY * 2 ** attempt, MAX_RECONNECT_DELAY)
    return delay * (0.8 + Math.random() * 0.4)
  }

  const handleMessage = (message: WSMessage) => {
    switch (message.type) {
      case 'new_decision':
      case 'approval_updated':
        queryClient.invalidateQueries({ queryKey: ['approvals'] })
        queryClient.invalidateQueries({ queryKey: ['decisions'] })
        break

      case 'circuit_breaker_changed':
        if (message.data) {
          emergencyStore.setCircuitBreakerLevel(message.data.level as 0 | 1 | 2 | 3)
        }
        queryClient.invalidateQueries({ queryKey: ['risk-status'] })
        break

      case 'emergency_stop_activated':
        emergencyStore.activateEmergencyStop()
        break

      case 'emergency_stop_deactivated':
        emergencyStore.deactivateEmergencyStop()
        break

      case 'risk_event':
        queryClient.invalidateQueries({ queryKey: ['risk-status'] })
        break

      case 'ping':
        break
    }
  }

  const stopFallbackPolling = () => {
    if (fallbackPollTimer) {
      clearInterval(fallbackPollTimer)
      fallbackPollTimer = null
    }
  }

  const startFallbackPolling = () => {
    stopFallbackPolling()
    fallbackPollTimer = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] })
      queryClient.invalidateQueries({ queryKey: ['risk-status'] })
    }, 30_000)
  }

  const connect = () => {
    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.hostname}:8000/ws`
    connectionStatus.value = 'connecting'

    try {
      ws.value = new WebSocket(wsUrl)
    } catch {
      connectionStatus.value = 'disconnected'
      scheduleReconnect()
      return
    }

    ws.value.onopen = () => {
      isConnected.value = true
      reconnectAttempts.value = 0
      connectionStatus.value = 'connected'
      stopFallbackPolling()
    }

    ws.value.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        lastMessage.value = message
        handleMessage(message)
      } catch {
        // Ignore malformed messages
      }
    }

    ws.value.onclose = () => {
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      scheduleReconnect()
    }

    ws.value.onerror = () => {
      ws.value?.close()
    }
  }

  const scheduleReconnect = () => {
    if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
      connectionStatus.value = 'fallback'
      startFallbackPolling()
      return
    }

    const delay = getReconnectDelay(reconnectAttempts.value)
    reconnectAttempts.value++
    reconnectTimer = setTimeout(connect, delay)
  }

  const disconnect = () => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    stopFallbackPolling()
    ws.value?.close()
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return {
    isConnected,
    connectionStatus,
    lastMessage,
    reconnectAttempts,
    reconnect: connect,
  }
}
