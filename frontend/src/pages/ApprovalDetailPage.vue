<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TagBadge from '@/components/ui/TagBadge.vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import WarningDialog from '@/components/ui/WarningDialog.vue'
import PortfolioSummary from '@/components/domain/PortfolioSummary.vue'
import { useApprovalDetail } from '@/composables/useApprovals'
import { approvalsApi } from '@/api/approvals'
import { formatDate, formatWeight, formatPercent, formatNumber } from '@/utils/formatters'
import { useQueryClient } from '@tanstack/vue-query'

const route = useRoute()
const router = useRouter()
const queryClient = useQueryClient()

const approvalId = computed(() => route.params.id as string)
const { data: approval, isLoading } = useApprovalDetail(approvalId)

const comment = ref('')
const reviewerName = ref('')

// Dialogs
const showApproveDialog = ref(false)
const showRejectDialog = ref(false)
const isProcessing = ref(false)

// Toast
const toast = ref<{ message: string; type: 'success' | 'error' } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(message: string, type: 'success' | 'error') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { message, type }
  toastTimer = setTimeout(() => { toast.value = null }, 3500)
}

// Modify weights — 两步流程
const showModifyWeights  = ref(false)
const modifyStep         = ref<'edit' | 'confirm'>('edit')
const modifiedWeights    = ref<Record<string, number>>({})
const modifyReviewerName = ref('')
const modifyComment      = ref('')

// 从风控配置读取单标的上限，默认 0.20
const maxPositionWeight = ref(0.20)
async function loadMaxPositionWeight() {
  try {
    const res = await fetch('/api/v1/risk/params')
    const data = await res.json()
    if (data?.max_position_weight) {
      maxPositionWeight.value = data.max_position_weight
    }
  } catch { /* 静默失败，使用默认值 */ }
}

function openModifyWeights() {
  if (!approval.value) return
  modifiedWeights.value = Object.fromEntries(
    approval.value.recommendations.map((r) => [r.symbol, r.recommended_weight])
  )
  modifyStep.value = 'edit'
  modifyReviewerName.value = ''
  modifyComment.value = ''
  showModifyWeights.value = true
  loadMaxPositionWeight()
}

const weightSum = computed(() =>
  Object.values(modifiedWeights.value).reduce((s, v) => s + (Number(v) || 0), 0)
)
const hasZeroWeight = computed(() =>
  Object.values(modifiedWeights.value).some((v) => Number(v) <= 0)
)
const weightMaxExceeded = computed(() =>
  Object.values(modifiedWeights.value).some((v) => Number(v) > maxPositionWeight.value)
)
const canSubmitModify = computed(
  () => !weightMaxExceeded.value && modifyReviewerName.value.trim().length > 0
)

const isPending = computed(() => approval.value?.status === 'pending')

const statusLabels: Record<string, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已拒绝',
  auto_approved: '自动通过',
  modified: '修改后批准',
}

async function handleApprove() {
  if (!reviewerName.value.trim()) {
    showToast('请输入操作人姓名', 'error')
    return
  }
  isProcessing.value = true
  try {
    await approvalsApi.processAction(approvalId.value, {
      action: 'approved',
      reviewed_by: reviewerName.value.trim(),
      comment: comment.value.trim() || undefined,
    })
    showApproveDialog.value = false
    queryClient.invalidateQueries({ queryKey: ['approval', approvalId.value] })
    queryClient.invalidateQueries({ queryKey: ['approvals'] })
    showToast('审批已通过', 'success')
    setTimeout(() => router.push('/approvals'), 1200)
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败，请重试', 'error')
  } finally {
    isProcessing.value = false
  }
}

async function handleReject() {
  if (!reviewerName.value.trim()) {
    showToast('请输入操作人姓名', 'error')
    return
  }
  isProcessing.value = true
  try {
    await approvalsApi.processAction(approvalId.value, {
      action: 'rejected',
      reviewed_by: reviewerName.value.trim(),
      comment: comment.value.trim() || undefined,
    })
    showRejectDialog.value = false
    queryClient.invalidateQueries({ queryKey: ['approval', approvalId.value] })
    queryClient.invalidateQueries({ queryKey: ['approvals'] })
    showToast('已拒绝该审批', 'success')
    setTimeout(() => router.push('/approvals'), 1200)
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败，请重试', 'error')
  } finally {
    isProcessing.value = false
  }
}

