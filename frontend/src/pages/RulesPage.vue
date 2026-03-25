<script setup lang="ts">
import { ref, computed } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import ActionButton from '@/components/ui/ActionButton.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import EmergencyDialog from '@/components/ui/EmergencyDialog.vue'
import ResetCircuitBreakerDialog from '@/components/ui/ResetCircuitBreakerDialog.vue'
import CircuitBreakerStatusComp from '@/components/domain/CircuitBreakerStatus.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import { rulesApi } from '@/api/rules'
import { riskApi } from '@/api/risk'
import { useEmergencyStore } from '@/store/emergency'
import { formatDate, formatRelativeTime } from '@/utils/formatters'
import type { AutoApprovalRule, RuleCondition, RiskParams } from '@/types/risk'

const queryClient = useQueryClient()
const emergencyStore = useEmergencyStore()

// ── Auto-approval rules ─────────────────────────────────────
const { data: rules, isLoading } = useQuery({
  queryKey: ['rules'],
  queryFn: () => rulesApi.list(),
})

// ── Risk status ─────────────────────────────────────────────
const { data: riskStatus } = useQuery({
  queryKey: ['risk-status'],
  queryFn: () => riskApi.getStatus(),
  refetchInterval: 10_000,
})

// ── Risk params ─────────────────────────────────────────────
const { data: riskParams, isLoading: isLoadingParams } = useQuery({
  queryKey: ['risk-params'],
  queryFn: () => riskApi.getRiskParams(),
})

const { data: riskEvents } = useQuery({
  queryKey: ['risk-events'],
  queryFn: () => riskApi.listEvents({ limit: 10 }),
})

// ── Mutations ───────────────────────────────────────────────
const toggleMutation = useMutation({
  mutationFn: (id: string) => rulesApi.toggle(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }),
})

const deleteMutation = useMutation({
  mutationFn: (id: string) => rulesApi.delete(id),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }),
})

const createMutation = useMutation({
  mutationFn: (payload: Parameters<typeof rulesApi.create>[0]) => rulesApi.create(payload),
  onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); showForm.value = false; resetForm() },
})

const updateMutation = useMutation({
  mutationFn: ({ id, payload }: { id: string; payload: Partial<AutoApprovalRule> }) => rulesApi.update(id, payload),
  onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); showForm.value = false; resetForm() },
})

const updateParamsMutation = useMutation({
  mutationFn: (payload: Partial<RiskParams>) => riskApi.updateRiskParams(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['risk-params'] })
    showParamsForm.value = false
    showParamsToast.value = true
    setTimeout(() => { showParamsToast.value = false }, 2500)
  },
})

const resetCircuitBreakerMutation = useMutation({
  mutationFn: ({ target_level, authorized_by }: { target_level: number; authorized_by: string }) =>
    riskApi.resetCircuitBreaker(target_level, authorized_by),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['risk-status'] })
    showResetDialog.value = false
  },
})

// ── Toast ────────────────────────────────────────────────────
const showParamsToast = ref(false)

// ── Risk params form ─────────────────────────────────────────
const showParamsForm = ref(false)
const paramsForm = ref<RiskParams>({
  max_position_weight: 0.20,
  daily_loss_warning_threshold: 0.03,
  daily_loss_suspend_threshold: 0.06,
  max_drawdown_emergency: 0.15,
})

function openParamsForm() {
  if (riskParams.value) {
    paramsForm.value = { ...riskParams.value }
  }
  showParamsForm.value = true
}

function submitParams() {
  updateParamsMutation.mutate(paramsForm.value)
}

// ── Circuit breaker reset ─────────────────────────────────────
const showResetDialog = ref(false)

// ── Rule form ─────────────────────────────────────────────────
const showForm = ref(false)
const editingRule = ref<AutoApprovalRule | null>(null)
const formName = ref('')
const formDescription = ref('')
const formPriority = ref(0)
const formLogicOp = ref<'AND' | 'OR'>('AND')
const formConditions = ref<RuleCondition[]>([{ field: 'max_weight_delta', operator: 'lte', value: 0.05 }])

const showDeleteConfirm = ref(false)
const deleteTargetId = ref('')
const showEmergencyDialog = ref(false)
const isActivatingEmergency = ref(false)

const fieldLabels: Record<string, string> = {
  max_weight_delta: '最大单标的权重变化',
  min_confidence_score: 'Agent 最低置信度',
  max_position_weight: '最大单标的建议权重',
  affected_symbols_count: '涉及调仓标的数量',
  total_turnover: '总换手率',
}

