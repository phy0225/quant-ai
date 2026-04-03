<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { approvalsApi } from '@/api/approvals'
import { decisionsApi } from '@/api/decisions'

const router = useRouter()

const loading = ref(false)
const pendingCount = ref(0)
const decisionCount = ref(0)
const effectiveFactorCount = ref(0)
const agentAccuracy = ref(0)
const latestDecisions = ref<any[]>([])

async function load() {
  loading.value = true
  try {
    const [approvals, decisions, graphStats] = await Promise.all([
      approvalsApi.list({ status: 'pending', page: 1, page_size: 1 }),
      decisionsApi.list({ page: 1, page_size: 8 }),
      fetch('/api/v1/graph/stats').then((r) => r.json()).catch(() => null),
    ])

    pendingCount.value = approvals.total ?? 0
    decisionCount.value = decisions.total ?? 0
    latestDecisions.value = decisions.items ?? []
    agentAccuracy.value = graphStats?.avg_accuracy ? Number(graphStats.avg_accuracy) : 0

    const first = latestDecisions.value.find((d) => d.status === 'completed')
    effectiveFactorCount.value = Array.isArray(first?.recommendations) ? first.recommendations.length : 0
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1200px] mx-auto space-y-5">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">总览仪表盘</h1>
      <button class="px-3 py-1.5 rounded bg-[var(--brand-primary)] text-white text-sm" @click="load">刷新</button>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">待审批</p>
        <p class="text-2xl font-semibold">{{ pendingCount }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">决策总数</p>
        <p class="text-2xl font-semibold">{{ decisionCount }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">有效因子数</p>
        <p class="text-2xl font-semibold">{{ effectiveFactorCount }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">Agent准确率</p>
        <p class="text-2xl font-semibold">{{ (agentAccuracy * 100).toFixed(1) }}%</p>
      </div>
    </div>

    <div class="card p-4">
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-semibold">最近决策</h2>
        <button class="text-sm text-[var(--brand-primary)] hover:underline" @click="router.push('/decisions')">查看全部</button>
      </div>
      <div v-if="loading" class="text-sm text-[var(--text-tertiary)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">时间</th>
            <th class="py-2">模式</th>
            <th class="py-2">状态</th>
            <th class="py-2">标的</th>
            <th class="py-2 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in latestDecisions" :key="row.id" class="border-b border-[var(--border-subtle)]">
            <td class="py-2 text-xs">{{ row.started_at?.slice(0, 19).replace('T', ' ') }}</td>
            <td class="py-2">{{ row.mode }}</td>
            <td class="py-2">{{ row.status }}</td>
            <td class="py-2">{{ (row.symbols || []).join(', ') }}</td>
            <td class="py-2 text-right">
              <button class="text-[var(--brand-primary)] hover:underline" @click="router.push(`/decisions/${row.id}`)">详情</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

