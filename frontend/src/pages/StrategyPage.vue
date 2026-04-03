<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { strategyApi } from '@/api/strategy'
import type { StrategyExperiment, StrategyVersion } from '@/types/strategy'

const versions = ref<StrategyVersion[]>([])
const experiments = ref<StrategyExperiment[]>([])
const baseVersionId = ref('v1')
const hypothesis = ref('')
const loading = ref(false)
const creating = ref(false)
const error = ref('')

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [v, e] = await Promise.all([strategyApi.listVersions(), strategyApi.listExperiments(20)])
    versions.value = v.items
    experiments.value = e.items
    if (!versions.value.find((row) => row.version_id === baseVersionId.value) && versions.value.length) {
      baseVersionId.value = versions.value[0].version_id
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to load strategy data.'
  } finally {
    loading.value = false
  }
}

async function createExperiment() {
  if (!hypothesis.value.trim()) return
  creating.value = true
  error.value = ''
  try {
    await strategyApi.createExperiment({
      base_version_id: baseVersionId.value,
      hypothesis: hypothesis.value.trim(),
    })
    hypothesis.value = ''
    await loadAll()
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || 'Failed to create experiment.'
  } finally {
    creating.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="p-6 max-w-[1280px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">Strategy</h1>

    <div class="card p-4 space-y-3">
      <h2 class="font-semibold">Layer 3 Manual Evolution Experiment</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">Base Version</label>
          <select v-model="baseVersionId">
            <option v-for="v in versions" :key="v.version_id" :value="v.version_id">{{ v.version_id }} - {{ v.name }}</option>
          </select>
        </div>
      </div>
      <div>
        <label class="block text-xs text-[var(--text-secondary)] mb-1">Hypothesis</label>
        <textarea v-model="hypothesis" rows="4" placeholder="Describe the strategy change hypothesis." />
      </div>
      <div class="flex items-center gap-3">
        <button
          class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="creating || !hypothesis.trim()"
          @click="createExperiment"
        >
          {{ creating ? 'Submitting...' : 'Create Experiment' }}
        </button>
        <button class="px-3 py-2 rounded border text-sm" @click="loadAll">Refresh</button>
      </div>
      <p v-if="error" class="text-sm text-[var(--negative)]">{{ error }}</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div class="card p-4">
        <h2 class="font-semibold mb-2">Versions</h2>
        <p v-if="loading" class="text-sm text-[var(--text-tertiary)]">Loading...</p>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">version_id</th>
              <th class="py-2">parent</th>
              <th class="py-2">name</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in versions" :key="v.version_id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2 font-mono text-xs">{{ v.version_id }}</td>
              <td class="py-2">{{ v.parent_version_id || '--' }}</td>
              <td class="py-2">{{ v.name }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">Experiments</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">experiment_id</th>
              <th class="py-2">status</th>
              <th class="py-2">new_version</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in experiments" :key="e.experiment_id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2 font-mono text-xs">{{ e.experiment_id.slice(0, 8) }}</td>
              <td class="py-2">{{ e.status }}</td>
              <td class="py-2">{{ e.new_version_id || '--' }}</td>
            </tr>
            <tr v-if="!experiments.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="3">No experiments yet.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
