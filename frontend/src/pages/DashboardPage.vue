<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import StatusCard from '@/components/ui/StatusCard.vue'
import DataTable from '@/components/ui/DataTable.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import AgentSignalCard from '@/components/domain/AgentSignalCard.vue'
import CircuitBreakerStatusComp from '@/components/domain/CircuitBreakerStatus.vue'
import NavCurveChart from '@/components/charts/NavCurveChart.vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useApprovals } from '@/composables/useApprovals'
import { usePortfolioOverview } from '@/composables/usePortfolio'
import { backtestApi } from '@/api/backtest'
import { decisionsApi } from '@/api/decisions'
import type { ApprovalStatus } from '@/types/approval'
import { formatRelativeTime, formatWeight, formatDate } from '@/utils/formatters'
import { useEmergencyStore } from '@/store/emergency'

const router = useRouter()
const emergencyStore = useEmergencyStore()
const { connectionStatus } = useWebSocket()

// Time filter
const timeFilter = ref<'today' | 'week' | 'month' | 'all'>('all')

function dateRange(filter: typeof timeFilter.value): { date_from?: string; date_to?: string } {
  const now = new Date()
  const fmt = (d: Date) => d.toISOString().slice(0, 10)
  if (filter === 'today') return { date_from: fmt(now), date_to: fmt(now) }
  if (filter === 'week') {
    const mon = new Date(now); mon.setDate(now.getDate() - now.getDay() + 1)
    return { date_from: fmt(mon), date_to: fmt(now) }
  }
  if (filter === 'month') {
    return { date_from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`, date_to: fmt(now) }
  }
  return {}
}

// Pending approvals
const pendingParams = ref({ status: 'pending', page: 1, page_size: 10 })
const { data: pendingData, isLoading: isLoadingPending } = useApprovals(pendingParams)
const { riskStatus, graphStats } = usePortfolioOverview()

// Latest decision for Agent signals
const { data: latestDecisions } = useQuery({
  queryKey: ['decisions', { page: 1, page_size: 1 }],
  queryFn: () => decisionsApi.list({ page: 1, page_size: 1 }),
  refetchInterval: 30_000,
})
const latestDecision = computed(() => latestDecisions.value?.items?.[0] ?? null)

// Latest backtest for nav curve
const { data: backtestList } = useQuery({
  queryKey: ['backtests'],
  queryFn: () => backtestApi.list({ limit: 1 }),
  staleTime: 60_000,
})
const latestBacktest = computed(() => {
  const list = backtestList.value
  if (!list || !Array.isArray(list)) return null
  return list.find(r => r.status === 'completed' && r.nav_curve) || null
})

const pendingCount = computed(() => pendingData.value?.total ?? 0)

// Banner
const showBanner = ref(localStorage.getItem('platform_banner_dismissed') !== '1')
function dismissBanner() {
  showBanner.value = false
  localStorage.setItem('platform_banner_dismissed', '1')
}

const connectionStatusText: Record<string, string> = {
  connected: '实时连接', connecting: '连接中...', disconnected: '连接断开', fallback: '降级轮询',
}

const statusLabels: Record<string, string> = {
  pending: '待审批', approved: '已通过', rejected: '已拒绝', auto_approved: '自动通过',
}

const tableColumns = [
  { key: 'created_at', label: '时间', width: '140px' },
  { key: 'symbols', label: '涉及标的' },
  { key: 'max_delta', label: '最大调仓', width: '100px', align: 'right' as const },
  { key: 'status', label: '状态', width: '100px', align: 'center' as const },
  { key: 'actions', label: '操作', width: '80px', align: 'center' as const },
]

const tableData = computed(() => {
  const dr = dateRange(timeFilter.value)
  const items = pendingData.value?.items || []
  return items
    .filter(item => {
      if (dr.date_from && item.created_at < dr.date_from) return false
      if (dr.date_to && item.created_at.slice(0, 10) > dr.date_to) return false
      return true
    })
    .map(item => ({
      ...item,
      symbols: item.recommendations.map(r => r.symbol).join(', '),
      max_delta: Math.max(...item.recommendations.map(r => Math.abs(r.weight_delta)), 0),
    }))
})

const timeFilterOptions: { key: typeof timeFilter.value; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'today', label: '今天' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
]
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <!-- Banner -->
    <div v-if="showBanner" class="mb-5 flex items-start gap-3 rounded-lg border border-[var(--brand-primary)] bg-[var(--brand-primary)]/10 px-4 py-3">
      <svg class="mt-0.5 w-4 h-4 flex-shrink-0 text-[var(--brand-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
      </svg>
      <div class="flex-1 text-[13px] text-[var(--text-primary)]">
        <span class="font-semibold">AI Agent 量化交易平台</span> — 多 LLM Agent 协作决策，支持技术/基本面/新闻/情绪四维分析，内置风控熔断与幻觉检测机制。
      </div>
      <button class="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] ml-2" @click="dismissBanner">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold text-[var(--text-primary)]">总览仪表盘</h1>
        <p class="text-[12px] text-[var(--text-tertiary)] mt-0.5">
          {{ new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' }) }}
        </p>
      </div>
      <div class="flex items-center gap-2 text-[12px]">
        <span class="w-2 h-2 rounded-full"
          :class="{
            'ws-dot-connected': connectionStatus === 'connected',
            'ws-dot-connecting animate-blink': connectionStatus === 'connecting',
            'ws-dot-disconnected': connectionStatus === 'disconnected',
            'ws-dot-fallback': connectionStatus === 'fallback',
          }"
        />
        <span class="text-[var(--text-tertiary)]">{{ connectionStatusText[connectionStatus] }}</span>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <StatusCard title="待审批" :value="pendingCount" :clickable="true" @click="router.push('/approvals?status=pending')">
        <template #footer>
          <p v-if="pendingCount > 0" class="text-[11px] text-[var(--warning)] mt-1">需要处理</p>
        </template>
      </StatusCard>
      <StatusCard title="熔断等级" :value="`L${emergencyStore.circuitBreakerLevel}`">
        <template #footer>
          <p class="text-[11px] mt-1" :class="`circuit-${emergencyStore.circuitBreakerLevelName.toLowerCase()}`">
            {{ emergencyStore.circuitBreakerLevelName }}
          </p>
        </template>
      </StatusCard>
      <StatusCard title="图谱节点数" :value="graphStats?.node_count ?? '--'">
        <template #footer><p class="text-[11px] text-[var(--text-tertiary)] mt-1">历史案例</p></template>
      </StatusCard>
      <StatusCard title="平均准确率" :value="graphStats?.avg_accuracy !== undefined ? `${(graphStats.avg_accuracy * 100).toFixed(1)}%` : '--'">
        <template #footer>
          <p class="text-[11px] text-[var(--text-tertiary)] mt-1">
            通过率 {{ graphStats?.approval_rate !== undefined ? `${(graphStats.approval_rate * 100).toFixed(0)}%` : '--' }}
          </p>
        </template>
      </StatusCard>
    </div>

    <!-- Agent signals panel -->
    <div class="mb-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-sm font-semibold text-[var(--text-primary)]">Agent 最新信号</h2>
        <button class="text-[12px] text-[var(--brand-primary)] hover:underline" @click="router.push('/analyze')">
          触发新分析 →
        </button>
      </div>
      <template v-if="latestDecision?.agent_signals?.length">
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <AgentSignalCard
            v-for="signal in latestDecision.agent_signals.filter(s => ['technical','fundamental','news','sentiment'].includes(s.agent_type))"
            :key="signal.agent_type"
            :signal="signal"
            :compact="true"
          />
        </div>
        <p class="text-[11px] text-[var(--text-tertiary)] mt-1.5">
          来自最近一次分析 · {{ latestDecision.symbols?.join(', ') }}
          <button class="ml-1 text-[var(--brand-primary)] hover:underline" @click="router.push(`/decisions/${latestDecision!.id}`)">查看完整链路</button>
        </p>
      </template>
      <div v-else class="card p-8 text-center">
        <p class="text-[var(--text-tertiary)] text-sm mb-2">暂无 Agent 信号</p>
        <button
          class="px-4 py-1.5 text-[13px] font-medium rounded-lg bg-[var(--brand-primary)] text-white hover:opacity-90 transition-opacity"
          @click="router.push('/analyze')"
        >
          前往触发分析
        </button>
      </div>
    </div>

    <!-- Main two columns -->
    <div class="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6 mb-6">
      <!-- Left: decisions list with time filter -->
      <div>
        <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 class="text-sm font-semibold text-[var(--text-primary)]">最新 Agent 决策</h2>
          <div class="flex items-center gap-1">
            <button
              v-for="opt in timeFilterOptions"
              :key="opt.key"
              class="px-2.5 py-1 text-[11px] font-medium rounded-full transition-colors"
              :class="timeFilter === opt.key
                ? 'bg-[var(--brand-primary)] text-white'
                : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
              @click="timeFilter = opt.key"
            >
              {{ opt.label }}
            </button>
            <button class="text-[12px] text-[var(--brand-primary)] hover:underline ml-2" @click="router.push('/approvals')">
              查看全部
            </button>
          </div>
        </div>

        <DataTable :columns="tableColumns" :data="tableData" :loading="isLoadingPending" empty-text="暂无待处理的决策">
          <template #empty>
            <div class="flex flex-col items-center justify-center py-10 gap-3">
              <p class="text-[var(--text-tertiary)] text-sm">还没有决策？点击触发第一次 Agent 分析</p>
              <button
                class="px-4 py-1.5 text-[13px] font-medium rounded-lg bg-[var(--brand-primary)] text-white hover:opacity-90 transition-opacity"
                @click="router.push('/analyze')"
              >
                前往触发分析
              </button>
            </div>
          </template>
          <template #cell-created_at="{ row }">
            <span class="text-[12px] tabular-nums text-[var(--text-secondary)]">{{ formatRelativeTime(row.created_at as string) }}</span>
          </template>
          <template #cell-symbols="{ row }">
            <span class="text-[13px] truncate block max-w-[200px]">{{ row.symbols }}</span>
          </template>
          <template #cell-max_delta="{ row }">
            <span class="tabular-nums">{{ formatWeight(row.max_delta as number) }}</span>
          </template>
          <template #cell-status="{ row }">
            <TagBadge :variant="row.status as ApprovalStatus" :label="statusLabels[row.status as string] || (row.status as string)" size="sm" />
          </template>
          <template #cell-actions="{ row }">
            <button class="text-[12px] text-[var(--brand-primary)] hover:underline" @click="router.push(`/approvals/${row.id}`)">详情</button>
          </template>
        </DataTable>
      </div>

      <!-- Right: System status -->
      <div class="space-y-4">
        <CircuitBreakerStatusComp v-if="riskStatus" :status="riskStatus.circuit_breaker" />

        <div class="card p-4">
          <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">最近风险事件</h4>
          <div v-if="riskStatus?.recent_risk_events?.length" class="space-y-2">
            <div v-for="event in riskStatus.recent_risk_events.slice(0, 3)" :key="event.id" class="flex items-start gap-2 text-[12px]">
              <span class="mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0"
                :class="{ 'bg-[var(--warning)]': event.severity === 'warning', 'bg-[var(--negative)]': event.severity === 'critical' || event.severity === 'emergency' }" />
              <div class="min-w-0 flex-1">
                <p class="text-[var(--text-primary)] truncate">{{ event.description }}</p>
                <p class="text-[var(--text-tertiary)] text-[11px]">{{ formatRelativeTime(event.created_at) }}</p>
              </div>
            </div>
          </div>
          <p v-else class="text-[12px] text-[var(--text-tertiary)]">暂无风险事件</p>
        </div>

        <div class="card p-4">
          <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">经验图谱</h4>
          <div class="grid grid-cols-2 gap-3 text-center">
            <div>
              <p class="text-lg font-semibold text-[var(--text-primary)] tabular-nums">{{ graphStats?.node_count ?? '--' }}</p>
              <p class="text-[11px] text-[var(--text-tertiary)]">节点</p>
            </div>
            <div>
              <p class="text-lg font-semibold text-[var(--text-primary)] tabular-nums">{{ graphStats?.edge_count ?? '--' }}</p>
              <p class="text-[11px] text-[var(--text-tertiary)]">边</p>
            </div>
          </div>
          <button class="mt-3 w-full text-[12px] text-[var(--brand-primary)] hover:underline text-center" @click="router.push('/graph')">
            查看图谱详情
          </button>
        </div>
      </div>
    </div>

    <!-- NAV Curve -->
    <div class="card p-4">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <h3 class="text-sm font-semibold text-[var(--text-primary)]">净值曲线</h3>
          <span v-if="latestBacktest" class="text-[11px] text-[var(--text-tertiary)]">
            {{ latestBacktest.start_date }} ~ {{ latestBacktest.end_date }}
            · 初始资金 {{ latestBacktest.initial_capital?.toLocaleString('zh-CN') }} 元
          </span>
        </div>
        <button v-if="latestBacktest" class="text-[12px] text-[var(--brand-primary)] hover:underline" @click="router.push('/backtest')">
          查看完整回测
        </button>
      </div>
      <template v-if="latestBacktest?.nav_curve">
        <NavCurveChart :data="latestBacktest.nav_curve" height="300px" />
      </template>
      <div v-else class="flex flex-col items-center justify-center py-16 text-center">
        <p class="text-[var(--text-tertiary)] text-sm mb-3">暂无回测数据</p>
        <button class="text-[13px] text-[var(--brand-primary)] hover:underline" @click="router.push('/backtest')">
          前往回测页运行回测
        </button>
      </div>
    </div>
  </div>
</template>
