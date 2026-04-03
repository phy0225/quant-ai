<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { weightsApi, type AgentWeightDetail } from '@/api/weights'

// 数据
const weights = ref<AgentWeightDetail[]>([])
const rlStatus = ref<{
  settled_count: number
  min_settled_for_rl: number
  progress_pct: number
  last_trained_at: string | null
  model_version: string | null
  rl_ready: boolean
} | null>(null)
const isLoading = ref(true)
const isSettling = ref(false)

// Toast
const toast = ref<{ message: string; type: 'success' | 'error' } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(message: string, type: 'success' | 'error') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { message, type }
  toastTimer = setTimeout(() => { toast.value = null }, 3500)
}

// 加载数据
async function loadWeights() {
  isLoading.value = true
  try {
    const data = await weightsApi.getWeights()
    weights.value = data.weights.length > 0 ? data.weights : [
      { agent_type: 'technical',   weight: 0.25, weight_source: 'default', locked: false, rl_model_version: null, last_updated_at: null },
      { agent_type: 'fundamental', weight: 0.25, weight_source: 'default', locked: false, rl_model_version: null, last_updated_at: null },
      { agent_type: 'news',        weight: 0.25, weight_source: 'default', locked: false, rl_model_version: null, last_updated_at: null },
      { agent_type: 'sentiment',   weight: 0.25, weight_source: 'default', locked: false, rl_model_version: null, last_updated_at: null },
    ]
    rlStatus.value = data.rl_status || null
  } catch (e) {
    showToast('加载权重配置失败', 'error')
  } finally {
    isLoading.value = false
  }
}

// 锁定/解锁
async function toggleLock(item: AgentWeightDetail) {
  const newLocked = !item.locked
  try {
    const updated = await weightsApi.lockAgent(item.agent_type, newLocked)
    const idx = weights.value.findIndex((w) => w.agent_type === item.agent_type)
    if (idx >= 0) weights.value[idx] = updated
    showToast(`${item.agent_type} 已${newLocked ? '锁定' : '解锁'}`, 'success')
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '操作失败', 'error')
  }
}

// 修改权重
const editingAgent = ref<string | null>(null)
const editValue = ref<number>(0)

function startEdit(item: AgentWeightDetail) {
  editingAgent.value = item.agent_type
  editValue.value = item.weight
}

async function submitEdit(item: AgentWeightDetail) {
  if (editValue.value < 0.05 || editValue.value > 0.45) {
    showToast('权重必须在 5% ~ 45% 之间', 'error')
    return
  }
  try {
    const updated = await weightsApi.setAgentWeight(item.agent_type, editValue.value)
    const idx = weights.value.findIndex((w) => w.agent_type === item.agent_type)
    if (idx >= 0) weights.value[idx] = updated
    editingAgent.value = null
    showToast(`${item.agent_type} 权重已更新为 ${(editValue.value * 100).toFixed(1)}%`, 'success')
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '修改失败', 'error')
  }
}

function cancelEdit() {
  editingAgent.value = null
}

// 手动触发结算
async function triggerSettlement() {
  isSettling.value = true
  try {
    const result = await weightsApi.triggerSettlement()
    showToast(`结算完成，本次处理 ${result.settled_count} 个节点`, 'success')
    await loadWeights()
  } catch (e: any) {
    showToast(e?.response?.data?.detail || '结算失败', 'error')
  } finally {
    isSettling.value = false
  }
}

// 权重来源徽章样式
function sourceBadgeClass(source: string): string {
  if (source === 'rl_optimized') return 'bg-purple-100 text-purple-700'
  if (source === 'accuracy_based') return 'bg-blue-100 text-blue-700'
  if (source === 'manual') return 'bg-orange-100 text-orange-700'
  return 'bg-gray-100 text-gray-600'
}

function sourceBadgeLabel(source: string): string {
  if (source === 'rl_optimized') return 'RL优化'
  if (source === 'accuracy_based') return '统计'
  if (source === 'manual') return '手动'
  return '默认'
}

// Agent 中文名
const agentNameMap: Record<string, string> = {
  technical:   '技术分析师',
  fundamental: '基本面分析师',
  news:        '新闻分析师',
  sentiment:   '情绪分析师',
}

// 权重总和
const totalWeight = computed(() =>
  weights.value.reduce((s, w) => s + w.weight, 0)
)

