<script setup lang="ts">
import { computed } from 'vue'
import type { RecommendationItem } from '@/types/approval'
import { formatWeight, formatPercent, getReturnColorClass } from '@/utils/formatters'

interface Props {
  recommendations: RecommendationItem[]
}

const props = defineProps<Props>()

const summary = computed(() => {
  if (!props.recommendations.length) return null

  const totalTurnover = props.recommendations.reduce(
    (sum, r) => sum + Math.abs(r.weight_delta), 0
  )
  const maxDelta = Math.max(...props.recommendations.map(r => Math.abs(r.weight_delta)))
  const avgConfidence = props.recommendations.reduce(
    (sum, r) => sum + r.confidence_score, 0
  ) / props.recommendations.length
  const affectedCount = props.recommendations.filter(r => Math.abs(r.weight_delta) > 0.01).length

  return {
    totalTurnover,
    maxDelta,
    avgConfidence,
    affectedCount,
    symbolCount: props.recommendations.length,
  }
})
</script>

<template>
  <div v-if="summary" class="card p-4">
    <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
      组合调整摘要
    </h4>
    <div class="grid grid-cols-2 gap-3">
      <div>
        <p class="text-[11px] text-[var(--text-tertiary)]">涉及标的</p>
        <p class="text-lg font-semibold text-[var(--text-primary)] tabular-nums">
          {{ summary.affectedCount }} / {{ summary.symbolCount }}
        </p>
      </div>
      <div>
        <p class="text-[11px] text-[var(--text-tertiary)]">总换手率</p>
        <p class="text-lg font-semibold tabular-nums" :class="getReturnColorClass(summary.totalTurnover)">
          {{ formatWeight(summary.totalTurnover) }}
        </p>
      </div>
      <div>
        <p class="text-[11px] text-[var(--text-tertiary)]">最大调仓</p>
        <p class="text-lg font-semibold tabular-nums text-[var(--text-primary)]">
          {{ formatWeight(summary.maxDelta) }}
        </p>
      </div>
      <div>
        <p class="text-[11px] text-[var(--text-tertiary)]">平均置信度</p>
        <p class="text-lg font-semibold tabular-nums text-[var(--brand-secondary)]">
          {{ formatWeight(summary.avgConfidence) }}
        </p>
      </div>
    </div>
  </div>
</template>
