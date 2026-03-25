<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import StatusCard from '@/components/ui/StatusCard.vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import DataTable from '@/components/ui/DataTable.vue'
import NavCurveChart from '@/components/charts/NavCurveChart.vue'
import MonthlyReturnHeatmap from '@/components/charts/MonthlyReturnHeatmap.vue'
import PortfolioWeightChart from '@/components/charts/PortfolioWeightChart.vue'
import { backtestApi } from '@/api/backtest'
import { formatPercent, formatNumber, formatDate } from '@/utils/formatters'
import type { BacktestRunRequest, BacktestReport } from '@/types/backtest'

const queryClient = useQueryClient()

const activeTab = ref<'config' | 'history'>('config')

// Form state
const formSymbols = ref('AAPL, GOOGL, MSFT')
const formStartDate = ref('2025-01-01')
const formEndDate = ref('2025-06-30')
const formCapital = ref(1000000)
const formBenchmark = ref<'buy_and_hold' | 'equal_weight' | 'market_cap_weight'>('buy_and_hold')
const formFrequency = ref<'daily' | 'weekly' | 'monthly'>('weekly')
const formCommissionRate = ref(0.003)
const formSlippage = ref(0.001)

const currentReportId = ref<string | null>(null)
const isPolling = ref(false)

const { mutate: submitBacktest, isPending: isSubmitting } = useMutation({
  mutationFn: (payload: BacktestRunRequest) => backtestApi.run(payload),
  onSuccess: (report: BacktestReport) => {
    currentReportId.value = report.id
    isPolling.value = true
    queryClient.invalidateQueries({ queryKey: ['backtests'] })
  },
})

const { data: currentReport } = useQuery({
  queryKey: computed(() => ['backtest', currentReportId.value]),
  queryFn: () => backtestApi.get(currentReportId.value!),
  enabled: computed(() => !!currentReportId.value),
  refetchInterval: computed(() => {
    if (!isPolling.value) return false
    const s = currentReport.value?.status
    return s === 'completed' || s === 'failed' ? false : 3_000
  }),
})

watch(() => currentReport.value?.status, (status) => {
  if (status === 'completed' || status === 'failed') isPolling.value = false
})

const { data: reportList, isLoading: isLoadingList } = useQuery({
  queryKey: ['backtests'],
  queryFn: () => backtestApi.list({ limit: 20 }),
})

function handleSubmit() {
  const symbols = formSymbols.value.split(',').map(s => s.trim()).filter(Boolean)
  if (symbols.length < 2) { alert('至少需要 2 个标的'); return }
  submitBacktest({
    symbols,
    start_date: formStartDate.value,
    end_date: formEndDate.value,
    initial_capital: formCapital.value,
    benchmark: formBenchmark.value,
    rebalance_frequency: formFrequency.value,
    commission_rate: formCommissionRate.value,
    slippage: formSlippage.value,
  })
}

function selectReport(id: string) {
  currentReportId.value = id
  isPolling.value = false
  activeTab.value = 'config'
}

const elapsedTime = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null
watch(isPolling, (val) => {
  if (val) {
    elapsedTime.value = 0
    elapsedTimer = setInterval(() => { elapsedTime.value++ }, 1000)
  } else {
    if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
  }
})

const metricsCards = computed(() => {
  const r = currentReport.value
  if (!r || r.status !== 'completed') return []
  return [
    { title: '累计收益率', value: formatPercent(r.total_return), variant: (r.total_return ?? 0) > 0 ? 'positive' : 'negative' },
    { title: '年化收益率', value: formatPercent(r.annualized_return), variant: (r.annualized_return ?? 0) > 0 ? 'positive' : 'negative' },
    { title: 'Sharpe 比率', value: formatNumber(r.sharpe_ratio), variant: (r.sharpe_ratio ?? 0) > 1 ? 'positive' : 'warning' },
    { title: '最大回撤', value: formatPercent(r.max_drawdown), variant: 'negative' },
    { title: '胜率', value: formatPercent(r.win_rate), variant: (r.win_rate ?? 0) > 0.5 ? 'positive' : 'warning' },
    { title: '平均持仓天数', value: r.avg_holding_days != null ? `${formatNumber(r.avg_holding_days, 1)} 天` : '—', variant: 'default' },
  ]
})

const costCards = computed(() => {
  const r = currentReport.value
  if (!r || r.status !== 'completed') return []
  if (r.total_commission == null && r.total_slippage_cost == null) return []
  return [
    { title: '总手续费', value: r.total_commission != null ? `¥${r.total_commission.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}` : '—' },
    { title: '总滑点成本', value: r.total_slippage_cost != null ? `¥${r.total_slippage_cost.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}` : '—' },
    { title: '手续费率', value: r.commission_rate != null ? `${(r.commission_rate * 1000).toFixed(1)}‰` : '—' },
    { title: '滑点', value: r.slippage != null ? `${(r.slippage * 100).toFixed(2)}%` : '—' },
  ]
})

