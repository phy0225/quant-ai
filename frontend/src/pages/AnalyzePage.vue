<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'

import { decisionsApi } from '@/api/decisions'
import { useAnalysisStore } from '@/store/analysis'
import type { DecisionMode, RebalanceOrder } from '@/types/decision'

const router = useRouter()
const store = useAnalysisStore()
const { currentRun, isPolling } = storeToRefs(store)

const mode = ref<DecisionMode>('targeted')
const symbolsInput = ref('')
const candidateInput = ref('')
const portfolioInput = ref('')
const loading = ref(false)
const error = ref('')
const orders = ref<RebalanceOrder[]>([])
let timer: ReturnType<typeof setTimeout> | null = null

function parseSymbols(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
}

function parsePortfolio(raw: string): Record<string, number> | undefined {
  const map: Record<string, number> = {}
  for (const part of raw.split(',')) {
    const [symbol, w] = part.trim().split(':')
    if (!symbol || !w) continue
    const weight = Number.parseFloat(w.trim())
    if (!Number.isNaN(weight)) map[symbol.trim().toUpperCase()] = weight
  }
  return Object.keys(map).length ? map : undefined
}

function clearTimer() {
  if (timer) {
    clearTimeout(timer)
    timer = null
  }
}

function stopPolling() {
  clearTimer()
  store.clearActiveRun()
}

async function loadOrders() {
  if (!currentRun.value) return
  try {
    orders.value = await decisionsApi.getOrders(currentRun.value.id)
  } catch {
    orders.value = []
  }
}

async function pollStatus(id: string) {
  const detail = await decisionsApi.get(id)
  store.setActiveRun(detail)
  if (detail.status === 'running') {
    timer = setTimeout(() => pollStatus(id), 1800)
    return
  }
  isPolling.value = false
  if (detail.mode === 'rebalance') {
    await loadOrders()
  }
  stopPolling()
}

const canSubmit = computed(() => {
  if (mode.value === 'targeted') return parseSymbols(symbolsInput.value).length > 0
  return parseSymbols(candidateInput.value).length > 0 || !!parsePortfolio(portfolioInput.value)
})

async function handleTrigger() {
  loading.value = true
  error.value = ''
  orders.value = []
  clearTimer()
  try {
    const payload =
      mode.value === 'targeted'
        ? {
            mode: 'targeted' as const,
            symbols: parseSymbols(symbolsInput.value),
          }
        : {
            mode: 'rebalance' as const,
            candidate_symbols: parseSymbols(candidateInput.value),
            current_portfolio: parsePortfolio(portfolioInput.value),
          }

    const run = await decisionsApi.trigger(payload)
    store.setActiveRun(run)
    if (run.status === 'running') {
      isPolling.value = true
      timer = setTimeout(() => pollStatus(run.id), 800)
    } else if (run.mode === 'rebalance') {
      await loadOrders()
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Trigger failed'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  if (store.activeRunId) {
    try {
      const restored = await decisionsApi.get(store.activeRunId)
      store.setActiveRun(restored)
      if (restored.status === 'running') {
        isPolling.value = true
        timer = setTimeout(() => pollStatus(restored.id), 800)
      } else if (restored.mode === 'rebalance') {
        await loadOrders()
      }
    } catch {
      store.clearActiveRun()
    }
  }
})

onUnmounted(clearTimer)
</script>

<template>
  <div class="p-6 max-w-[1100px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">Analyze</h1>

    <div class="card p-4 space-y-4">
      <div class="flex gap-2">
        <button
          class="px-3 py-1.5 rounded text-sm"
          :class="mode === 'targeted' ? 'bg-[var(--brand-primary)] text-white' : 'bg-[var(--bg-elevated)]'"
          @click="mode = 'targeted'"
        >
          targeted
        </button>
        <button
          class="px-3 py-1.5 rounded text-sm"
          :class="mode === 'rebalance' ? 'bg-[var(--brand-primary)] text-white' : 'bg-[var(--bg-elevated)]'"
          @click="mode = 'rebalance'"
        >
          rebalance
        </button>
      </div>

      <div v-if="mode === 'targeted'" class="space-y-2">
        <label class="text-xs text-[var(--text-secondary)] block">symbols (comma separated)</label>
        <input v-model="symbolsInput" placeholder="600519,300750" />
      </div>

      <template v-else>
        <div class="space-y-2">
          <label class="text-xs text-[var(--text-secondary)] block">candidate_symbols</label>
          <input v-model="candidateInput" placeholder="600519,300750,002594" />
        </div>
        <div class="space-y-2">
          <label class="text-xs text-[var(--text-secondary)] block">current_portfolio (symbol:weight)</label>
          <input v-model="portfolioInput" placeholder="600519:0.15,000001:0.10" />
        </div>
      </template>

      <div class="flex gap-2">
        <button
          class="px-4 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="loading || !canSubmit"
          @click="handleTrigger"
        >
          {{ loading ? 'Running...' : 'Trigger' }}
        </button>
        <button class="px-4 py-2 rounded border text-sm" :disabled="!currentRun" @click="stopPolling">
          Stop Polling
        </button>
      </div>
      <p v-if="error" class="text-sm text-[var(--negative)]">{{ error }}</p>
    </div>

    <div v-if="currentRun" class="card p-4 space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold">Run Status</h2>
        <span class="text-sm">{{ currentRun.status }} <span v-if="isPolling">(polling)</span></span>
      </div>
      <div class="text-sm text-[var(--text-secondary)]">mode: {{ currentRun.mode }}</div>
      <div class="text-sm text-[var(--text-secondary)]">symbols: {{ (currentRun.symbols || []).join(', ') }}</div>
      <div class="flex gap-2">
        <button class="text-sm text-[var(--brand-primary)] hover:underline" @click="router.push(`/decisions/${currentRun.id}`)">
          decision detail
        </button>
        <button class="text-sm text-[var(--brand-primary)] hover:underline" @click="router.push('/approvals')">
          approvals
        </button>
      </div>
    </div>

    <div v-if="currentRun?.mode === 'rebalance' && orders.length" class="card p-4">
      <h3 class="font-semibold mb-2">Rebalance Orders (stock-only)</h3>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">symbol</th>
            <th class="py-2">action</th>
            <th class="py-2">current</th>
            <th class="py-2">target</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.symbol" class="border-b border-[var(--border-subtle)]">
            <td class="py-2">{{ o.symbol }}</td>
            <td class="py-2">{{ o.action }}</td>
            <td class="py-2">{{ (o.current_weight * 100).toFixed(1) }}%</td>
            <td class="py-2">{{ (o.target_weight * 100).toFixed(1) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
