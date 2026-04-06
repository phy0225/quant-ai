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
    error.value = err?.response?.data?.detail || err?.message || '加载策略数据失败。'
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
    error.value = err?.response?.data?.detail || err?.message || '创建实验失败。'
  } finally {
    creating.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div class="p-6 max-w-[1280px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">策略开发</h1>

    <div class="card p-4 space-y-3">
      <h2 class="font-semibold">三层人工演化实验</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">基础版本</label>
          <select v-model="baseVersionId">
            <option v-for="v in versions" :key="v.version_id" :value="v.version_id">{{ v.version_id }} - {{ v.name }}</option>
          </select>
        </div>
      </div>
      <div>
        <label class="block text-xs text-[var(--text-secondary)] mb-1">研究假设</label>
        <textarea v-model="hypothesis" rows="4" placeholder="描述本次策略变更的研究假设。" />
      </div>
      <div class="flex items-center gap-3">
        <button
          class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="creating || !hypothesis.trim()"
          @click="createExperiment"
        >
          {{ creating ? '提交中...' : '创建实验' }}
        </button>
        <button class="px-3 py-2 rounded border text-sm" @click="loadAll">刷新</button>
      </div>
      <p v-if="error" class="text-sm text-[var(--negative)]">{{ error }}</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div class="card p-4">
        <h2 class="font-semibold mb-2">版本列表</h2>
        <p v-if="loading" class="text-sm text-[var(--text-tertiary)]">加载中...</p>
        <table v-else class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">版本号</th>
              <th class="py-2">父版本</th>
              <th class="py-2">名称</th>
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
        <h2 class="font-semibold mb-2">实验记录</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">实验编号</th>
              <th class="py-2">状态</th>
              <th class="py-2">新版本</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in experiments" :key="e.experiment_id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2 font-mono text-xs">{{ e.experiment_id.slice(0, 8) }}</td>
              <td class="py-2">{{ e.status }}</td>
              <td class="py-2">{{ e.new_version_id || '--' }}</td>
            </tr>
            <tr v-if="!experiments.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="3">暂无实验记录。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
