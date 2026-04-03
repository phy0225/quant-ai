<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { approvalsApi } from '@/api/approvals'
import type { ApprovalRecord } from '@/types/approval'

const router = useRouter()
const loading = ref(false)
const status = ref<string | undefined>(undefined)
const rows = ref<ApprovalRecord[]>([])

async function load() {
  loading.value = true
  try {
    const data = await approvalsApi.list({ status: status.value, page: 1, page_size: 50 })
    rows.value = data.items
  } finally {
    loading.value = false
  }
}

async function quickAction(id: string, action: 'approved' | 'rejected') {
  await approvalsApi.processAction(id, { action, reviewed_by: 'admin' })
  await load()
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1200px] mx-auto space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">审批列表</h1>
      <div class="flex gap-2">
        <select v-model="status" class="text-sm" @change="load">
          <option :value="undefined">全部</option>
          <option value="pending">pending</option>
          <option value="approved">approved</option>
          <option value="rejected">rejected</option>
          <option value="modified">modified</option>
        </select>
        <button class="px-3 py-1.5 rounded bg-[var(--brand-primary)] text-white text-sm" @click="load">刷新</button>
      </div>
    </div>

    <div class="card p-4">
      <div v-if="loading" class="text-sm text-[var(--text-tertiary)]">加载中...</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">id</th>
            <th class="py-2">status</th>
            <th class="py-2">orders</th>
            <th class="py-2">created</th>
            <th class="py-2 text-right">actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" class="border-b border-[var(--border-subtle)]">
            <td class="py-2 font-mono text-xs">{{ row.id.slice(0, 8) }}</td>
            <td class="py-2">{{ row.status }}</td>
            <td class="py-2">{{ row.recommendations.length }}</td>
            <td class="py-2 text-xs">{{ row.created_at?.slice(0, 19).replace('T', ' ') }}</td>
            <td class="py-2 text-right space-x-2">
              <button class="text-[var(--brand-primary)] hover:underline" @click="router.push(`/approvals/${row.id}`)">
                详情
              </button>
              <button
                v-if="row.status === 'pending'"
                class="text-[var(--positive)] hover:underline"
                @click="quickAction(row.id, 'approved')"
              >
                通过
              </button>
              <button
                v-if="row.status === 'pending'"
                class="text-[var(--negative)] hover:underline"
                @click="quickAction(row.id, 'rejected')"
              >
                拒绝
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

