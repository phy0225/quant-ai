<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  name: string
  weight: number
  trend?: number | null
  category?: string
}

const props = withDefaults(defineProps<Props>(), {
  trend: null,
  category: '',
})

const trendIcon = computed(() => {
  if (!props.trend) return ''
  return props.trend > 0 ? '&#9650;' : '&#9660;'  // up/down triangles
})

const trendColor = computed(() => {
  if (!props.trend) return 'text-[var(--text-tertiary)]'
  return props.trend > 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'
})
</script>

<template>
  <div class="card p-3 flex items-center justify-between gap-2">
    <div class="min-w-0 flex-1">
      <p class="text-[11px] text-[var(--text-tertiary)] uppercase tracking-wider mb-0.5">
        {{ props.category }}
      </p>
      <p class="text-[13px] text-[var(--text-primary)] font-medium truncate">
        {{ props.name }}
      </p>
    </div>
    <div class="text-right flex-shrink-0">
      <span class="text-[14px] font-semibold tabular-nums text-[var(--text-primary)]">
        {{ props.weight.toFixed(4) }}
      </span>
      <span
        v-if="props.trend !== null && props.trend !== undefined"
        class="block text-[11px] tabular-nums"
        :class="trendColor"
        v-html="trendIcon + ' ' + Math.abs(props.trend).toFixed(4)"
      />
    </div>
  </div>
</template>
