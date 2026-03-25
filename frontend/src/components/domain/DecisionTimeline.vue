<script setup lang="ts">
import { computed } from 'vue'
import type { AgentSignal, HallucinationEvent, AgentType } from '@/types/decision'
import { AGENT_LABELS } from '@/types/decision'
import { formatDate } from '@/utils/formatters'
import TagBadge from '@/components/ui/TagBadge.vue'

const props = defineProps<{
  agentSignals: AgentSignal[]
  hallucinationEvents?: HallucinationEvent[]
  startedAt: string
  completedAt?: string | null
}>()

const AGENT_ORDER: AgentType[] = ['technical', 'fundamental', 'news', 'sentiment', 'risk', 'executor']

const sortedSignals = computed(() =>
  [...props.agentSignals].sort(
    (a, b) => AGENT_ORDER.indexOf(a.agent_type) - AGENT_ORDER.indexOf(b.agent_type)
  )
)

function hallucinationsFor(agentType: AgentType) {
  return (props.hallucinationEvents ?? []).filter(e => e.agent_type === agentType)
}

const hallucinationLabels: Record<string, string> = {
  structure_violation: '结构违规',
  data_mismatch: '数值幻觉',
  logic_contradiction: '逻辑矛盾',
}

const directionLabel: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }
</script>

<template>
  <div class="space-y-0">
    <!-- Start node -->
    <div class="flex gap-3">
      <div class="flex flex-col items-center">
        <div class="w-3 h-3 rounded-full bg-[var(--brand-primary)] mt-1.5 flex-shrink-0" />
        <div class="w-px flex-1 bg-[var(--border-subtle)] my-1" />
      </div>
      <div class="pb-4">
        <p class="text-[12px] font-medium text-[var(--text-primary)]">分析启动</p>
        <p class="text-[11px] text-[var(--text-tertiary)]">{{ formatDate(startedAt) }}</p>
      </div>
    </div>

    <!-- Agent nodes -->
    <div v-for="(signal, idx) in sortedSignals" :key="signal.agent_type" class="flex gap-3">
      <div class="flex flex-col items-center">
        <div
          class="w-3 h-3 rounded-full mt-1.5 flex-shrink-0 border-2"
          :class="signal.retry_count > 0 ? 'bg-[var(--warning)] border-[var(--warning)]' : 'bg-[var(--bg-surface)] border-[var(--brand-primary)]'"
        />
        <div v-if="idx < sortedSignals.length - 1 || completedAt" class="w-px flex-1 bg-[var(--border-subtle)] my-1" />
      </div>
      <div class="pb-4 min-w-0 flex-1">
        <div class="flex items-center gap-2 flex-wrap mb-1">
          <span class="text-[12px] font-semibold text-[var(--text-primary)]">
            {{ AGENT_LABELS[signal.agent_type] }}
          </span>
          <span
            v-if="signal.direction"
            class="text-[11px] font-bold"
            :class="signal.direction === 'buy' ? 'text-[var(--positive)]' : signal.direction === 'sell' ? 'text-[var(--negative)]' : 'text-[var(--text-secondary)]'"
          >
            {{ directionLabel[signal.direction] ?? signal.direction }}
          </span>
          <span class="text-[11px] text-[var(--brand-primary)] tabular-nums">
            置信度 {{ Math.round(signal.confidence * 100) }}%
          </span>
          <span
            v-if="signal.retry_count > 0"
            class="text-[10px] font-medium text-[var(--warning)]"
          >
            ⚠ 重试×{{ signal.retry_count }}
          </span>
        </div>
        <p class="text-[12px] text-[var(--text-secondary)] mb-1.5">{{ signal.reasoning_summary }}</p>

        <!-- Hallucination events for this agent -->
        <div v-if="hallucinationsFor(signal.agent_type).length" class="space-y-1 mb-1.5">
          <div
            v-for="(evt, ei) in hallucinationsFor(signal.agent_type)"
            :key="ei"
            class="flex items-start gap-1.5 text-[11px] p-1.5 rounded bg-[var(--warning)]/10 border border-[var(--warning)]/30"
          >
            <span class="text-[var(--warning)] flex-shrink-0">⚠</span>
            <span class="text-[var(--text-secondary)]">
              {{ hallucinationLabels[evt.event_type] ?? evt.event_type }} — {{ evt.description }}
              <span v-if="evt.resolved" class="text-[var(--positive)] ml-1">（已解决）</span>
              <span v-else class="text-[var(--negative)] ml-1">（未解决）</span>
            </span>
          </div>
        </div>

        <p class="text-[10px] text-[var(--text-tertiary)]">{{ formatDate(signal.created_at) }}</p>
      </div>
    </div>

    <!-- End node -->
    <div v-if="completedAt" class="flex gap-3">
      <div class="flex flex-col items-center">
        <div class="w-3 h-3 rounded-full bg-[var(--positive)] mt-1.5 flex-shrink-0" />
      </div>
      <div class="pb-2">
        <p class="text-[12px] font-medium text-[var(--positive)]">决策完成</p>
        <p class="text-[11px] text-[var(--text-tertiary)]">{{ formatDate(completedAt) }}</p>
      </div>
    </div>
  </div>
</template>
