<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  title: string
  value: string | number
  trend?: number | null
  icon?: string
  clickable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  trend: null,
  clickable: false,
})

const emit = defineEmits<{
  click: []
}>()

const trendColor = computed(() => {
  if (props.trend === null || props.trend === undefined || props.trend === 0) return 'text-[var(--text-tertiary)]'
  return props.trend > 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'
})

const trendText = computed(() => {
  if (props.trend === null || props.trend === undefined) return ''
  const sign = props.trend >= 0 ? '+' : ''
  return `${sign}${(props.trend * 100).toFixed(1)}%`
})
</script>

<template>
  <div
    class="card p-4 transition-all"
    :class="[
      props.clickable && 'cursor-pointer hover:shadow-[var(--shadow-card-hover)] hover:border-[var(--border-strong)]',
    ]"
    @click="props.clickable ? emit('click') : undefined"
    role="article"
    :tabindex="props.clickable ? 0 : undefined"
  >
    <div class="flex items-start justify-between">
      <p class="text-[var(--text-secondary)] text-[12px] font-medium mb-1 uppercase tracking-wide">
        {{ props.title }}
      </p>
      <slot name="icon" />
    </div>
    <div class="flex items-end gap-2">
      <span class="text-[var(--text-primary)] text-2xl font-semibold tabular-nums leading-none">
        {{ props.value }}
      </span>
      <span
        v-if="props.trend !== null && props.trend !== undefined"
        class="text-[12px] font-medium tabular-nums pb-0.5"
        :class="trendColor"
      >
        {{ trendText }}
      </span>
    </div>
    <slot name="footer" />
  </div>
</template>
