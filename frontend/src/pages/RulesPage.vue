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
    error.value = e?.response?.data?.detail || e?.message || '加载规则数据失败。'
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
    error.value = e?.response?.data?.detail || e?.message || '执行结算失败。'
  } finally {
    runningSettlement.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="p-6 max-w-[1320px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">规则配置</h1>

    <div v-if="loading" class="card p-4 text-sm text-[var(--text-tertiary)]">加载中...</div>
    <div v-else-if="error" class="card p-4 text-sm text-[var(--negative)]">{{ error }}</div>

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div class="card p-4 lg:col-span-2">
          <h2 class="font-semibold mb-2">风控参数</h2>
          <div class="grid grid-cols-2 gap-2 text-sm">
            <div>单标的仓位上限：{{ params?.max_position_weight }}</div>
            <div>日跌幅预警线：{{ params?.daily_loss_warning_threshold }}</div>
            <div>日跌幅暂停线：{{ params?.daily_loss_suspend_threshold }}</div>
            <div>最大回撤紧急线：{{ params?.max_drawdown_emergency }}</div>
          </div>
        </div>

        <div class="card p-4 space-y-2">
          <h2 class="font-semibold">收益结算</h2>
          <label class="block text-xs text-[var(--text-secondary)]">结算日期</label>
          <input v-model="settleDate" type="date" @change="load" />
          <p class="text-sm">待结算信号数：<strong>{{ pendingCount }}</strong></p>
          <button
            class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
            :disabled="runningSettlement"
            @click="runSettlement"
          >
            {{ runningSettlement ? '执行中...' : '执行 T+5 结算' }}
          </button>
        </div>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">智能体动态权重</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">智能体类型</th>
              <th class="py-2">权重</th>
              <th class="py-2">30日准确率</th>
              <th class="py-2">60日准确率</th>
              <th class="py-2">是否锁定</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in agentWeights" :key="row.agent_type" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.agent_type }}</td>
              <td class="py-2">{{ (row.weight * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ row.accuracy_30d == null ? '--' : `${(row.accuracy_30d * 100).toFixed(1)}%` }}</td>
              <td class="py-2">{{ row.accuracy_60d == null ? '--' : `${(row.accuracy_60d * 100).toFixed(1)}%` }}</td>
              <td class="py-2">{{ row.is_locked ? '是' : '否' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">自动审批规则</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">规则名称</th>
              <th class="py-2">优先级</th>
              <th class="py-2">状态</th>
              <th class="py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rules" :key="row.id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.name }}</td>
              <td class="py-2">{{ row.priority }}</td>
              <td class="py-2">{{ row.is_active ? '启用中' : '未启用' }}</td>
              <td class="py-2 text-right">
                <button class="text-[var(--brand-primary)] hover:underline" @click="toggleRule(row.id)">切换</button>
              </td>
            </tr>
            <tr v-if="!rules.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="4">暂无规则配置。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>