async function handleModifySubmit() {
  if (!modifyReviewerName.value.trim()) return
  isProcessing.value = true
  try {
    const weights: Record<string, number> = {}
    for (const [sym, val] of Object.entries(modifiedWeights.value)) {
      weights[sym] = Number(val)
    }
    await approvalsApi.modifyWeights(approvalId.value, {
      modified_weights: weights,
      reviewed_by: modifyReviewerName.value.trim(),
      comment: modifyComment.value.trim() || undefined,
    })
    showModifyWeights.value = false
    modifyStep.value = 'edit'
    queryClient.invalidateQueries({ queryKey: ['approval', approvalId.value] })
    queryClient.invalidateQueries({ queryKey: ['approvals'] })
    showToast('权重已修改并批准，持仓已同步更新', 'success')
    setTimeout(() => router.push('/approvals'), 1500)
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败，请重试', 'error')
  } finally {
    isProcessing.value = false
  }
}

function getDeltaColor(delta: number): string {
  if (delta > 0.005) return 'text-[var(--positive)]'
  if (delta < -0.005) return 'text-[var(--negative)]'
  return 'text-[var(--text-tertiary)]'
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

    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 mb-4 text-[12px]">
      <button class="text-[var(--brand-primary)] hover:underline" @click="router.push('/approvals')">
        审批列表
      </button>
      <span class="text-[var(--text-tertiary)]">/</span>
      <span class="text-[var(--text-secondary)]">审批详情</span>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="space-y-4">
      <div class="skeleton h-8 w-1/3 rounded" />
      <div class="skeleton h-64 rounded-lg" />
    </div>

    <template v-else-if="approval">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-6 flex-wrap">
        <h1 class="text-xl font-bold text-[var(--text-primary)]">审批详情</h1>
        <TagBadge
          :variant="approval.status"
          :label="statusLabels[approval.status] || approval.status"
        />
        <span class="text-[12px] text-[var(--text-tertiary)]">
          {{ formatDate(approval.created_at) }}
        </span>
        <!-- 决策链路入口 — 审批依据的核心 -->
        <div class="ml-auto">
          <button
            class="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-lg border border-[var(--brand-primary)] text-[var(--brand-primary)] hover:bg-[var(--brand-primary)]/10 transition-colors"
            @click="router.push(`/decisions/${approval.decision_run_id}`)"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            查看 Agent 分析链路
          </button>
        </div>
      </div>

      <!-- 决策依据提示 — 提醒审批者先看链路再决策 -->
      <div
        v-if="approval.status === 'pending'"
        class="mb-4 flex items-start gap-2 px-4 py-3 rounded-lg bg-[var(--brand-primary)]/8 border border-[var(--brand-primary)]/20 text-[12px]"
      >
        <svg class="w-4 h-4 text-[var(--brand-primary)] flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20A10 10 0 0012 2z" />
        </svg>
        <span class="text-[var(--text-secondary)]">
          建议审批前先
          <button
            class="text-[var(--brand-primary)] font-medium hover:underline"
            @click="router.push(`/decisions/${approval.decision_run_id}`)"
          >查看 Agent 完整分析链路</button>，
          了解技术面、基本面、新闻、情绪四个维度的具体依据后再做决策。
        </span>
      </div>

      <!-- Main layout -->
      <div class="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6 mb-6">
        <!-- Left: Recommendations table -->
        <div class="card p-4">
          <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-4">投资组合调整建议</h3>
          <div class="overflow-x-auto">
            <table class="w-full border-collapse text-[13px]">
              <thead>
                <tr class="border-b border-[var(--border-subtle)]">
                  <th class="px-3 py-2 text-left text-[11px] font-semibold text-[var(--text-secondary)] uppercase">标的</th>
                  <th class="px-3 py-2 text-right text-[11px] font-semibold text-[var(--text-secondary)] uppercase">当前权重</th>
                  <th class="px-3 py-2 text-right text-[11px] font-semibold text-[var(--text-secondary)] uppercase">建议权重</th>
                  <th class="px-3 py-2 text-right text-[11px] font-semibold text-[var(--text-secondary)] uppercase">变化量</th>
                  <th class="px-3 py-2 text-right text-[11px] font-semibold text-[var(--text-secondary)] uppercase">置信度</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="rec in approval.recommendations"
                  :key="rec.symbol"
                  class="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] transition-colors"
                >
                  <td class="px-3 py-2.5 font-medium text-[var(--text-primary)]">{{ rec.symbol }}</td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-[var(--text-secondary)]">{{ formatWeight(rec.current_weight) }}</td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-[var(--text-primary)] font-medium">{{ formatWeight(rec.recommended_weight) }}</td>
                  <td class="px-3 py-2.5 text-right tabular-nums font-medium" :class="getDeltaColor(rec.weight_delta)">
                    {{ formatPercent(rec.weight_delta) }}
                  </td>
                  <td class="px-3 py-2.5 text-right tabular-nums text-[var(--brand-secondary)]">{{ formatWeight(rec.confidence_score) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Right: Summary + Similar cases grouped by symbol -->
        <div class="space-y-4">
          <PortfolioSummary :recommendations="approval.recommendations" />

          <!-- Similar cases grouped by symbol -->
          <div class="card p-4">
            <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
              相似历史案例
            </h4>
            <div class="space-y-4">
              <template v-for="rec in approval.recommendations" :key="rec.symbol">
                <div v-if="rec.similar_cases?.length">
                  <p class="text-[11px] font-semibold text-[var(--text-secondary)] mb-2">{{ rec.symbol }}</p>
                  <div class="space-y-2">
                    <div
                      v-for="(sc, scIdx) in rec.similar_cases.slice(0, 3)"
                      :key="sc.node_id"
                      class="p-3 bg-[var(--bg-elevated)] rounded-lg"
                    >
                      <div class="flex items-center justify-between mb-1.5">
                        <span class="text-[11px] text-[var(--text-tertiary)]">#{{ scIdx + 1 }}</span>
                        <TagBadge
                          :variant="sc.approved ? 'approved' : 'rejected'"
                          :label="sc.approved ? '已通过' : '未通过'"
                          size="sm"
                        />
                      </div>
                      <div class="mb-1.5">
                        <div class="flex items-center justify-between text-[11px] mb-0.5">
                          <span class="text-[var(--text-tertiary)]">相似度</span>
                          <span class="text-[var(--brand-primary)] tabular-nums">{{ formatNumber(sc.similarity_score, 2) }}</span>
                        </div>
                        <div class="w-full h-1 bg-[var(--bg-overlay)] rounded-full">
                          <div
                            class="h-full bg-[var(--brand-primary)] rounded-full transition-all"
                            :style="{ width: `${sc.similarity_score * 100}%` }"
                          />
                        </div>
                      </div>
                      <div class="flex items-center justify-between text-[11px]">
                        <span class="text-[var(--text-tertiary)]">历史收益</span>
                        <span
                          class="tabular-nums font-medium"
                          :class="sc.outcome_return >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'"
                        >
                          {{ formatPercent(sc.outcome_return) }}
                        </span>
                      </div>
                      <div v-if="sc.outcome_sharpe !== undefined" class="flex items-center justify-between text-[11px] mt-0.5">
                        <span class="text-[var(--text-tertiary)]">历史 Sharpe</span>
                        <span class="tabular-nums text-[var(--text-secondary)]">{{ formatNumber(sc.outcome_sharpe, 2) }}</span>
                      </div>
                      <div v-if="sc.timestamp" class="text-[10px] text-[var(--text-tertiary)] mt-1">
                        {{ formatDate(sc.timestamp) }}
                      </div>
                    </div>
                  </div>
                </div>
              </template>
              <p
                v-if="!approval.recommendations.some((r) => r.similar_cases?.length)"
                class="text-[12px] text-[var(--text-tertiary)]"
              >
                暂无相似案例数据
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Modify weights panel — 两步流程：先调整，预览变化，再确认提交 -->
      <div v-if="showModifyWeights && isPending" class="card p-4 mb-6 border border-[var(--brand-primary)]/30">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">修改调仓权重</h3>
            <p class="text-[11px] text-[var(--text-tertiary)] mt-0.5">
              调整后点击「预览并确认」，再执行批准
            </p>
          </div>
          <button class="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]" @click="showModifyWeights = false; modifyStep = 'edit'">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Step 1: 编辑权重 -->
        <template v-if="modifyStep === 'edit'">
          <div class="space-y-3 mb-4">
            <div
              v-for="rec in approval.recommendations"
              :key="rec.symbol"
              class="grid grid-cols-[120px_1fr_120px_120px] gap-3 items-center"
            >
              <span class="text-[13px] font-medium text-[var(--text-primary)]">{{ rec.symbol }}</span>
              <div class="flex items-center gap-2">
                <input
                  v-model.number="modifiedWeights[rec.symbol]"
                  type="number"
                  min="0.001"
                  :max="maxPositionWeight"
                  step="0.01"
                  class="w-24 text-[13px]"
                  :class="{ 'border-[var(--negative)]': modifiedWeights[rec.symbol] > maxPositionWeight || modifiedWeights[rec.symbol] <= 0 }"
                />
                <span class="text-[11px] text-[var(--text-tertiary)]">
                  {{ ((modifiedWeights[rec.symbol] || 0) * 100).toFixed(1) }}%
                </span>
              </div>
              <span class="text-[12px] text-[var(--text-tertiary)]">
                原建议: {{ formatWeight(rec.recommended_weight) }}
              </span>
              <span class="text-[12px] tabular-nums" :class="(modifiedWeights[rec.symbol] || 0) > rec.recommended_weight ? 'text-[var(--positive)]' : (modifiedWeights[rec.symbol] || 0) < rec.recommended_weight ? 'text-[var(--negative)]' : 'text-[var(--text-tertiary)]'">
                {{ (modifiedWeights[rec.symbol] || 0) > rec.recommended_weight ? '+' : '' }}{{ (((modifiedWeights[rec.symbol] || 0) - rec.recommended_weight) * 100).toFixed(1) }}%
              </span>
            </div>
          </div>

          <!-- 校验提示 -->
          <div class="text-[12px] mb-4 space-y-1">
            <div v-if="weightMaxExceeded" class="flex items-center gap-1 text-[var(--negative)]">
              <span>⚠</span>
              <span>单标的上限为 {{ (maxPositionWeight * 100).toFixed(0) }}%，请降低权重</span>
            </div>
            <div v-else-if="hasZeroWeight" class="flex items-center gap-1 text-[var(--negative)]">
              <span>⚠</span>
              <span>权重必须大于 0%。如需清仓请填写 0 后确认</span>
            </div>
            <div v-else class="text-[var(--text-tertiary)]">
              单标的上限：{{ (maxPositionWeight * 100).toFixed(0) }}%
            </div>
          </div>

          <ActionButton
            variant="primary"
            :disabled="weightMaxExceeded"
            @click="modifyStep = 'confirm'"
          >
            预览变化 →
          </ActionButton>
        </template>

        <!-- Step 2: 确认预览 + 填写操作人 -->
        <template v-else-if="modifyStep === 'confirm'">
          <div class="mb-4 p-3 bg-[var(--bg-elevated)] rounded-lg">
            <p class="text-[12px] font-medium text-[var(--text-secondary)] mb-2">调仓变化确认：</p>
            <div class="space-y-2">
              <div v-for="rec in approval.recommendations" :key="rec.symbol"
                class="flex items-center justify-between text-[13px]">
                <span class="font-medium">{{ rec.symbol }}</span>
                <div class="flex items-center gap-2">
                  <span class="text-[var(--text-tertiary)]">原建议 {{ formatWeight(rec.recommended_weight) }}</span>
                  <span class="text-[var(--text-tertiary)]">→</span>
                  <span class="font-semibold" :class="(modifiedWeights[rec.symbol] || 0) !== rec.recommended_weight ? 'text-[var(--brand-primary)]' : ''">
                    {{ formatWeight(modifiedWeights[rec.symbol] || 0) }}
                  </span>
                  <span class="text-[11px] tabular-nums" :class="(modifiedWeights[rec.symbol] || 0) > rec.recommended_weight ? 'text-[var(--positive)]' : (modifiedWeights[rec.symbol] || 0) < rec.recommended_weight ? 'text-[var(--negative)]' : 'text-[var(--text-tertiary)]'">
                    （{{ (modifiedWeights[rec.symbol] || 0) > rec.recommended_weight ? '+' : '' }}{{ (((modifiedWeights[rec.symbol] || 0) - rec.recommended_weight) * 100).toFixed(1) }}%）
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- 操作人（在确认步骤填写，不依赖底部字段） -->
          <div class="mb-4">
            <label class="block text-[12px] text-[var(--text-secondary)] mb-1">操作人 <span class="text-[var(--negative)]">*</span></label>
            <input
              v-model="modifyReviewerName"
              type="text"
              placeholder="请输入您的姓名"
              class="w-full text-[13px]"
            />
          </div>
          <div class="mb-4">
            <label class="block text-[12px] text-[var(--text-secondary)] mb-1">修改原因（可选）</label>
            <input
              v-model="modifyComment"
              type="text"
              placeholder="说明调整原因..."
              class="w-full text-[13px]"
            />
          </div>

          <div class="flex items-center gap-3">
            <ActionButton variant="outline" @click="modifyStep = 'edit'">← 返回修改</ActionButton>
            <ActionButton
              variant="primary"
              :disabled="!modifyReviewerName.trim()"
              :loading="isProcessing"
              @click="handleModifySubmit"
            >
              确认修改并批准
            </ActionButton>
          </div>
        </template>
      </div>

      <!-- Bottom: Approval actions -->
      <div class="card p-4">
        <template v-if="isPending">
          <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-4">审批操作</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">操作人</label>
              <input v-model="reviewerName" type="text" placeholder="请输入您的姓名" />
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">审批备注（可选）</label>
              <input v-model="comment" type="text" placeholder="填写审批备注..." />
            </div>
          </div>
          <div class="flex items-center gap-3">
            <ActionButton variant="success" size="lg" @click="showApproveDialog = true">
              批准
            </ActionButton>
            <ActionButton variant="outline" size="lg" @click="openModifyWeights">
              修改权重
            </ActionButton>
            <ActionButton variant="danger" size="lg" @click="showRejectDialog = true">
              拒绝
            </ActionButton>
          </div>
        </template>
        <template v-else>
          <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-2">审批结果</h3>
          <div class="text-[13px] text-[var(--text-secondary)] space-y-1">
            <p>状态: <TagBadge :variant="approval.status" :label="statusLabels[approval.status]" size="sm" /></p>
            <p v-if="approval.reviewed_by">审批人: {{ approval.reviewed_by }}</p>
            <p v-if="approval.reviewed_at">审批时间: {{ formatDate(approval.reviewed_at) }}</p>
            <p v-if="approval.comment">备注: {{ approval.comment }}</p>
          </div>
        </template>
      </div>
    </template>

    <!-- Not found -->
    <div v-else class="text-center py-20">
      <p class="text-[var(--text-tertiary)]">审批记录不存在</p>
    </div>

    <!-- Dialogs -->
    <ConfirmDialog
      :visible="showApproveDialog"
      @update:visible="showApproveDialog = $event"
      title="确认批准"
      message="确认要批准此投资组合调整建议吗？批准后将写入经验图谱。"
      confirm-text="批准"
      :loading="isProcessing"
      @confirm="handleApprove"
    />

    <WarningDialog
      :visible="showRejectDialog"
      @update:visible="showRejectDialog = $event"
      title="确认拒绝"
      message="确认要拒绝此投资组合调整建议吗？此操作不可逆。"
      confirm-text="拒绝"
      :loading="isProcessing"
      @confirm="handleReject"
    />
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