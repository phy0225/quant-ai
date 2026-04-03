<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { decisionsApi } from '@/api/decisions'
import type { DecisionRun } from '@/types/decision'

const router = useRouter()
const loading = ref(false)
const rows = ref<DecisionRun[]>([])

async function load() {
  loading.value = true
  try {
    const data = await decisionsApi.list({ page: 1, page_size: 50 })
    rows.value = data.items
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1200px] mx-auto space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">决策列表</h1>
      <button class="px-3 py-1.5 rounded bg-[var(--brand-primary)] text-white text-sm" @click="load">刷新</button>
    </div>

    <div class="card p-4">
      <div v-if="loading" class="text-sm text-[var(--text-tertiary)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">ID</th>
            <th class="py-2">模式</th>
            <th class="py-2">状态</th>
            <th class="py-2">标的</th>
            <th class="py-2">时间</th>
            <th class="py-2 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" class="border-b border-[var(--border-subtle)]">
            <td class="py-2 font-mono text-xs">{{ row.id.slice(0, 8) }}</td>
            <td class="py-2">{{ row.mode }}</td>
            <td class="py-2">{{ row.status }}</td>
            <td class="py-2">{{ (row.symbols || []).join(', ') }}</td>
            <td class="py-2 text-xs">{{ row.started_at?.slice(0, 19).replace('T', ' ') }}</td>
            <td class="py-2 text-right">
              <button class="text-[var(--brand-primary)] hover:underline" @click="router.push(`/decisions/${row.id}`)">
                查看
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