const operatorLabels: Record<string, string> = {
  lte: '<=', gte: '>=', lt: '<', gt: '>', eq: '=',
}

const ruleTemplates = [
  { name: '小幅调仓自动批准', description: '调仓幅度小且置信度较高时自动批准', priority: 10, logic_operator: 'AND' as const,
    conditions: [{ field: 'max_weight_delta', operator: 'lte', value: 0.05 }, { field: 'min_confidence_score', operator: 'gte', value: 0.6 }] },
  { name: '高置信度自动批准', description: 'Agent 置信度极高时自动批准', priority: 20, logic_operator: 'AND' as const,
    conditions: [{ field: 'min_confidence_score', operator: 'gte', value: 0.8 }] },
  { name: '保守模式', description: '仅允许极小幅度调仓且单标的不超过 30%', priority: 5, logic_operator: 'AND' as const,
    conditions: [{ field: 'max_weight_delta', operator: 'lte', value: 0.02 }, { field: 'max_position_weight', operator: 'lte', value: 0.3 }] },
]

function applyTemplate(tpl: typeof ruleTemplates[0]) {
  resetForm()
  formName.value = tpl.name
  formDescription.value = tpl.description
  formPriority.value = tpl.priority
  formLogicOp.value = tpl.logic_operator
  formConditions.value = tpl.conditions.map(c => ({ ...c }))
  showForm.value = true
}

// ── BUG FIX: function declaration was missing ────────────────
function resetForm() {
  editingRule.value = null
  formName.value = ''
  formDescription.value = ''
  formPriority.value = 0
  formLogicOp.value = 'AND'
  formConditions.value = [{ field: 'max_weight_delta', operator: 'lte', value: 0.05 }]
}

function startCreate() { resetForm(); showForm.value = true }

function startEdit(rule: AutoApprovalRule) {
  editingRule.value = rule
  formName.value = rule.name
  formDescription.value = rule.description || ''
  formPriority.value = rule.priority
  formLogicOp.value = rule.logic_operator
  formConditions.value = [...rule.conditions]
  showForm.value = true
}

function addCondition() { if (formConditions.value.length < 10) formConditions.value.push({ field: 'max_weight_delta', operator: 'lte', value: 0 }) }
function removeCondition(index: number) { if (formConditions.value.length > 1) formConditions.value.splice(index, 1) }

const canSubmitForm = computed(() => formName.value.trim().length > 0 && formConditions.value.length > 0)

function submitForm() {
  const payload = {
    name: formName.value.trim(), description: formDescription.value.trim() || null,
    priority: formPriority.value, logic_operator: formLogicOp.value, conditions: formConditions.value, is_active: true,
  }
  if (editingRule.value) {
    updateMutation.mutate({ id: editingRule.value.id, payload })
  } else {
    createMutation.mutate(payload)
  }
}

function confirmDelete(id: string) { deleteTargetId.value = id; showDeleteConfirm.value = true }
function handleDelete() { deleteMutation.mutate(deleteTargetId.value); showDeleteConfirm.value = false }

async function handleEmergencyActivate(data: { reason: string; activated_by: string }) {
  isActivatingEmergency.value = true
  try {
    await riskApi.activateEmergencyStop(data)
    emergencyStore.activateEmergencyStop(data.activated_by)
    showEmergencyDialog.value = false
  } catch { alert('激活失败，请重试') } finally { isActivatingEmergency.value = false }
}

