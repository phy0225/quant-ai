<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { approvalsApi } from '@/api/approvals'
import type { ApprovalRecord } from '@/types/approval'

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id as string)

const loading = ref(false)
const saving = ref(false)
const approval = ref<ApprovalRecord | null>(null)
const reviewer = ref('risk-admin')
const modifyMap = ref<Record<string, number>>({})

const statusLabelMap: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已拒绝',
  modified: '已修改',
  auto_approved: '自动通过',
}

const stockRows = computed(() =>
  (approval.value?.recommendations || []).filter((r) => /^\d{6}$/.test(r.symbol))
)

async function load() {
  loading.value = true
  try {
    approval.value = await approvalsApi.get(id.value)
    modifyMap.value = Object.fromEntries((approval.value.recommendations || []).map((r) => [r.symbol, r.recommended_weight]))
  } finally {
    loading.value = false
  }
}

async function approve(action: 'approved' | 'rejected') {
  saving.value = true
  try {
    await approvalsApi.processAction(id.value, { action, reviewed_by: reviewer.value })
    await load()
  } finally {
    saving.value = false
  }
}

async function modify() {
  saving.value = true
  try {
    await approvalsApi.modifyWeights(id.value, {
      modified_weights: modifyMap.value,
      reviewed_by: reviewer.value,
    })
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1200px] mx-auto space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">审批详情</h1>
      <button class="text-sm text-[var(--brand-primary)] hover:underline" @click="router.push('/approvals')">返回列表</button>
    </div>

    <div class="card p-4 space-y-3">
      <p v-if="loading" class="text-sm text-[var(--text-tertiary)]">加载中...</p>
      <template v-else-if="approval">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div>审批编号: <span class="font-mono text-xs">{{ approval.id }}</span></div>
          <div>审批状态: {{ statusLabelMap[approval.status] || approval.status }}</div>
          <div>决策任务: <span class="font-mono text-xs">{{ approval.decision_run_id }}</span></div>
        </div>

        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">审批人</label>
          <input v-model="reviewer" />
        </div>

        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">标的</th>
              <th class="py-2">当前权重</th>
              <th class="py-2">建议权重</th>
              <th class="py-2">修改权重</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stockRows" :key="row.symbol" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.symbol }}</td>
              <td class="py-2">{{ (row.current_weight * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ (row.recommended_weight * 100).toFixed(1) }}%</td>
              <td class="py-2 w-40">
                <input v-model.number="modifyMap[row.symbol]" type="number" min="0" max="1" step="0.01" />
              </td>
            </tr>
          </tbody>
        </table>

        <div class="flex gap-2">
          <button class="px-3 py-1.5 rounded border text-sm" :disabled="saving" @click="modify">修改权重</button>
          <button class="px-3 py-1.5 rounded bg-[var(--positive)] text-white text-sm" :disabled="saving" @click="approve('approved')">通过</button>
          <button class="px-3 py-1.5 rounded bg-[var(--negative)] text-white text-sm" :disabled="saving" @click="approve('rejected')">拒绝</button>
        </div>
      </template>
    </div>
  </div>
</template>
