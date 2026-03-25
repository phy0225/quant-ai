<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import type { AutoApprovalRule, RuleCondition } from '@/types/risk'

interface Props {
  rule?: AutoApprovalRule | null
  mode: 'create' | 'edit'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  rule: null,
  loading: false,
})

const emit = defineEmits<{
  submit: [payload: {
    name: string
    description: string | null
    priority: number
    logic_operator: 'AND' | 'OR'
    conditions: RuleCondition[]
    is_active: boolean
  }]
  cancel: []
}>()

const name = ref('')
const description = ref('')
const priority = ref(0)
const logicOperator = ref<'AND' | 'OR'>('AND')
const isActive = ref(true)
const conditions = ref<RuleCondition[]>([
  { field: 'max_weight_delta', operator: 'lte', value: 0.05 },
])

const fieldLabels: Record<string, string> = {
  max_weight_delta: '最大单标的权重变化',
  min_confidence_score: 'Agent 最低置信度',
  max_position_weight: '最大单标的建议权重',
  affected_symbols_count: '涉及调仓标的数量',
  total_turnover: '总换手率',
}

const operatorLabels: Record<string, string> = {
  lte: '<=',
  gte: '>=',
  lt: '<',
  gt: '>',
  eq: '=',
}

// Populate form when editing
watch(
  () => props.rule,
  (rule) => {
    if (rule) {
      name.value = rule.name
      description.value = rule.description || ''
      priority.value = rule.priority
      logicOperator.value = rule.logic_operator
      isActive.value = rule.is_active
      conditions.value = rule.conditions.map((c) => ({ ...c }))
    }
  },
  { immediate: true }
)

const canSubmit = computed(() => {
  return name.value.trim().length > 0 && conditions.value.length > 0
})

function addCondition() {
  if (conditions.value.length < 10) {
    conditions.value.push({ field: 'max_weight_delta', operator: 'lte', value: 0 })
  }
}

function removeCondition(index: number) {
  if (conditions.value.length > 1) {
    conditions.value.splice(index, 1)
  }
}

function handleSubmit() {
  if (!canSubmit.value) return
  emit('submit', {
    name: name.value.trim(),
    description: description.value.trim() || null,
    priority: priority.value,
    logic_operator: logicOperator.value,
    conditions: conditions.value,
    is_active: isActive.value,
  })
}
</script>

<template>
  <div class="card p-5" role="form" :aria-label="props.mode === 'create' ? '创建规则' : '编辑规则'">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-[var(--text-primary)]">
        {{ props.mode === 'create' ? '创建规则' : '编辑规则' }}
      </h3>
      <button
        class="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
        aria-label="关闭表单"
        @click="emit('cancel')"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <div class="space-y-3">
      <!-- Rule name -->
      <div>
        <label class="block text-xs text-[var(--text-secondary)] mb-1" for="rule-name">
          规则名称 <span class="text-[var(--negative)]">*</span>
        </label>
        <input
          id="rule-name"
          v-model="name"
          type="text"
          placeholder="输入规则名称"
          required
        />
      </div>

      <!-- Description -->
      <div>
        <label class="block text-xs text-[var(--text-secondary)] mb-1" for="rule-desc">描述</label>
        <textarea
          id="rule-desc"
          v-model="description"
          rows="2"
          placeholder="可选描述"
          class="resize-none"
        />
      </div>

      <!-- Priority and logic operator -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1" for="rule-priority">
            优先级 (0-100)
          </label>
          <input
            id="rule-priority"
            v-model.number="priority"
            type="number"
            min="0"
            max="100"
          />
        </div>
        <div>
          <label class="block text-xs text-[var(--text-secondary)] mb-1">逻辑运算符</label>
          <div class="flex rounded-lg overflow-hidden border border-[var(--border-default)]" role="radiogroup" aria-label="逻辑运算符">
            <button
              class="flex-1 py-1.5 text-[12px] font-medium transition-colors"
              :class="logicOperator === 'AND' ? 'bg-[var(--brand-primary)] text-white' : 'bg-[var(--bg-input)] text-[var(--text-secondary)]'"
              role="radio"
              :aria-checked="logicOperator === 'AND'"
              @click="logicOperator = 'AND'"
            >AND</button>
            <button
              class="flex-1 py-1.5 text-[12px] font-medium transition-colors"
              :class="logicOperator === 'OR' ? 'bg-[var(--brand-primary)] text-white' : 'bg-[var(--bg-input)] text-[var(--text-secondary)]'"
              role="radio"
              :aria-checked="logicOperator === 'OR'"
              @click="logicOperator = 'OR'"
            >OR</button>
          </div>
        </div>
      </div>

      <!-- Enable/Disable toggle -->
      <div class="flex items-center gap-2">
        <label class="relative inline-flex items-center cursor-pointer">
          <input
            v-model="isActive"
            type="checkbox"
            class="sr-only peer"
            aria-label="启用规则"
          />
          <div class="w-9 h-5 bg-[var(--bg-overlay)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[var(--brand-primary)]" />
        </label>
        <span class="text-xs text-[var(--text-secondary)]">
          {{ isActive ? '启用' : '禁用' }}
        </span>
      </div>

      <!-- Conditions -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-xs text-[var(--text-secondary)]">
            条件 ({{ conditions.length }}/10)
          </label>
          <button
            v-if="conditions.length < 10"
            class="text-[11px] text-[var(--brand-primary)] hover:underline"
            @click="addCondition"
          >
            + 添加条件
          </button>
        </div>
        <div class="space-y-2">
          <div
            v-for="(cond, idx) in conditions"
            :key="idx"
            class="flex items-center gap-1.5"
          >
            <select
              v-model="cond.field"
              class="flex-1 text-[12px] py-1.5"
              :aria-label="`条件 ${idx + 1} 字段`"
            >
              <option v-for="(label, key) in fieldLabels" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
            <select
              v-model="cond.operator"
              class="w-16 text-[12px] py-1.5"
              :aria-label="`条件 ${idx + 1} 运算符`"
            >
              <option v-for="(label, key) in operatorLabels" :key="key" :value="key">
                {{ label }}
              </option>
            </select>
            <input
              v-model.number="cond.value"
              type="number"
              step="0.01"
              class="w-20 text-[12px] py-1.5"
              :aria-label="`条件 ${idx + 1} 值`"
            />
            <button
              v-if="conditions.length > 1"
              class="text-[var(--text-tertiary)] hover:text-[var(--negative)] p-1 transition-colors"
              :aria-label="`删除条件 ${idx + 1}`"
              @click="removeCondition(idx)"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-2 pt-2">
        <ActionButton
          variant="primary"
          :disabled="!canSubmit"
          :loading="props.loading"
          @click="handleSubmit"
        >
          {{ props.mode === 'create' ? '创建' : '更新' }}
        </ActionButton>
        <ActionButton variant="ghost" @click="emit('cancel')">
          取消
        </ActionButton>
      </div>
    </div>
  </div>
</template>
