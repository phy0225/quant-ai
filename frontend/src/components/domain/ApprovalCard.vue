<script setup lang="ts">
import { computed } from 'vue'
import type { ApprovalRecord } from '@/types/approval'
import TagBadge from '@/components/ui/TagBadge.vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import { formatRelativeTime, formatWeight } from '@/utils/formatters'

interface Props {
  approval: ApprovalRecord
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'view-detail': [id: string]
  'quick-approve': [id: string]
  'quick-reject': [id: string]
}>()

const statusLabels: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已拒绝',
  auto_approved: '自动通过',
}

const maxDelta = computed(() => {
  if (!props.approval.recommendations.length) return 0
  return Math.max(...props.approval.recommendations.map(r => Math.abs(r.weight_delta)))
})

const symbolCount = computed(() => props.approval.recommendations.length)

const isPending = computed(() => props.approval.status === 'pending')
</script>

<template>
  <div class="card p-4 hover:shadow-[var(--shadow-card-hover)] transition-shadow">
    <div class="flex items-start justify-between gap-3 mb-3">
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 mb-1">
          <TagBadge :variant="props.approval.status" :label="statusLabels[props.approval.status] || props.approval.status" size="sm" />
          <span class="text-[11px] text-[var(--text-tertiary)]">
            {{ formatRelativeTime(props.approval.created_at) }}
          </span>
        </div>
        <p class="text-[13px] text-[var(--text-primary)]">
          {{ symbolCount }} 标的调仓 | 最大幅度 {{ formatWeight(maxDelta) }}
        </p>
      </div>
    </div>

    <!-- Symbol chips -->
    <div class="flex flex-wrap gap-1 mb-3">
      <span
        v-for="rec in props.approval.recommendations.slice(0, 5)"
        :key="rec.symbol"
        class="inline-block px-1.5 py-0.5 text-[11px] bg-[var(--bg-elevated)] text-[var(--text-secondary)] rounded"
      >
        {{ rec.symbol }}
      </span>
      <span
        v-if="props.approval.recommendations.length > 5"
        class="inline-block px-1.5 py-0.5 text-[11px] bg-[var(--bg-overlay)] text-[var(--text-tertiary)] rounded"
      >
        +{{ props.approval.recommendations.length - 5 }}
      </span>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2">
      <ActionButton variant="ghost" size="sm" @click="emit('view-detail', props.approval.id)">
        详情
      </ActionButton>
      <template v-if="isPending">
        <ActionButton variant="success" size="sm" @click="emit('quick-approve', props.approval.id)">
          通过
        </ActionButton>
        <ActionButton variant="danger" size="sm" @click="emit('quick-reject', props.approval.id)">
          拒绝
        </ActionButton>
      </template>
    </div>
  </div>
</template>