// 格式化时间
function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(() => {
  loadWeights()
})
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto">
    <!-- Toast -->
    <Transition name="toast">
      <div
        v-if="toast"
        class="fixed top-5 right-5 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-[13px] font-medium"
        :class="toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'"
      >
        {{ toast.message }}
      </div>
    </Transition>

    <h1 class="text-xl font-bold text-[var(--text-primary)] mb-6">Agent 权重管理</h1>

    <!-- RL 训练进度卡片 -->
    <div v-if="rlStatus" class="card p-4 mb-6">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">RL 训练进度</h3>
        <span
          class="px-2 py-0.5 rounded text-[11px] font-medium"
          :class="rlStatus.rl_ready ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'"
        >
          {{ rlStatus.rl_ready ? 'RL 已就绪' : `需要 ${rlStatus.min_settled_for_rl} 个结算节点` }}
        </span>
      </div>
      <div class="mb-2">
        <div class="flex justify-between text-[12px] text-[var(--text-secondary)] mb-1">
          <span>已结算节点: {{ rlStatus.settled_count }} / {{ rlStatus.min_settled_for_rl }}</span>
          <span>{{ rlStatus.progress_pct }}%</span>
        </div>
        <div class="w-full bg-gray-200 rounded-full h-2">
          <div
            class="h-2 rounded-full transition-all duration-500"
            :class="rlStatus.rl_ready ? 'bg-green-500' : 'bg-blue-400'"
            :style="{ width: rlStatus.progress_pct + '%' }"
          />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4 mt-3 text-[12px] text-[var(--text-secondary)]">
        <div>
          <span class="text-[var(--text-tertiary)]">上次 RL 训练: </span>
          {{ formatTime(rlStatus.last_trained_at) }}
        </div>
        <div>
          <span class="text-[var(--text-tertiary)]">模型版本: </span>
          {{ rlStatus.model_version || '-' }}
        </div>
      </div>
    </div>

    <!-- 权重配置表格 -->
    <div class="card p-4 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">Agent 权重配置</h3>
        <span class="text-[12px]" :class="Math.abs(totalWeight - 1.0) > 0.01 ? 'text-red-500 font-medium' : 'text-[var(--text-tertiary)]'">
          权重合计: {{ (totalWeight * 100).toFixed(1) }}%
        </span>
      </div>

      <div v-if="isLoading" class="space-y-3">
        <div v-for="i in 4" :key="i" class="h-12 bg-gray-100 rounded animate-pulse" />
      </div>
      <template v-else>
        <div
          v-for="item in weights"
          :key="item.agent_type"
          class="flex items-center gap-4 py-3 border-b border-[var(--border-subtle)] last:border-0"
        >
          <!-- Agent 名称 + 来源徽章 -->
          <div class="w-40 flex-shrink-0">
            <p class="text-[13px] font-medium text-[var(--text-primary)]">
              {{ agentNameMap[item.agent_type] || item.agent_type }}
            </p>
            <span
              class="inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium"
              :class="sourceBadgeClass(item.weight_source)"
            >
              {{ sourceBadgeLabel(item.weight_source) }}
            </span>
          </div>

          <!-- 权重进度条 + 编辑 -->
          <div class="flex-1">
            <template v-if="editingAgent === item.agent_type">
              <div class="flex items-center gap-2">
                <input
                  v-model.number="editValue"
                  type="number"
                  min="0.05"
                  max="0.45"
                  step="0.01"
                  class="w-24 text-[13px] px-2 py-1 border rounded"
                  @keydown.enter="submitEdit(item)"
                  @keydown.esc="cancelEdit"
                />
                <span class="text-[12px] text-[var(--text-tertiary)]">{{ (editValue * 100).toFixed(1) }}%</span>
                <button
                  class="px-2 py-1 text-[12px] bg-blue-600 text-white rounded hover:bg-blue-700"
                  @click="submitEdit(item)"
                >
                  确认
                </button>
                <button
                  class="px-2 py-1 text-[12px] border rounded hover:bg-gray-50"
                  @click="cancelEdit"
                >
                  取消
                </button>
              </div>
            </template>
            <template v-else>
              <div class="flex items-center gap-2">
                <div class="flex-1 bg-gray-200 rounded-full h-2">
                  <div
                    class="h-2 rounded-full bg-blue-500 transition-all"
                    :style="{ width: (item.weight * 100) + '%' }"
                  />
                </div>
                <span class="text-[13px] font-medium tabular-nums w-12 text-right">
                  {{ (item.weight * 100).toFixed(1) }}%
                </span>
                <button
                  v-if="!item.locked"
                  class="text-[11px] text-blue-600 hover:underline"
                  @click="startEdit(item)"
                >
                  修改
                </button>
              </div>
              <p v-if="item.last_updated_at" class="text-[10px] text-[var(--text-tertiary)] mt-0.5">
                更新于 {{ formatTime(item.last_updated_at) }}
              </p>
            </template>
          </div>

          <!-- 锁定开关 -->
          <button
            class="flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded text-[12px] border transition-colors"
            :class="item.locked
              ? 'bg-orange-50 border-orange-300 text-orange-700 hover:bg-orange-100'
              : 'border-gray-200 text-[var(--text-secondary)] hover:bg-gray-50'"
            @click="toggleLock(item)"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                v-if="item.locked"
                stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
              <path
                v-else
                stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z"
              />
            </svg>
            {{ item.locked ? '已锁定' : '锁定' }}
          </button>
        </div>
      </template>
    </div>

    <!-- 操作区 -->
    <div class="card p-4">
      <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-3">运维操作</h3>
      <div class="flex items-center gap-4">
        <button
          class="px-4 py-2 text-[13px] font-medium rounded-lg border border-blue-500 text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          :disabled="isSettling"
          @click="triggerSettlement"
        >
          {{ isSettling ? '结算中...' : '手动触发 T+5 结算' }}
        </button>
        <p class="text-[12px] text-[var(--text-tertiary)]">
          结算 7 天前已审批通过但尚未计算收益的图谱节点
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
