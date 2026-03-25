<script setup lang="ts">
import { computed } from 'vue'
import type { CircuitBreakerStatus as CBStatus } from '@/types/risk'
import ActionButton from '@/components/ui/ActionButton.vue'
import { formatDate } from '@/utils/formatters'

interface Props {
  status: CBStatus
}

const props = defineProps<Props>()

const emit = defineEmits<{
  reset: []
}>()

const levels = [
  { level: 0, name: 'NORMAL', label: '正常', color: 'var(--positive)' },
  { level: 1, name: 'WARNING', label: '警告', color: 'var(--warning)' },
  { level: 2, name: 'SUSPENDED', label: '暂停', color: '#F97316' },
  { level: 3, name: 'EMERGENCY', label: '紧急', color: 'var(--negative)' },
]

const currentLevel = computed(() => levels[props.status.level])

const isNormal = computed(() => props.status.level === 0)
</script>

<template>
  <div class="card p-4">
    <div class="flex items-center justify-between mb-3">
      <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
        熔断状态
      </h4>
      <ActionButton
        v-if="!isNormal"
        variant="outline"
        size="sm"
        @click="emit('reset')"
      >
        重置
      </ActionButton>
    </div>

    <!-- Level indicator -->
    <div class="flex items-center gap-3 mb-3">
      <span
        class="text-2xl font-bold tabular-nums"
        :style="{ color: currentLevel.color }"
      >
        L{{ props.status.level }}
      </span>
      <span
        class="text-sm font-medium"
        :style="{ color: currentLevel.color }"
      >
        {{ currentLevel.label }}
      </span>
    </div>

    <!-- Progress bar -->
    <div class="flex gap-1 mb-3">
      <div
        v-for="lvl in levels"
        :key="lvl.level"
        class="flex-1 h-1.5 rounded-full transition-colors"
        :style="{
          backgroundColor: lvl.level <= props.status.level ? lvl.color : 'var(--bg-overlay)',
        }"
      />
    </div>

    <!-- Trigger info -->
    <div v-if="props.status.triggered_at" class="text-[11px] text-[var(--text-tertiary)] space-y-0.5">
      <p>触发时间: {{ formatDate(props.status.triggered_at) }}</p>
      <p v-if="props.status.trigger_value !== null">
        触发值: {{ (props.status.trigger_value * 100).toFixed(2) }}%
      </p>
    </div>
  </div>
</template>
