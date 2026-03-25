<script setup lang="ts">
import TagBadge from '@/components/ui/TagBadge.vue'
import { formatDate, formatPercent, formatNumber } from '@/utils/formatters'

interface WeightChange {
  symbol: string
  delta: number
}

interface HistoryCase {
  date: string
  similarity: number
  weights: WeightChange[]
  result: number
  approved?: boolean
}

interface Props {
  case: HistoryCase
  index?: number
}

const props = withDefaults(defineProps<Props>(), {
  index: 0,
})

function getResultLabel(result: number): string {
  return result >= 0 ? '盈' : '亏'
}

function getResultVariant(result: number): 'success' | 'danger' {
  return result >= 0 ? 'success' : 'danger'
}
</script>

<template>
  <div
    class="p-3 bg-[var(--bg-elevated)] rounded-lg border border-[var(--border-subtle)] hover:border-[var(--border-default)] transition-colors"
    role="article"
    :aria-label="`历史案例 #${props.index + 1}，相似度 ${formatNumber(props.case.similarity * 100, 1)}%`"
  >
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-2">
        <span class="text-[11px] text-[var(--text-tertiary)]">#{{ props.index + 1 }}</span>
        <span class="text-[11px] text-[var(--text-tertiary)]">
          {{ formatDate(props.case.date, false) }}
        </span>
      </div>
      <TagBadge
        :variant="getResultVariant(props.case.result)"
        :label="getResultLabel(props.case.result)"
        size="sm"
      />
    </div>

    <!-- Similarity bar -->
    <div class="mb-2">
      <div class="flex items-center justify-between text-[11px] mb-0.5">
        <span class="text-[var(--text-tertiary)]">相似度</span>
        <span class="text-[var(--brand-primary)] tabular-nums font-medium">
          {{ formatNumber(props.case.similarity * 100, 1) }}%
        </span>
      </div>
      <div class="w-full h-1.5 bg-[var(--bg-overlay)] rounded-full" role="progressbar" :aria-valuenow="props.case.similarity * 100" aria-valuemin="0" aria-valuemax="100">
        <div
          class="h-full bg-[var(--brand-primary)] rounded-full transition-all duration-300"
          :style="{ width: `${props.case.similarity * 100}%` }"
        />
      </div>
    </div>

    <!-- Weight adjustments summary -->
    <div v-if="props.case.weights.length > 0" class="mb-2">
      <p class="text-[11px] text-[var(--text-tertiary)] mb-1">权重调整</p>
      <div class="flex flex-wrap gap-1">
        <span
          v-for="w in props.case.weights.slice(0, 4)"
          :key="w.symbol"
          class="inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] bg-[var(--bg-surface)] rounded"
        >
          <span class="text-[var(--text-secondary)]">{{ w.symbol }}</span>
          <span
            class="tabular-nums font-medium"
            :class="w.delta >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'"
          >
            {{ formatPercent(w.delta) }}
          </span>
        </span>
        <span
          v-if="props.case.weights.length > 4"
          class="inline-flex items-center px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)] bg-[var(--bg-surface)] rounded"
        >
          +{{ props.case.weights.length - 4 }}
        </span>
      </div>
    </div>

    <!-- Result -->
    <div class="flex items-center justify-between text-[11px]">
      <span class="text-[var(--text-tertiary)]">历史收益</span>
      <span
        class="tabular-nums font-medium"
        :class="props.case.result >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'"
      >
        {{ formatPercent(props.case.result) }}
      </span>
    </div>
  </div>
</template>
