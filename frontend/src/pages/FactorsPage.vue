<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { factorsApi } from '@/api/factors'
import type { FactorDiscoveryTask, FactorSnapshotResponse } from '@/types/factor'

const date = ref(new Date().toISOString().slice(0, 10))
const snapshot = ref<FactorSnapshotResponse | null>(null)
const loadingSnapshot = ref(false)
const snapshotError = ref('')

const researchDirection = ref('')
const creatingTask = ref(false)
const taskError = ref('')
const tasks = ref<FactorDiscoveryTask[]>([])

const effectiveFactors = computed(() => snapshot.value?.effective_factors || [])

async function loadSnapshot() {
  loadingSnapshot.value = true
  snapshotError.value = ''
  try {
    snapshot.value = await factorsApi.daily(date.value)
  } catch (e: any) {
    snapshotError.value = e?.response?.data?.detail || e?.message || 'Failed to load factor snapshot.'
  } finally {
    loadingSnapshot.value = false
  }
}

async function loadTasks() {
  const data = await factorsApi.listDiscoveryTasks(20)
  tasks.value = data.items
}

async function createDiscoveryTask() {
  if (!researchDirection.value.trim()) return
  creatingTask.value = true
  taskError.value = ''
  try {
    await factorsApi.discover({ research_direction: researchDirection.value.trim() })
    researchDirection.value = ''
    await loadTasks()
  } catch (e: any) {
    taskError.value = e?.response?.data?.detail || e?.message || 'Failed to create discovery task.'
  } finally {
    creatingTask.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadSnapshot(), loadTasks()])
})
</script>

<template>
  <div class="p-6 max-w-[1280px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">Factors</h1>

    <div class="card p-4 space-y-3">
      <h2 class="font-semibold">Daily Snapshot</h2>
      <div class="flex items-end gap-3">
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Trade Date</label>
          <input v-model="date" type="date" />
        </div>
        <button class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm" @click="loadSnapshot">Load</button>
      </div>
      <p v-if="loadingSnapshot" class="text-sm text-[var(--text-tertiary)]">Loading...</p>
      <p v-else-if="snapshotError" class="text-sm text-[var(--negative)]">{{ snapshotError }}</p>
      <template v-else-if="snapshot">
        <p class="text-sm">market_regime: <strong>{{ snapshot.market_regime }}</strong></p>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">factor_key</th>
              <th class="py-2">ic_ir</th>
              <th class="py-2">weight</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in effectiveFactors" :key="row.factor_key" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.factor_key }}</td>
              <td class="py-2">{{ row.ic_ir.toFixed(3) }}</td>
              <td class="py-2">{{ (row.weight * 100).toFixed(1) }}%</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>

    <div class="card p-4 space-y-3">
      <h2 class="font-semibold">Layer 2 Manual Discovery Task</h2>
      <label class="block text-xs text-[var(--text-secondary)]">Research Direction</label>
      <textarea v-model="researchDirection" rows="4" placeholder="Describe what factor direction we should discover next." />
      <div class="flex items-center gap-3">
        <button
          class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="creatingTask || !researchDirection.trim()"
          @click="createDiscoveryTask"
        >
          {{ creatingTask ? 'Submitting...' : 'Create Discovery Task' }}
        </button>
        <button class="px-3 py-2 rounded border text-sm" @click="loadTasks">Refresh Tasks</button>
      </div>
      <p v-if="taskError" class="text-sm text-[var(--negative)]">{{ taskError }}</p>

      <table class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">task_id</th>
            <th class="py-2">status</th>
            <th class="py-2">direction</th>
            <th class="py-2">recommended_factors</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.task_id" class="border-b border-[var(--border-subtle)] align-top">
            <td class="py-2 font-mono text-xs">{{ task.task_id.slice(0, 8) }}</td>
            <td class="py-2">{{ task.status }}</td>
            <td class="py-2">{{ task.research_direction }}</td>
            <td class="py-2">
              <div v-for="f in task.recommended_factors" :key="`${task.task_id}-${f.factor_key}`" class="text-xs">
                {{ f.factor_key }} ({{ f.score.toFixed(3) }})
              </div>
            </td>
          </tr>
          <tr v-if="!tasks.length">
            <td class="py-3 text-[var(--text-tertiary)]" colspan="4">No discovery tasks yet.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
