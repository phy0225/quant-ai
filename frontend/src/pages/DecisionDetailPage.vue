<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import TagBadge from '@/components/ui/TagBadge.vue'
import AgentSignalCard from '@/components/domain/AgentSignalCard.vue'
import DecisionTimeline from '@/components/domain/DecisionTimeline.vue'
import { decisionsApi } from '@/api/decisions'
import { formatDate } from '@/utils/formatters'

const route = useRoute()
const router = useRouter()

const decisionId = computed(() => route.params.id as string)

const { data: run, isLoading } = useQuery({
  queryKey: computed(() => ['decision', decisionId.value]),
  queryFn: () => decisionsApi.get(decisionId.value),
  enabled: computed(() => !!decisionId.value),
  refetchInterval: (query) => {
    const status = query.state.data?.status
    return status === 'running' ? 2000 : false
  },
})

const statusLabels: Record<string, string> = {
  running: '分析中',
  completed: '已完成',
  failed: '失败',
}

const directionLabel: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }
const riskLabel: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }

const elapsedMs = computed(() => {
  if (!run.value?.started_at || !run.value?.completed_at) return null
  return new Date(run.value.completed_at).getTime() - new Date(run.value.started_at).getTime()
})

const hallucinationTotal = computed(() => run.value?.hallucination_events?.length ?? 0)
const retryTotal = computed(() => (run.value?.agent_signals ?? []).reduce((s, a) => s + a.retry_count, 0))
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 mb-4 text-[12px]">
      <button class="text-[var(--brand-primary)] hover:underline" @click="router.push('/analyze')">触发分析</button>
      <span class="text-[var(--text-tertiary)]">/</span>
      <span class="text-[var(--text-secondary)]">决策详情</span>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="space-y-4">
      <div class="skeleton h-8 w-1/3 rounded" />
      <div class="skeleton h-64 rounded-lg" />
    </div>

    <template v-else-if="run">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-6 flex-wrap">
        <h1 class="text-xl font-bold text-[var(--text-primary)]">决策详情</h1>
        <TagBadge
          :variant="run.status === 'completed' ? 'approved' : run.status === 'failed' ? 'rejected' : 'pending'"
          :label="statusLabels[run.status] ?? run.status"
        />
        <span v-if="run.final_direction" class="text-sm font-bold"
          :class="run.final_direction === 'buy' ? 'text-[var(--positive)]'
            : run.final_direction === 'sell' ? 'text-[var(--negative)]'
            : 'text-[var(--text-secondary)]'"
        >
          {{ directionLabel[run.final_direction] }}
        </span>
        <span v-if="run.risk_level" class="text-[12px] text-[var(--text-tertiary)]">
          · {{ riskLabel[run.risk_level] ?? run.risk_level }}
        </span>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-[1fr_320px] gap-6">
        <!-- Left: Timeline + Signal cards -->
        <div class="space-y-6">
          <!-- Timeline -->
          <div class="card p-5">
            <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-4">决策链路时间轴</h3>
            <DecisionTimeline
              v-if="run.agent_signals?.length"
              :agent-signals="run.agent_signals"
              :hallucination-events="run.hallucination_events"
              :started-at="run.started_at"
              :completed-at="run.completed_at"
            />
            <p v-else class="text-[12px] text-[var(--text-tertiary)]">
              {{ run.status === 'running' ? '分析进行中，等待 Agent 信号...' : '暂无 Agent 信号数据' }}
            </p>
          </div>

          <!-- Signal cards grid -->
          <div v-if="run.agent_signals?.length">
            <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-3">各 Agent 信号详情</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <AgentSignalCard
                v-for="signal in run.agent_signals"
                :key="signal.agent_type"
                :signal="signal"
              />
            </div>
          </div>
        </div>

        <!-- Right: Summary -->
        <div class="space-y-4">
          <!-- Run info -->
          <div class="card p-4 space-y-2.5 text-[13px]">
            <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">运行信息</h4>
            <div>
              <p class="text-[11px] text-[var(--text-tertiary)] mb-0.5">运行 ID（可用于溯源）</p>
              <p class="font-mono text-[11px] text-[var(--text-primary)] break-all select-all">{{ run.id }}</p>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">分析标的</span>
              <span class="font-medium text-[var(--text-primary)]">{{ (run.symbols ?? []).join(', ') || '—' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">触发来源</span>
              <span class="text-[var(--text-primary)]">{{ run.triggered_by }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-secondary)]">启动时间</span>
              <span class="text-[var(--text-tertiary)] text-[12px]">{{ formatDate(run.started_at) }}</span>
            </div>
            <div v-if="run.completed_at" class="flex justify-between">
              <span class="text-[var(--text-secondary)]">完成时间</span>
              <span class="text-[var(--text-tertiary)] text-[12px]">{{ formatDate(run.completed_at) }}</span>
            </div>
            <div v-if="elapsedMs !== null" class="flex justify-between">
              <span class="text-[var(--text-secondary)]">耗时</span>
              <span class="tabular-nums text-[var(--text-primary)]">{{ (elapsedMs / 1000).toFixed(1) }}s</span>
            </div>
          </div>

          <!-- Quality stats -->
          <div class="card p-4">
            <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">质量指标</h4>
            <div class="grid grid-cols-2 gap-3 text-center">
              <div>
                <p class="text-lg font-bold text-[var(--text-primary)] tabular-nums">
                  {{ run.agent_signals?.length ?? 0 }}
                </p>
                <p class="text-[11px] text-[var(--text-tertiary)]">Agent 信号</p>
              </div>
              <div>
                <p
                  class="text-lg font-bold tabular-nums"
                  :class="hallucinationTotal > 0 ? 'text-[var(--warning)]' : 'text-[var(--positive)]'"
                >
                  {{ hallucinationTotal }}
                </p>
                <p class="text-[11px] text-[var(--text-tertiary)]">幻觉检测</p>
              </div>
              <div>
                <p
                  class="text-lg font-bold tabular-nums"
                  :class="retryTotal > 0 ? 'text-[var(--warning)]' : 'text-[var(--positive)]'"
                >
                  {{ retryTotal }}
                </p>
                <p class="text-[11px] text-[var(--text-tertiary)]">重试次数</p>
              </div>
              <div>
                <p class="text-lg font-bold text-[var(--text-primary)] tabular-nums">
                  {{ run.recommendations?.length ?? 0 }}
                </p>
                <p class="text-[11px] text-[var(--text-tertiary)]">调仓建议</p>
              </div>
            </div>
          </div>

          <!-- Related approval -->
          <div class="card p-4">
            <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">关联审批</h4>
            <button
              class="w-full text-[12px] text-[var(--brand-primary)] hover:underline text-left"
              @click="router.push('/approvals')"
            >
              前往审批列表查看关联审批 →
            </button>
          </div>

          <!-- Error -->
          <div v-if="run.status === 'failed'" class="card p-4 border border-[var(--negative)]/30">
            <p class="text-[var(--negative)] text-[12px] font-semibold mb-1">失败原因</p>
            <p class="text-[12px] text-[var(--text-secondary)]">{{ run.error_message ?? '未知错误' }}</p>
          </div>
        </div>
      </div>
    </template>

    <!-- Not found -->
    <div v-else class="text-center py-20">
      <p class="text-[var(--text-tertiary)]">决策记录不存在</p>
    </div>
  </div>
</template>
