<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import StatusCard from '@/components/ui/StatusCard.vue'
import DataTable from '@/components/ui/DataTable.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useApprovals } from '@/composables/useApprovals'
import type { ApprovalStatus } from '@/types/approval'
import { formatRelativeTime, formatWeight } from '@/utils/formatters'
import { approvalsApi } from '@/api/approvals'
import { useQueryClient } from '@tanstack/vue-query'

const router = useRouter()
const queryClient = useQueryClient()

const statusFilter = ref<string | undefined>(undefined)
const currentPage = ref(1)
const pageSize = 20

const queryParams = computed(() => ({
  status: statusFilter.value,
  page: currentPage.value,
  page_size: pageSize,
}))

const { data, isLoading, processAction, isPending } = useApprovals(queryParams)

const items = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)
const totalPages = computed(() => Math.ceil(total.value / pageSize))

// Toast
const toast = ref<{ message: string; type: 'success' | 'error' } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(message: string, type: 'success' | 'error') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { message, type }
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
}

// Quick action dialog
const showConfirm = ref(false)
const confirmAction = ref<'approved' | 'rejected'>('approved')
const confirmId = ref('')

function handleQuickApprove(id: string) {
  confirmId.value = id
  confirmAction.value = 'approved'
  showConfirm.value = true
}

function handleQuickReject(id: string) {
  confirmId.value = id
  confirmAction.value = 'rejected'
  showConfirm.value = true
}

async function handleConfirm() {
  try {
    await processAction({
      id: confirmId.value,
      payload: {
        action: confirmAction.value,
        reviewed_by: 'admin',
      },
    })
    showConfirm.value = false
    showToast(confirmAction.value === 'approved' ? '审批已通过' : '已拒绝该审批', 'success')
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败，请重试', 'error')
  }
}

const statusOptions = [
  { value: undefined, label: '全部' },
  { value: 'pending', label: '待审批' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已拒绝' },
  { value: 'auto_approved', label: '自动通过' },
]

const statusLabels: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已拒绝',
  auto_approved: '自动通过',
  modified: '修改后批准',
}

function getStatusVariant(status: ApprovalStatus): ApprovalStatus {
  return status
}

const tableColumns = [
  { key: 'checkbox', label: '', width: '40px' },
  { key: 'created_at', label: '时间', width: '140px' },
  { key: 'symbols', label: '涉及标的' },
  { key: 'max_delta', label: '最大调仓', width: '100px', align: 'right' as const },
  { key: 'status', label: '状态', width: '100px', align: 'center' as const },
  { key: 'chain', label: '分析链路', width: '90px', align: 'center' as const },
  { key: 'actions', label: '操作', width: '160px', align: 'center' as const },
]

const tableData = computed(() =>
  items.value.map((item) => ({
    ...item,
    symbols: item.recommendations.map((r) => r.symbol).join(', '),
    max_delta: item.recommendations.length
      ? Math.max(...item.recommendations.map((r) => Math.abs(r.weight_delta)))
      : 0,
  }))
)

// ── 多选逻辑 ─────────────────────────────────────────────────────────────────
const selectedIds = ref<Set<string>>(new Set())

const pendingItems = computed(() =>
  tableData.value.filter((row) => row.status === 'pending')
)

const allPendingSelected = computed(() => {
  if (pendingItems.value.length === 0) return false
  return pendingItems.value.every((row) => selectedIds.value.has(row.id as string))
})

function toggleSelectAll() {
  if (allPendingSelected.value) {
    pendingItems.value.forEach((row) => selectedIds.value.delete(row.id as string))
  } else {
    pendingItems.value.forEach((row) => selectedIds.value.add(row.id as string))
  }
  // trigger reactivity
  selectedIds.value = new Set(selectedIds.value)
}

function toggleSelect(id: string) {
  if (selectedIds.value.has(id)) {
    selectedIds.value.delete(id)
  } else {
    selectedIds.value.add(id)
  }
  selectedIds.value = new Set(selectedIds.value)
}

function clearSelection() {
  selectedIds.value = new Set()
}

