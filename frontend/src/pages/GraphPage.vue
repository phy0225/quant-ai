<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { graphApi } from '@/api/graph'
import type { GraphNode, GraphStats } from '@/types/graph'

const loading = ref(false)
const error = ref('')
const stats = ref<GraphStats | null>(null)
const nodes = ref<GraphNode[]>([])
const approvedOnly = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [s, n] = await Promise.all([
      graphApi.getStats(),
      graphApi.listNodes({ limit: 100, approved_only: approvedOnly.value }),
    ])
    stats.value = s
    nodes.value = n.items || n.nodes || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to load graph data.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1300px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">Graph</h1>

    <div class="card p-4 flex items-center justify-between">
      <label class="inline-flex items-center gap-2 text-sm">
        <input v-model="approvedOnly" type="checkbox" @change="load" />
        approved only
      </label>
      <button class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm" @click="load">Refresh</button>
    </div>

    <div v-if="loading" class="card p-4 text-sm text-[var(--text-tertiary)]">Loading...</div>
    <div v-else-if="error" class="card p-4 text-sm text-[var(--negative)]">{{ error }}</div>
    <template v-else>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">node_count</p><p class="text-2xl font-semibold">{{ stats?.node_count ?? 0 }}</p></div>
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">edge_count</p><p class="text-2xl font-semibold">{{ stats?.edge_count ?? 0 }}</p></div>
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">avg_accuracy</p><p class="text-2xl font-semibold">{{ stats ? `${(stats.avg_accuracy * 100).toFixed(1)}%` : '--' }}</p></div>
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">approval_rate</p><p class="text-2xl font-semibold">{{ stats ? `${(stats.approval_rate * 100).toFixed(1)}%` : '--' }}</p></div>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">Nodes (v3 metadata)</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">node_id</th>
              <th class="py-2">mode</th>
              <th class="py-2">market_regime</th>
              <th class="py-2">factor_count</th>
              <th class="py-2">outcome_return</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in nodes" :key="row.node_id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2 font-mono text-xs">{{ row.node_id.slice(0, 8) }}</td>
              <td class="py-2">{{ row.mode || '--' }}</td>
              <td class="py-2">{{ row.market_regime || '--' }}</td>
              <td class="py-2">{{ row.factor_snapshot ? Object.keys(row.factor_snapshot).length : 0 }}</td>
              <td class="py-2">{{ (row.outcome_return * 100).toFixed(2) }}%</td>
            </tr>
            <tr v-if="!nodes.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="5">No graph nodes yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
