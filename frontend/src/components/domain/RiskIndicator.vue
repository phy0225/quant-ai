<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  level: 0 | 1 | 2 | 3
  label?: string
  showText?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  showText: true,
})

const levelConfig = computed(() => {
  const configs = {
    0: { name: 'NORMAL', label: '正常', colorClass: 'circuit-normal', bgClass: 'circuit-bg-normal' },
    1: { name: 'WARNING', label: '警告', colorClass: 'circuit-warning', bgClass: 'circuit-bg-warning' },
    2: { name: 'SUSPENDED', label: '暂停', colorClass: 'circuit-suspended', bgClass: 'circuit-bg-suspended' },
    3: { name: 'EMERGENCY', label: '紧急', colorClass: 'circuit-emergency', bgClass: 'circuit-bg-emergency' },
  }
  return configs[props.level]
})
</script>

<template>
  <div class="inline-flex items-center gap-1.5">
    <!-- Level dots -->
    <div class="flex items-center gap-0.5">
      <span
        v-for="i in 4"
        :key="i"
        class="w-2 h-2 rounded-full transition-colors"
        :class="[
          i - 1 <= props.level
            ? levelConfig.colorClass.replace('circuit-', 'bg-[var(--') + ')]'
            : 'bg-[var(--bg-overlay)]',
          i - 1 === props.level && props.level > 0 && 'animate-blink',
        ]"
        :style="{
          backgroundColor: i - 1 <= props.level
            ? (props.level === 0 ? 'var(--positive)' : props.level === 1 ? 'var(--warning)' : props.level === 2 ? '#F97316' : 'var(--negative)')
            : 'var(--bg-overlay)',
        }"
      />
    </div>
    <span
      v-if="props.showText"
      class="text-[12px] font-medium"
      :class="levelConfig.colorClass"
    >
      {{ props.label || levelConfig.label }}
    </span>
  </div>
</template>