const riskParamConfig = computed(() => [
  {
    key: 'max_position_weight' as keyof RiskParams,
    label: '单标的仓位上限',
    value: riskParams.value?.max_position_weight,
    consequence: '超出时拒绝执行',
    level: 'L1',
    fmt: (v: number) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: 'daily_loss_warning_threshold' as keyof RiskParams,
    label: '日内净值下跌警告线',
    value: riskParams.value?.daily_loss_warning_threshold,
    consequence: '触发 L1 警告',
    level: 'L1',
    fmt: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: 'daily_loss_suspend_threshold' as keyof RiskParams,
    label: '日内净值下跌暂停线',
    value: riskParams.value?.daily_loss_suspend_threshold,
    consequence: '触发 L2 暂停（须人工解除）',
    level: 'L2',
    fmt: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: 'max_drawdown_emergency' as keyof RiskParams,
    label: '最大回撤紧急停止线',
    value: riskParams.value?.max_drawdown_emergency,
    consequence: '触发 L3 紧急熔断',
    level: 'L3',
    fmt: (v: number) => `${(v * 100).toFixed(1)}%`,
  },
])
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <!-- Toast -->
    <Transition name="toast">
      <div v-if="showParamsToast" class="fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-[13px] font-medium bg-[var(--positive)] text-white">
        风控参数已更新
      </div>
    </Transition>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold text-[var(--text-primary)]">规则配置</h1>
        <div v-if="riskStatus">
          <CircuitBreakerStatusComp
            :status="riskStatus.circuit_breaker"
            @reset="showResetDialog = true"
          />
        </div>
      </div>
      <ActionButton variant="danger" @click="showEmergencyDialog = true">紧急停止</ActionButton>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-[1fr_420px] gap-6">
      <div class="space-y-6">

        <!-- ── Section 1: Hard risk params ── -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <div>
              <h2 class="text-sm font-semibold text-[var(--text-primary)]">硬性风控参数</h2>
              <p class="text-[11px] text-[var(--text-tertiary)] mt-0.5">
                由代码规则强制执行，优先级高于所有 Agent 信号，修改后立即生效。
              </p>
            </div>
            <ActionButton variant="outline" size="sm" @click="openParamsForm">编辑参数</ActionButton>
          </div>

          <div v-if="isLoadingParams" class="space-y-2">
            <div v-for="i in 4" :key="i" class="skeleton h-16 rounded-lg" />
          </div>

          <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div
              v-for="cfg in riskParamConfig"
              :key="cfg.key"
              class="card p-3"
            >
              <div class="flex items-start justify-between mb-1">
                <p class="text-[12px] font-medium text-[var(--text-primary)]">{{ cfg.label }}</p>
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded"
                  :class="cfg.level === 'L3' ? 'bg-[var(--negative)]/15 text-[var(--negative)]'
                    : cfg.level === 'L2' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                    : 'bg-[var(--warning)]/15 text-[var(--warning)]'"
                >
                  {{ cfg.level }}
                </span>
              </div>
              <p class="text-xl font-bold tabular-nums text-[var(--brand-primary)] mb-0.5">
                {{ cfg.value != null ? cfg.fmt(cfg.value) : '—' }}
              </p>
              <p class="text-[11px] text-[var(--text-tertiary)]">{{ cfg.consequence }}</p>
            </div>
          </div>
        </div>

        <!-- ── Section 2: Auto-approval rules ── -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <div>
              <h2 class="text-sm font-semibold text-[var(--text-primary)]">自动审批规则</h2>
              <p class="text-[11px] text-[var(--text-tertiary)] mt-0.5">
                满足条件的 Agent 决策将跳过人工审批自动通过，与上方硬性风控参数相互独立。
              </p>
            </div>
            <ActionButton variant="primary" size="sm" @click="startCreate">新增规则</ActionButton>
          </div>

          <div v-if="isLoading" class="space-y-3 mt-3">
            <div v-for="i in 3" :key="i" class="skeleton h-20 rounded-lg" />
          </div>

          <div v-else-if="!rules?.length" class="card p-8 text-center mt-3">
            <p class="text-[var(--text-tertiary)] text-sm mb-1">暂无自动审批规则</p>
            <p class="text-[var(--text-tertiary)] text-[12px] mb-3">创建规则，满足条件的决策将跳过人工审批</p>
            <div class="flex flex-wrap justify-center gap-2 mb-4">
              <button
                v-for="tpl in ruleTemplates"
                :key="tpl.name"
                class="px-3 py-1.5 text-[12px] rounded-lg border border-[var(--border-default)] text-[var(--text-secondary)] hover:border-[var(--brand-primary)] hover:text-[var(--brand-primary)] transition-colors"
                @click="applyTemplate(tpl)"
              >
                {{ tpl.name }}
              </button>
            </div>
          </div>

          <div v-else class="space-y-3 mt-3">
            <div v-for="rule in rules" :key="rule.id" class="card p-4 hover:shadow-[var(--shadow-card-hover)] transition-shadow">
              <div class="flex items-start justify-between gap-3 mb-2">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2 mb-0.5">
                    <h3 class="text-[14px] font-medium text-[var(--text-primary)]">{{ rule.name }}</h3>
                    <TagBadge :variant="rule.is_active ? 'success' : 'info'" :label="rule.is_active ? '启用' : '禁用'" size="sm" />
                    <span class="text-[11px] text-[var(--text-tertiary)] tabular-nums">P{{ rule.priority }}</span>
                  </div>
                  <p v-if="rule.description" class="text-[12px] text-[var(--text-secondary)] truncate">{{ rule.description }}</p>
                </div>
              </div>
              <div class="flex flex-wrap gap-1 mb-2">
                <span
                  v-for="(cond, idx) in rule.conditions"
                  :key="idx"
                  class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] bg-[var(--bg-elevated)] rounded text-[var(--text-secondary)]"
                >
                  {{ fieldLabels[cond.field] || cond.field }} {{ operatorLabels[cond.operator] || cond.operator }} {{ cond.value }}
                  <span v-if="idx < rule.conditions.length - 1" class="text-[var(--brand-primary)] font-semibold">{{ rule.logic_operator }}</span>
                </span>
              </div>
              <div class="flex items-center justify-between text-[11px] text-[var(--text-tertiary)]">
                <span>触发 {{ rule.trigger_count }} 次 <template v-if="rule.last_triggered_at">| 最近 {{ formatRelativeTime(rule.last_triggered_at) }}</template></span>
                <div class="flex items-center gap-1">
                  <ActionButton :variant="rule.is_active ? 'ghost' : 'outline'" size="sm" @click="toggleMutation.mutate(rule.id)">
                    {{ rule.is_active ? '禁用' : '启用' }}
                  </ActionButton>
                  <ActionButton variant="ghost" size="sm" @click="startEdit(rule)">编辑</ActionButton>
                  <ActionButton variant="ghost" size="sm" @click="confirmDelete(rule.id)">删除</ActionButton>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Risk events -->
        <div>
          <h2 class="text-sm font-semibold text-[var(--text-primary)] mb-3">最近风险事件</h2>
          <div v-if="riskEvents?.length" class="space-y-2">
            <div
              v-for="event in riskEvents.slice(0, 10)"
              :key="event.id"
              class="flex items-start gap-2 p-2.5 bg-[var(--bg-surface)] rounded-lg border border-[var(--border-subtle)] text-[12px]"
            >
              <span class="mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0"
                :class="{ 'bg-[var(--warning)]': event.severity === 'warning', 'bg-[var(--negative)]': event.severity === 'critical' || event.severity === 'emergency' }" />
              <div class="min-w-0 flex-1">
                <p class="text-[var(--text-primary)]">{{ event.description }}</p>
                <p class="text-[var(--text-tertiary)] text-[11px] mt-0.5">{{ formatDate(event.created_at) }}</p>
              </div>
            </div>
          </div>
          <p v-else class="text-[12px] text-[var(--text-tertiary)]">暂无风险事件</p>
        </div>
      </div>

      <!-- Right: Forms panel -->
      <div class="space-y-4">
        <!-- Risk params edit form -->
        <div v-if="showParamsForm" class="card p-5 self-start">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">编辑硬性风控参数</h3>
            <button class="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]" @click="showParamsForm = false">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <div class="space-y-3">
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">单标的仓位上限（0.05 ~ 0.50）</label>
              <input v-model.number="paramsForm.max_position_weight" type="number" min="0.05" max="0.5" step="0.01" />
              <p class="text-[10px] text-[var(--text-tertiary)] mt-0.5">当前: {{ (paramsForm.max_position_weight * 100).toFixed(0) }}%</p>
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">日内净值下跌警告线（L1，0.01 ~ 0.10）</label>
              <input v-model.number="paramsForm.daily_loss_warning_threshold" type="number" min="0.01" max="0.10" step="0.005" />
              <p class="text-[10px] text-[var(--text-tertiary)] mt-0.5">当前: {{ (paramsForm.daily_loss_warning_threshold * 100).toFixed(1) }}%</p>
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">日内净值下跌暂停线（L2，须大于警告线）</label>
              <input v-model.number="paramsForm.daily_loss_suspend_threshold" type="number" min="0.01" max="0.20" step="0.005" />
              <p class="text-[10px] text-[var(--text-tertiary)] mt-0.5">当前: {{ (paramsForm.daily_loss_suspend_threshold * 100).toFixed(1) }}%</p>
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">最大回撤紧急停止线（L3，须大于暂停线）</label>
              <input v-model.number="paramsForm.max_drawdown_emergency" type="number" min="0.05" max="0.50" step="0.01" />
              <p class="text-[10px] text-[var(--text-tertiary)] mt-0.5">当前: {{ (paramsForm.max_drawdown_emergency * 100).toFixed(1) }}%</p>
            </div>
            <div class="flex gap-2 pt-2">
              <ActionButton
                variant="primary"
                :loading="updateParamsMutation.isPending.value"
                @click="submitParams"
              >
                保存并立即生效
              </ActionButton>
              <ActionButton variant="ghost" @click="showParamsForm = false">取消</ActionButton>
            </div>
          </div>
        </div>

        <!-- Rule form -->
        <div v-if="showForm" class="card p-5 self-start sticky top-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">{{ editingRule ? '编辑规则' : '创建规则' }}</h3>
            <button class="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]" @click="showForm = false">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <div class="space-y-3">
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">规则名称 *</label>
              <input v-model="formName" type="text" placeholder="输入规则名称" />
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">描述</label>
              <textarea v-model="formDescription" rows="2" placeholder="可选描述" class="resize-none" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">优先级 (0-100)</label>
                <input v-model.number="formPriority" type="number" min="0" max="100" />
              </div>
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">逻辑运算符</label>
                <div class="flex rounded-lg overflow-hidden border border-[var(--border-default)]">
                  <button
                    class="flex-1 py-1.5 text-[12px] font-medium transition-colors"
                    :class="formLogicOp === 'AND' ? 'bg-[var(--brand-primary)] text-white' : 'bg-[var(--bg-input)] text-[var(--text-secondary)]'"
                    @click="formLogicOp = 'AND'"
                  >AND</button>
                  <button
                    class="flex-1 py-1.5 text-[12px] font-medium transition-colors"
                    :class="formLogicOp === 'OR' ? 'bg-[var(--brand-primary)] text-white' : 'bg-[var(--bg-input)] text-[var(--text-secondary)]'"
                    @click="formLogicOp = 'OR'"
                  >OR</button>
                </div>
              </div>
            </div>
            <div>
              <div class="flex items-center justify-between mb-2">
                <label class="text-xs text-[var(--text-secondary)]">条件 ({{ formConditions.length }}/10)</label>
                <button v-if="formConditions.length < 10" class="text-[11px] text-[var(--brand-primary)] hover:underline" @click="addCondition">+ 添加条件</button>
              </div>
              <div class="space-y-2">
                <div v-for="(cond, idx) in formConditions" :key="idx" class="flex items-center gap-1.5">
                  <select v-model="cond.field" class="flex-1 text-[12px] py-1.5">
                    <option v-for="(label, key) in fieldLabels" :key="key" :value="key">{{ label }}</option>
                  </select>
                  <select v-model="cond.operator" class="w-16 text-[12px] py-1.5">
                    <option v-for="(label, key) in operatorLabels" :key="key" :value="key">{{ label }}</option>
                  </select>
                  <input v-model.number="cond.value" type="number" step="0.01" class="w-20 text-[12px] py-1.5" />
                  <button v-if="formConditions.length > 1" class="text-[var(--text-tertiary)] hover:text-[var(--negative)] p-1" @click="removeCondition(idx)">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                  </button>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 pt-2">
              <ActionButton
                variant="primary"
                :disabled="!canSubmitForm"
                :loading="createMutation.isPending.value || updateMutation.isPending.value"
                @click="submitForm"
              >
                {{ editingRule ? '更新' : '创建' }}
              </ActionButton>
              <ActionButton variant="ghost" @click="showForm = false">取消</ActionButton>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Dialogs -->
    <ConfirmDialog
      :visible="showDeleteConfirm"
      @update:visible="showDeleteConfirm = $event"
      title="删除规则"
      message="确认要删除此规则吗？此操作不可逆。"
      variant="danger"
      confirm-text="删除"
      :loading="deleteMutation.isPending.value"
      @confirm="handleDelete"
    />

    <EmergencyDialog
      :visible="showEmergencyDialog"
      mode="activate"
      :loading="isActivatingEmergency"
      @update:visible="showEmergencyDialog = $event"
      @activate="handleEmergencyActivate"
      @cancel="showEmergencyDialog = false"
    />

    <ResetCircuitBreakerDialog
      :visible="showResetDialog"
      :current-level="(riskStatus?.circuit_breaker?.level ?? 0) as 0|1|2|3"
      :loading="resetCircuitBreakerMutation.isPending.value"
      @update:visible="showResetDialog = $event"
      @confirm="({ target_level, authorized_by }) => resetCircuitBreakerMutation.mutate({ target_level, authorized_by })"
    />
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
