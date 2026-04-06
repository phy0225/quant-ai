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
    snapshotError.value = e?.response?.data?.detail || e?.message || '加载因子快照失败。'
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
    taskError.value = e?.response?.data?.detail || e?.message || '创建发现任务失败。'
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
    <h1 class="text-xl font-bold text-[var(--text-primary)]">因子研究</h1>

    <div class="card p-4 space-y-3">
      <h2 class="font-semibold">每日快照</h2>
      <div class="flex items-end gap-3">
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">交易日期</label>
          <input v-model="date" type="date" />
        </div>
        <button class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm" @click="loadSnapshot">加载</button>
      </div>
      <p v-if="loadingSnapshot" class="text-sm text-[var(--text-tertiary)]">加载中...</p>
      <p v-else-if="snapshotError" class="text-sm text-[var(--negative)]">{{ snapshotError }}</p>
      <template v-else-if="snapshot">
        <p class="text-sm">市场状态：<strong>{{ snapshot.market_regime }}</strong></p>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">因子标识</th>
              <th class="py-2">IC/IR</th>
              <th class="py-2">权重</th>
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
      <h2 class="font-semibold">二层人工发现任务</h2>
      <label class="block text-xs text-[var(--text-secondary)]">研究方向</label>
      <textarea v-model="researchDirection" rows="4" placeholder="描述下一步希望探索的因子方向。" />
      <div class="flex items-center gap-3">
        <button
          class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="creatingTask || !researchDirection.trim()"
          @click="createDiscoveryTask"
        >
          {{ creatingTask ? '提交中...' : '创建发现任务' }}
        </button>
        <button class="px-3 py-2 rounded border text-sm" @click="loadTasks">刷新任务</button>
      </div>
      <p v-if="taskError" class="text-sm text-[var(--negative)]">{{ taskError }}</p>

      <table class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">任务编号</th>
            <th class="py-2">状态</th>
            <th class="py-2">研究方向</th>
            <th class="py-2">推荐因子</th>
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
              <td class="py-3 text-[var(--text-tertiary)]" colspan="4">暂无发现任务。</td>
            </tr>
          </tbody>
        </table>
    </div>
  </div>
</template>
