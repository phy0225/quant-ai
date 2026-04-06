<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { decisionsApi } from '@/api/decisions'
import type { DecisionRun, RebalanceOrder } from '@/types/decision'
import StatusCard from '@/components/ui/StatusCard.vue'
import { formatDate } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()

const decisionId = computed(() => String(route.params.id || ''))
const loading = ref(false)
const error = ref('')
const run = ref<DecisionRun | null>(null)
const orders = ref<RebalanceOrder[]>([])
let pollTimer: ReturnType<typeof setTimeout> | null = null

const statusTone = computed(() => {
  if (!run.value) return 'text-[var(--text-secondary)] bg-[var(--bg-elevated)]'
  if (run.value.status === 'completed') return 'text-[var(--positive)] bg-[var(--positive)]/10'
  if (run.value.status === 'failed') return 'text-[var(--negative)] bg-[var(--negative)]/10'
  return 'text-[var(--warning)] bg-[var(--warning)]/10'
})

const elapsedMs = computed(() => {
  if (!run.value?.started_at || !run.value?.completed_at) return null
  return new Date(run.value.completed_at).getTime() - new Date(run.value.started_at).getTime()
})

const effectiveFactorCount = computed(() => run.value?.recommendations?.length ?? 0)

const agentAccuracy = computed(() => {
  const signals = (run.value?.agent_signals || []).filter((s) =>
    ['technical', 'fundamental', 'news', 'sentiment'].includes(s.agent_type)
  )
  if (!signals.length) return '--'
  const avg = signals.reduce((sum, row) => sum + (row.confidence || 0), 0) / signals.length
  return `${(avg * 100).toFixed(1)}%`
})

const stockOrders = computed(() => (orders.value || []).filter((row) => /^\d{6}$/.test(row.symbol)))

const statusLabelMap: Record<string, string> = {
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

const modeLabelMap: Record<string, string> = {
  targeted: '定向分析',
  rebalance: '调仓分析',
}

async function loadDecision() {
  if (!decisionId.value) return
  run.value = await decisionsApi.get(decisionId.value)
  if (run.value.mode === 'rebalance') {
    try {
      orders.value = await decisionsApi.getOrders(decisionId.value)
    } catch {
      orders.value = []
    }
  } else {
    orders.value = []
  }
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    await loadDecision()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载决策详情失败。'
  } finally {
    loading.value = false
  }
}

async function pollIfRunning() {
  if (!run.value || run.value.status !== 'running') return
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(async () => {
    await refresh()
    await pollIfRunning()
  }, 1800)
}

onMounted(async () => {
  await refresh()
  await pollIfRunning()
})

onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <div class="p-6 max-w-[1320px] mx-auto space-y-5">
    <div class="flex items-center justify-between">
      <div class="space-y-1">
        <button class="text-sm text-[var(--brand-primary)] hover:underline" @click="router.push('/decisions')">
          返回决策列表
        </button>
        <h1 class="text-xl font-bold text-[var(--text-primary)]">决策详情</h1>
      </div>
      <button class="px-3 py-1.5 rounded bg-[var(--brand-primary)] text-white text-sm" @click="refresh">刷新</button>
    </div>

    <div v-if="loading && !run" class="card p-4 text-sm text-[var(--text-tertiary)]">正在加载决策详情...</div>

    <div v-else-if="run" class="space-y-5">
      <div class="card p-4 space-y-3">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs text-[var(--text-secondary)]">任务编号</span>
          <span class="font-mono text-xs break-all">{{ run.id }}</span>
          <span class="px-2 py-1 rounded text-xs font-medium" :class="statusTone">{{ statusLabelMap[run.status] || run.status }}</span>
          <span class="text-xs text-[var(--text-secondary)]">模式：{{ modeLabelMap[run.mode] || run.mode }}</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
          <div>标的代码：{{ run.symbols?.join(', ') || '--' }}</div>
          <div>触发人：{{ run.triggered_by }}</div>
          <div>开始时间：{{ formatDate(run.started_at) }}</div>
          <div>完成时间：{{ run.completed_at ? formatDate(run.completed_at) : '--' }}</div>
          <div>最终方向：{{ run.final_direction || '--' }}</div>
          <div>风险等级：{{ run.risk_level || '--' }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard title="有效因子数" :value="effectiveFactorCount" />
        <StatusCard title="Agent 平均置信度" :value="agentAccuracy" />
        <StatusCard title="Agent 信号数" :value="run.agent_signals?.length || 0" />
        <StatusCard
          title="耗时"
          :value="elapsedMs === null ? '--' : `${(elapsedMs / 1000).toFixed(1)}s`"
        />
      </div>

      <div v-if="run.mode === 'rebalance'" class="card p-4">
        <div class="flex items-center justify-between mb-2">
          <h2 class="font-semibold">调仓订单（仅股票）</h2>
          <span class="text-xs text-[var(--text-tertiary)]">{{ stockOrders.length }} 条记录</span>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">标的</th>
              <th class="py-2">动作</th>
              <th class="py-2">当前权重</th>
              <th class="py-2">目标权重</th>
              <th class="py-2">变化幅度</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in stockOrders" :key="row.symbol" class="border-b border-[var(--border-subtle)]">
              <td class="py-2">{{ row.symbol }}</td>
              <td class="py-2">{{ row.action === 'buy' ? '买入' : row.action === 'sell' ? '卖出' : '持有' }}</td>
              <td class="py-2">{{ (row.current_weight * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ (row.target_weight * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ (row.weight_delta * 100).toFixed(1) }}%</td>
            </tr>
            <tr v-if="!stockOrders.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="5">暂无调仓订单。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">策略建议</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">标的</th>
              <th class="py-2">当前权重</th>
              <th class="py-2">建议权重</th>
              <th class="py-2">变化幅度</th>
              <th class="py-2">置信度</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in run.recommendations || []"
              :key="`${row.symbol}-${idx}`"
              class="border-b border-[var(--border-subtle)]"
            >
              <td class="py-2">{{ row.symbol }}</td>
              <td class="py-2">{{ ((row.current_weight || 0) * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ ((row.recommended_weight || 0) * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ ((row.weight_delta || 0) * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ (((row.confidence_score || 0) as number) * 100).toFixed(1) }}%</td>
            </tr>
            <tr v-if="!(run.recommendations || []).length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="5">暂无策略建议。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">Agent 信号</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">智能体</th>
              <th class="py-2">方向</th>
              <th class="py-2">置信度</th>
              <th class="py-2">重试次数</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="signal in run.agent_signals || []"
              :key="signal.agent_type"
              class="border-b border-[var(--border-subtle)]"
            >
              <td class="py-2">{{ signal.agent_type }}</td>
              <td class="py-2">{{ signal.direction || '--' }}</td>
              <td class="py-2">{{ ((signal.confidence || 0) * 100).toFixed(1) }}%</td>
              <td class="py-2">{{ signal.retry_count }}</td>
            </tr>
            <tr v-if="!(run.agent_signals || []).length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="4">暂无 Agent 信号。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="run.status === 'failed'" class="card p-4 border border-[var(--negative)]/30">
        <p class="text-sm text-[var(--negative)]">失败原因</p>
        <p class="text-sm text-[var(--text-secondary)]">{{ run.error_message || '未知错误。' }}</p>
      </div>
    </div>

    <div v-else-if="error" class="card p-4 text-sm text-[var(--negative)]">{{ error }}</div>

    <div v-else class="card p-4 text-sm text-[var(--text-tertiary)]">未找到对应的决策记录。</div>
  </div>
</template>
