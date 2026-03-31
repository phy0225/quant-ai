import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DecisionRun } from '@/types/decision'

export const useAnalysisStore = defineStore('analysis', () => {
  const activeRunId = ref<string | null>(sessionStorage.getItem('activeRunId'))
  const currentRun  = ref<DecisionRun | null>(null)
  const isPolling   = ref(false)

  const isRunning = computed(
    () => isPolling.value || currentRun.value?.status === 'running'
  )

  function setActiveRun(run: DecisionRun) {
    currentRun.value  = run
    activeRunId.value = run.id
    sessionStorage.setItem('activeRunId', run.id)
  }

  function clearActiveRun() {
    currentRun.value  = null
    activeRunId.value = null
    isPolling.value   = false
    sessionStorage.removeItem('activeRunId')
  }

  return { activeRunId, currentRun, isPolling, isRunning, setActiveRun, clearActiveRun }
})