// ── 批量拒绝弹窗 ─────────────────────────────────────────────────────────────
const showBatchDialog = ref(false)
const batchReviewer = ref('')
const batchComment = ref('')
const isBatchPending = ref(false)

function openBatchReject() {
  batchReviewer.value = ''
  batchComment.value = ''
  showBatchDialog.value = true
}

async function handleBatchReject() {
  if (!batchReviewer.value.trim()) return
  isBatchPending.value = true
  try {
    const res = await approvalsApi.batchAction({
      approval_ids: Array.from(selectedIds.value),
      action: 'rejected',
      reviewed_by: batchReviewer.value.trim(),
      comment: batchComment.value.trim() || undefined,
    })
    showBatchDialog.value = false
    clearSelection()
    showToast(
      `已拒绝 ${res.success_count} 条${res.fail_count > 0 ? `，${res.fail_count} 条操作失败` : ''}`,
      res.fail_count > 0 ? 'error' : 'success'
    )
    queryClient.invalidateQueries({ queryKey: ['approvals'] })
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '批量操作失败', 'error')
  } finally {
    isBatchPending.value = false
  }
}
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toast"
        class="fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-[13px] font-medium"
        :class="toast.type === 'success' ? 'bg-[var(--positive)] text-white' : 'bg-[var(--negative)] text-white'"
      >
        {{ toast.message }}
      </div>
    </Transition>

    <!-- Header -->
    <div class="mb-6">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">审批列表</h1>
    </div>

    <!-- Stat cards -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      <StatusCard title="待审批" :value="data?.total ?? '--'" />
      <StatusCard title="当前页" :value="`${currentPage} / ${totalPages || 1}`" />
      <StatusCard title="总记录" :value="total" />
    </div>

    <!-- Filter bar -->
    <div class="flex items-center gap-2 mb-4">
      <button
        v-for="opt in statusOptions"
        :key="String(opt.value)"
        class="px-3 py-1.5 text-[12px] font-medium rounded-full transition-colors"
        :class="[
          statusFilter === opt.value
            ? 'bg-[var(--brand-primary)] text-white'
            : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]',
        ]"
        @click="statusFilter = opt.value; currentPage = 1; clearSelection()"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- 批量操作栏 -->
    <Transition name="toast">
      <div
        v-if="selectedIds.size > 0"
        class="flex items-center gap-3 mb-3 px-4 py-2.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)]"
      >
        <span class="text-[13px] text-[var(--text-secondary)]">已选 {{ selectedIds.size }} 条</span>
        <ActionButton variant="danger" size="sm" @click="openBatchReject">批量拒绝</ActionButton>
        <ActionButton variant="ghost" size="sm" @click="clearSelection">取消选择</ActionButton>
      </div>
    </Transition>

    <!-- Table -->
    <DataTable
      :columns="tableColumns"
      :data="tableData"
      :loading="isLoading"
      empty-text="暂无审批记录"
    >
      <template #header-checkbox>
        <input
          type="checkbox"
          class="cursor-pointer"
          :checked="allPendingSelected"
          :indeterminate="selectedIds.size > 0 && !allPendingSelected"
          @change="toggleSelectAll"
          title="全选当前页待审批"
        />
      </template>
      <template #empty>
        <div class="flex flex-col items-center justify-center py-10 gap-2">
          <p class="text-[var(--text-tertiary)] text-sm">暂无审批记录</p>
          <p class="text-[var(--text-tertiary)] text-[12px]">前往 Dashboard 触发 Agent 决策，决策完成后会出现在这里等待审批</p>
          <button
            class="mt-1 text-[13px] text-[var(--brand-primary)] hover:underline"
            @click="router.push('/')"
          >
            前往 Dashboard
          </button>
        </div>
      </template>
      <template #cell-checkbox="{ row }">
        <input
          v-if="row.status === 'pending'"
          type="checkbox"
          class="cursor-pointer"
          :checked="selectedIds.has(row.id as string)"
          @change="toggleSelect(row.id as string)"
        />
      </template>
      <template #cell-created_at="{ row }">
        <span class="text-[12px] tabular-nums text-[var(--text-secondary)]">
          {{ formatRelativeTime(row.created_at as string) }}
        </span>
      </template>
      <template #cell-symbols="{ row }">
        <span class="text-[13px] truncate block max-w-[240px]">{{ row.symbols }}</span>
      </template>
      <template #cell-max_delta="{ row }">
        <span class="tabular-nums">{{ formatWeight(row.max_delta as number) }}</span>
      </template>
      <template #cell-status="{ row }">
        <TagBadge
          :variant="getStatusVariant(row.status as ApprovalStatus)"
          :label="statusLabels[row.status as string] || (row.status as string)"
          size="sm"
        />
      </template>
      <template #cell-chain="{ row }">
        <button
          class="text-[12px] text-[var(--brand-primary)] hover:underline whitespace-nowrap"
          @click="router.push(`/decisions/${row.decision_run_id}`)"
          title="查看 Agent 分析链路"
        >
          查看链路
        </button>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex items-center justify-center gap-1">
          <ActionButton variant="ghost" size="sm" @click="router.push(`/approvals/${row.id}`)">
            详情
          </ActionButton>
          <template v-if="row.status === 'pending'">
            <ActionButton variant="success" size="sm" @click="handleQuickApprove(row.id as string)">
              通过
            </ActionButton>
            <ActionButton variant="danger" size="sm" @click="handleQuickReject(row.id as string)">
              拒绝
            </ActionButton>
          </template>
        </div>
      </template>
    </DataTable>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-center gap-2 mt-4">
      <ActionButton
        variant="outline"
        size="sm"
        :disabled="currentPage <= 1"
        @click="currentPage--"
      >
        上一页
      </ActionButton>
      <span class="text-[12px] text-[var(--text-secondary)] tabular-nums px-3">
        {{ currentPage }} / {{ totalPages }}
      </span>
      <ActionButton
        variant="outline"
        size="sm"
        :disabled="currentPage >= totalPages"
        @click="currentPage++"
      >
        下一页
      </ActionButton>
    </div>

    <!-- 单条操作确认弹窗 -->
    <ConfirmDialog
      :visible="showConfirm"
      @update:visible="showConfirm = $event"
      :title="confirmAction === 'approved' ? '确认通过' : '确认拒绝'"
      :message="confirmAction === 'approved' ? '确认要通过此审批吗？' : '确认要拒绝此审批吗？此操作不可逆。'"
      :variant="confirmAction === 'approved' ? 'default' : 'danger'"
      :confirm-text="confirmAction === 'approved' ? '通过' : '拒绝'"
      :loading="isPending"
      @confirm="handleConfirm"
    />

    <!-- 批量拒绝弹窗 -->
    <div
      v-if="showBatchDialog"
      class="fixed inset-0 z-40 flex items-center justify-center bg-black/40"
      @click.self="showBatchDialog = false"
    >
      <div class="card p-6 w-full max-w-sm mx-4">
        <h3 class="text-base font-semibold mb-1 text-[var(--text-primary)]">批量拒绝确认</h3>
        <p class="text-[12px] text-[var(--text-tertiary)] mb-4">共 {{ selectedIds.size }} 条待审批记录将被拒绝，此操作不可逆。</p>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">操作人 <span class="text-[var(--negative)]">*</span></label>
            <input
              v-model="batchReviewer"
              placeholder="请输入操作人"
              class="w-full"
            />
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">拒绝原因（可选）</label>
            <input
              v-model="batchComment"
              placeholder="如：批量清理历史遗留"
              class="w-full"
            />
          </div>
        </div>
        <div class="flex gap-3 mt-5">
          <ActionButton
            variant="danger"
            class="flex-1"
            :loading="isBatchPending"
            :disabled="!batchReviewer.trim()"
            @click="handleBatchReject"
          >
            确认拒绝
          </ActionButton>
          <ActionButton variant="outline" @click="showBatchDialog = false">取消</ActionButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