const historyColumns = [
  { key: 'created_at', label: '提交时间', width: '140px' },
  { key: 'symbol_count', label: '标的数', width: '70px', align: 'center' as const },
  { key: 'date_range', label: '回测区间', width: '180px' },
  { key: 'annualized_return', label: '年化收益', width: '100px', align: 'right' as const },
  { key: 'sharpe_ratio', label: 'Sharpe', width: '80px', align: 'right' as const },
  { key: 'max_drawdown', label: '最大回撤', width: '100px', align: 'right' as const },
  { key: 'status', label: '状态', width: '80px', align: 'center' as const },
  { key: 'actions', label: '', width: '60px', align: 'center' as const },
]

const historyData = computed(() =>
  (reportList.value || []).map(r => ({
    ...r,
    symbol_count: r.symbols?.length ?? 0,
    date_range: `${r.start_date} ~ ${r.end_date}`,
  }))
)
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <h1 class="text-xl font-bold text-[var(--text-primary)] mb-6">历史回测</h1>

    <!-- Tabs -->
    <div class="flex gap-1 mb-6 border-b border-[var(--border-subtle)]">
      <button
        v-for="tab in [{ key: 'config', label: '配置 & 结果' }, { key: 'history', label: '历史报告' }]"
        :key="tab.key"
        class="px-4 py-2 text-[13px] font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === tab.key
          ? 'text-[var(--brand-primary)] border-[var(--brand-primary)]'
          : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]'"
        @click="activeTab = tab.key as any"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Config & Results -->
    <div v-if="activeTab === 'config'" class="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">
      <!-- Form -->
      <div class="card p-5 self-start">
        <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-1">回测配置</h3>
        <p class="text-[12px] text-[var(--text-tertiary)] mb-4">
          回测使用历史因子数据模拟 Agent 决策，评估策略在指定时间段内的表现，并正确扣除手续费与滑点。
        </p>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">标的（逗号分隔）</label>
            <input v-model="formSymbols" type="text" placeholder="AAPL, GOOGL, MSFT" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">开始日期</label>
              <input v-model="formStartDate" type="date" />
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">结束日期</label>
              <input v-model="formEndDate" type="date" />
            </div>
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">初始资金</label>
            <input v-model.number="formCapital" type="number" min="10000" step="100000" />
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">对比基准</label>
            <select v-model="formBenchmark">
              <option value="buy_and_hold">买持（Buy & Hold）</option>
              <option value="equal_weight">等权</option>
              <option value="market_cap_weight">市值加权</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">调仓频率</label>
            <select v-model="formFrequency">
              <option value="daily">每日</option>
              <option value="weekly">每周</option>
              <option value="monthly">每月</option>
            </select>
          </div>
          <!-- Trading costs -->
          <div class="pt-1 border-t border-[var(--border-subtle)]">
            <p class="text-[11px] font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-2">交易成本参数</p>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">手续费率</label>
                <div class="relative">
                  <input v-model.number="formCommissionRate" type="number" min="0" max="0.05" step="0.001" />
                  <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-[var(--text-tertiary)] pointer-events-none">
                    {{ (formCommissionRate * 1000).toFixed(1) }}‰
                  </span>
                </div>
              </div>
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">滑点</label>
                <div class="relative">
                  <input v-model.number="formSlippage" type="number" min="0" max="0.05" step="0.0001" />
                  <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[11px] text-[var(--text-tertiary)] pointer-events-none">
                    {{ (formSlippage * 100).toFixed(2) }}%
                  </span>
                </div>
              </div>
            </div>
            <p class="text-[10px] text-[var(--text-tertiary)] mt-1">
              手续费按每笔交易金额收取；滑点为实际成交价与理想价格的偏差。
            </p>
          </div>

          <ActionButton variant="primary" size="lg" class="w-full" :loading="isSubmitting" @click="handleSubmit">
            提交回测
          </ActionButton>
        </div>
      </div>

      <!-- Results -->
      <div>
        <!-- Polling -->
        <div v-if="isPolling" class="card p-8 text-center mb-6">
          <div class="animate-spin w-8 h-8 border-2 border-[var(--brand-primary)] border-t-transparent rounded-full mx-auto mb-3" />
          <p class="text-[var(--text-primary)] text-sm font-medium">回测执行中...</p>
          <p class="text-[var(--text-tertiary)] text-[12px] tabular-nums mt-1">已耗时 {{ elapsedTime }}s</p>
          <div class="mt-3 mx-auto w-48 h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
            <div class="h-full bg-[var(--brand-primary)] rounded-full transition-all duration-1000"
              :style="{ width: `${Math.min(95, elapsedTime / 1.8)}%` }" />
          </div>
        </div>

        <!-- Completed -->
        <template v-else-if="currentReport?.status === 'completed'">
          <!-- 6 metrics -->
          <div class="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
            <div v-for="(card, idx) in metricsCards" :key="idx" class="card p-3">
              <p class="text-[11px] text-[var(--text-tertiary)] uppercase tracking-wider mb-1">{{ card.title }}</p>
              <p class="text-lg font-semibold tabular-nums"
                :class="{
                  'text-[var(--positive)]': card.variant === 'positive',
                  'text-[var(--negative)]': card.variant === 'negative',
                  'text-[var(--warning)]': card.variant === 'warning',
                  'text-[var(--text-primary)]': card.variant === 'default',
                }"
              >
                {{ card.value }}
              </p>
            </div>
          </div>

          <!-- Cost breakdown -->
          <div v-if="costCards.length" class="card p-4 mb-4">
            <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">交易成本明细</h4>
            <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div v-for="card in costCards" :key="card.title">
                <p class="text-[11px] text-[var(--text-tertiary)] mb-0.5">{{ card.title }}</p>
                <p class="text-[14px] font-semibold tabular-nums text-[var(--text-primary)]">{{ card.value }}</p>
              </div>
            </div>
          </div>

          <!-- NAV Curve -->
          <div class="card p-4 mb-4">
            <h4 class="text-sm font-semibold text-[var(--text-primary)] mb-3">
              净值曲线
              <span class="text-[11px] text-[var(--text-tertiary)] font-normal ml-2">
                vs 买持基准（{{ currentReport.benchmark }}）
              </span>
            </h4>
            <NavCurveChart
              v-if="currentReport.nav_curve?.length"
              :data="currentReport.nav_curve"
              height="320px"
            />
            <p v-else class="text-[var(--text-tertiary)] text-sm text-center py-8">暂无净值曲线数据</p>
          </div>

          <!-- Monthly heatmap -->
          <div class="card p-4 mb-4">
            <h4 class="text-sm font-semibold text-[var(--text-primary)] mb-3">月度收益热力图</h4>
            <MonthlyReturnHeatmap
              v-if="currentReport.monthly_returns?.length"
              :data="currentReport.monthly_returns"
              height="200px"
            />
            <p v-else class="text-[var(--text-tertiary)] text-sm text-center py-8">暂无月度收益数据</p>
          </div>
        </template>

        <!-- Failed -->
        <div v-else-if="currentReport?.status === 'failed'" class="card p-8 text-center">
          <p class="text-[var(--negative)] text-sm font-medium mb-2">回测执行失败</p>
          <p v-if="currentReport.error_message" class="text-[var(--text-tertiary)] text-xs">{{ currentReport.error_message }}</p>
        </div>

        <!-- Empty -->
        <div v-else class="card p-16 text-center">
          <p class="text-[var(--text-tertiary)] text-sm">配置并提交回测以查看结果</p>
        </div>
      </div>
    </div>

    <!-- History tab -->
    <div v-if="activeTab === 'history'">
      <DataTable :columns="historyColumns" :data="historyData" :loading="isLoadingList" empty-text="暂无历史回测记录">
        <template #cell-created_at="{ row }">
          <span class="text-[12px] tabular-nums text-[var(--text-secondary)]">{{ formatDate(row.created_at as string) }}</span>
        </template>
        <template #cell-annualized_return="{ row }">
          <span class="tabular-nums"
            :class="(row.annualized_return as number | null) != null && (row.annualized_return as number) >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'">
            {{ formatPercent(row.annualized_return as number | null) }}
          </span>
        </template>
        <template #cell-sharpe_ratio="{ row }">
          <span class="tabular-nums">{{ formatNumber(row.sharpe_ratio as number | null) }}</span>
        </template>
        <template #cell-max_drawdown="{ row }">
          <span class="tabular-nums text-[var(--negative)]">{{ formatPercent(row.max_drawdown as number | null) }}</span>
        </template>
        <template #cell-status="{ row }">
          <span class="text-[12px]"
            :class="{ 'text-[var(--positive)]': row.status === 'completed', 'text-[var(--warning)]': row.status === 'running' || row.status === 'pending', 'text-[var(--negative)]': row.status === 'failed' }">
            {{ row.status }}
          </span>
        </template>
        <template #cell-actions="{ row }">
          <button v-if="row.status === 'completed'" class="text-[12px] text-[var(--brand-primary)] hover:underline" @click="selectReport(row.id as string)">
            查看
          </button>
        </template>
      </DataTable>
    </div>
  </div>
</template>
