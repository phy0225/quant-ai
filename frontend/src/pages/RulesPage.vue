<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { rulesApi } from '@/api/rules'
import { riskApi } from '@/api/risk'
import { settlementApi } from '@/api/settlement'
import type { AgentWeightRow } from '@/api/rules'
import type { AutoApprovalRule, RiskParams } from '@/types/risk'

const loading = ref(false)
const error = ref('')
const rules = ref<AutoApprovalRule[]>([])
const params = ref<RiskParams | null>(null)
const agentWeights = ref<AgentWeightRow[]>([])
const pendingCount = ref(0)
const settleDate = ref(new Date().toISOString().slice(0, 10))
const runningSettlement = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [ruleList, riskParams, weights, pending] = await Promise.all([
      rulesApi.list(),
      riskApi.getRiskParams(),
      rulesApi.getAgentWeights(),
      settlementApi.pending(settleDate.value),
    ])
    rules.value = ruleList
    params.value = riskParams
    agentWeights.value = weights.items
    pendingCount.value = pending.total
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to load rules data.'
  } finally {
    loading.value = false
  }
}

async function toggleRule(id: string) {
  await rulesApi.toggle(id)
  await load()
}

async function runSettlement() {
  runningSettlement.value = true
  error.value = ''
  try {
    await settlementApi.run({ settle_date: settleDate.value })
    await load()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'Failed to run settlement.'
  } finally {
    runningSettlement.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1320px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">Rules</h1>

    <div v-if="loading" class="card p-4 text-sm text-[var(--text-tertiary)]">Loading...</div>
    <div v-else-if="error" class="card p-4 text-sm text-[var(--negative)]">{{ error }}</div>

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="card p-4 lg:col-span-2">
          <h2 class="font-semibold mb-2">Risk Params</h2>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>max_position_weight: {{ params?.max_position_weight }}</div>
            <div>daily_warning: {{ params?.daily_loss_warning_threshold }}</div>
            <div>daily_suspend: {{ params?.daily_loss_suspend_threshold }}</div>
            <div>max_drawdown_emergency: {{ params?.max_drawdown_emergency }}</div>
          </div>
        </div>

        <div class="card p-4 space-y-2">
          <h2 class="font-semibold">Settlement</h2>
          <label class="block text-xs text-[var(--text-secondary)]">settle_date</label>
          <input v-model="settleDate" type="date" @change="load" />
          <p class="text-sm">pending agent signals: <strong>{{ pendingCount }}</strong></p>
          <button
            class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
            :disabled="runningSettlement"
            @click="runSettlement"
          >
            {{ runningSettlement ? 'Running...' : 'Run T+5 Settlement' }}
          </button>
        </div>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">Agent Dynamic Weights</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">agent_type</th>
              <th class="py-2">weight</th>
              <th class="py-2">accuracy_30d</th>
              <th class="py-2">accuracy_60d</th>
              <th class="py-2">is_locked</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in agentWeights" :key="row.agent_type" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.agent_type }}</td>
              <td class="py-2">{{ (row.weight * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ row.accuracy_30d == null ? '--' : `${(row.accuracy_30d * 100).toFixed(1)}%` }}</td>
              <td class="py-2">{{ row.accuracy_60d == null ? '--' : `${(row.accuracy_60d * 100).toFixed(1)}%` }}</td>
              <td class="py-2">{{ row.is_locked ? 'yes' : 'no' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">Auto Approval Rules</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">name</th>
              <th class="py-2">priority</th>
              <th class="py-2">status</th>
              <th class="py-2 text-right">actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rules" :key="row.id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.name }}</td>
              <td class="py-2">{{ row.priority }}</td>
              <td class="py-2">{{ row.is_active ? 'active' : 'inactive' }}</td>
              <td class="py-2 text-right">
                <button class="text-[var(--brand-primary)] hover:underline" @click="toggleRule(row.id)">toggle</button>
              </td>
            </tr>
            <tr v-if="!rules.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="4">No rules configured.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
