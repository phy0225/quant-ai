<script setup lang="ts">
import { computed } from 'vue'
import type { AgentSignal, AgentType } from '@/types/decision'
import { AGENT_LABELS } from '@/types/decision'
import { formatRelativeTime, formatNumber } from '@/utils/formatters'

const props = defineProps<{
  signal: AgentSignal
  compact?: boolean
}>()

const directionLabel: Record<string, string> = {
  buy: '买入',
  sell: '卖出',
  hold: '持有',
}

const directionColor = computed(() => {
  switch (props.signal.direction) {
    case 'buy': return 'text-[var(--positive)]'
    case 'sell': return 'text-[var(--negative)]'
    default: return 'text-[var(--text-secondary)]'
  }
})

const borderColor = computed(() => {
  switch (props.signal.direction) {
    case 'buy': return 'border-l-[var(--positive)]'
    case 'sell': return 'border-l-[var(--negative)]'
    default: return 'border-l-[var(--border-subtle)]'
  }
})

const confidencePct = computed(() => Math.round(props.signal.confidence * 100))

const agentIcon: Record<AgentType, string> = {
  technical: '📈',
  fundamental: '📊',
  news: '📰',
  sentiment: '🧠',
  risk: '🛡️',
  executor: '⚡',
}
</script>

<template>
  <div
    class="card p-3 border-l-4 transition-shadow hover:shadow-[var(--shadow-card-hover)]"
    :class="borderColor"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-1.5">
        <span class="text-base leading-none">{{ agentIcon[signal.agent_type] }}</span>
        <span class="text-[13px] font-semibold text-[var(--text-primary)]">
          {{ AGENT_LABELS[signal.agent_type] }}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <!-- Retry warning -->
        <span
          v-if="signal.retry_count > 0"
          class="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-medium rounded bg-[var(--warning)]/15 text-[var(--warning)]"
          :title="`幻觉检测触发 ${signal.retry_count} 次重试`"
        >
          ⚠ 重试×{{ signal.retry_count }}
        </span>
        <!-- Direction badge -->
        <span
          v-if="signal.direction"
          class="text-[12px] font-bold"
          :class="directionColor"
        >
          {{ directionLabel[signal.direction] ?? signal.direction }}
        </span>
        <span v-else class="text-[12px] text-[var(--text-tertiary)]">—</span>
      </div>
    </div>

    <!-- Confidence bar -->
    <div class="mb-2">
      <div class="flex justify-between text-[11px] mb-1">
        <span class="text-[var(--text-tertiary)]">置信度</span>
        <span class="tabular-nums font-medium text-[var(--brand-primary)]">{{ confidencePct }}%</span>
      </div>
      <div class="w-full h-1 bg-[var(--bg-overlay)] rounded-full">
        <div
          class="h-full rounded-full transition-all duration-500"
          :class="signal.direction === 'buy' ? 'bg-[var(--positive)]' : signal.direction === 'sell' ? 'bg-[var(--negative)]' : 'bg-[var(--brand-primary)]'"
          :style="{ width: `${confidencePct}%` }"
        />
      </div>
    </div>

    <!-- Reasoning summary (hide in compact mode) -->
    <p v-if="!compact && signal.reasoning_summary" class="text-[12px] text-[var(--text-secondary)] line-clamp-2 mb-2">
      {{ signal.reasoning_summary }}
    </p>

    <!-- Extra fields -->
    <div v-if="!compact" class="space-y-0.5">
      <div v-if="signal.support_level != null || signal.resistance_level != null" class="flex gap-3 text-[11px]">
        <span v-if="signal.support_level != null" class="text-[var(--text-tertiary)]">
          支撑位 <span class="text-[var(--positive)] tabular-nums">{{ formatNumber(signal.support_level, 2) }}</span>
        </span>
        <span v-if="signal.resistance_level != null" class="text-[var(--text-tertiary)]">
          压力位 <span class="text-[var(--negative)] tabular-nums">{{ formatNumber(signal.resistance_level, 2) }}</span>
        </span>
      </div>
      <div v-if="signal.data_sources?.length" class="text-[11px] text-[var(--text-tertiary)] truncate">
        来源: {{ signal.data_sources.join(' · ') }}
      </div>
    </div>

    <!-- Timestamp -->
    <p class="text-[10px] text-[var(--text-tertiary)] mt-1.5">
      {{ formatRelativeTime(signal.created_at) }}
    </p>
  </div>
</template>
