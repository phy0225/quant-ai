<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { backtestApi } from '@/api/backtest'
import type { BacktestMode, BacktestReport } from '@/types/backtest'

const symbolsInput = ref('600519,300750,000001')
const startDate = ref('2025-01-01')
const endDate = ref('2025-12-31')
const initialCapital = ref(1_000_000)
const backtestMode = ref<BacktestMode>('signal_based')

const loading = ref(false)
const reports = ref<BacktestReport[]>([])
const selectedReport = ref<BacktestReport | null>(null)
const error = ref('')
let pollTimer: ReturnType<typeof setTimeout> | null = null

const reportStatusLabelMap: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

const backtestModeLabelMap: Record<string, string> = {
  signal_based: '信号驱动',
  factor_based: '因子驱动',
}

const metrics = computed(() => {
  if (!selectedReport.value || selectedReport.value.status !== 'completed') return null
  return [
    { label: 'total_return', value: selectedReport.value.total_return },
    { label: 'annualized_return', value: selectedReport.value.annualized_return },
    { label: 'sharpe_ratio', value: selectedReport.value.sharpe_ratio },
    { label: 'max_drawdown', value: selectedReport.value.max_drawdown },
  ]
})

function parseSymbols(raw: string): string[] {
  return raw
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
}

async function loadReports() {
  const data = await backtestApi.list({ limit: 30 })
  reports.value = data.items
}

async function refreshSelected(reportId: string) {
  selectedReport.value = await backtestApi.get(reportId)
  if (selectedReport.value.status === 'running' || selectedReport.value.status === 'pending') {
    if (pollTimer) clearTimeout(pollTimer)
    pollTimer = setTimeout(() => refreshSelected(reportId), 1800)
  }
}

async function runBacktest() {
  loading.value = true
  error.value = ''
  try {
    const created = await backtestApi.run({
      symbols: parseSymbols(symbolsInput.value),
      start_date: startDate.value,
      end_date: endDate.value,
      initial_capital: initialCapital.value,
      benchmark: 'buy_and_hold',
      rebalance_frequency: 'weekly',
      commission_rate: 0.003,
      slippage: 0.001,
      backtest_mode: backtestMode.value,
    })
    await loadReports()
    await refreshSelected(created.id)
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '执行回测失败。'
  } finally {
    loading.value = false
  }
}

async function selectReport(id: string) {
  await refreshSelected(id)
}

onMounted(loadReports)

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="p-6 max-w-[1300px] mx-auto space-y-5">
    <h1 class="text-xl font-bold text-[var(--text-primary)]">回测分析</h1>

    <div class="card p-4 space-y-3">
      <h2 class="font-semibold">运行 v3 回测</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="lg:col-span-2">
          <label class="block text-xs text-[var(--text-secondary)] mb-1">标的代码</label>
          <input v-model="symbolsInput" placeholder="600519,300750,000001" />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">开始日期</label>
          <input v-model="startDate" type="date" />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">结束日期</label>
          <input v-model="endDate" type="date" />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">初始资金</label>
          <input v-model.number="initialCapital" type="number" min="10000" />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">回测模式</label>
          <select v-model="backtestMode">
            <option value="signal_based">信号驱动</option>
            <option value="factor_based">因子驱动</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm disabled:opacity-50"
          :disabled="loading"
          @click="runBacktest"
        >
          {{ loading ? '运行中...' : '执行回测' }}
        </button>
        <button class="px-3 py-2 rounded border text-sm" @click="loadReports">刷新报告</button>
      </div>
      <p v-if="error" class="text-sm text-[var(--negative)]">{{ error }}</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div class="card p-4">
        <h2 class="font-semibold mb-2">报告列表</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">编号</th>
              <th class="py-2">模式</th>
              <th class="py-2">状态</th>
              <th class="py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in reports" :key="r.id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2 font-mono text-xs">{{ r.id.slice(0, 8) }}</td>
              <td class="py-2">{{ backtestModeLabelMap[r.backtest_mode] || r.backtest_mode }}</td>
              <td class="py-2">{{ reportStatusLabelMap[r.status] || r.status }}</td>
              <td class="py-2 text-right">
                <button class="text-[var(--brand-primary)] hover:underline" @click="selectReport(r.id)">查看</button>
              </td>
            </tr>
            <tr v-if="!reports.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="4">暂无回测报告。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">已选报告</h2>
        <div v-if="!selectedReport" class="text-sm text-[var(--text-tertiary)]">请选择一份报告查看详情。</div>
        <template v-else>
          <div class="space-y-1 text-sm mb-3">
            <div>报告编号: <span class="font-mono text-xs">{{ selectedReport.id }}</span></div>
            <div>报告状态: {{ reportStatusLabelMap[selectedReport.status] || selectedReport.status }}</div>
            <div>回测模式: {{ backtestModeLabelMap[selectedReport.backtest_mode] || selectedReport.backtest_mode }}</div>
            <div>回测区间: {{ selectedReport.start_date }} ~ {{ selectedReport.end_date }}</div>
          </div>
          <div v-if="metrics" class="grid grid-cols-2 gap-3">
            <div v-for="m in metrics" :key="m.label" class="border rounded p-2 text-sm">
              <p class="text-[var(--text-secondary)] text-xs">
                {{ m.label === 'total_return' ? '累计收益率' : m.label === 'annualized_return' ? '年化收益率' : m.label === 'sharpe_ratio' ? '夏普比率' : m.label === 'max_drawdown' ? '最大回撤' : m.label }}
              </p>
              <p class="font-semibold">{{ m.value == null ? '--' : m.value }}</p>
            </div>
          </div>
          <p v-if="selectedReport.error_message" class="text-sm text-[var(--negative)] mt-2">{{ selectedReport.error_message }}</p>
        </template>
      </div>
    </div>
  </div>
</template>
