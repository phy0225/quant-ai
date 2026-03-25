<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import ActionButton from '@/components/ui/ActionButton.vue'
import AgentSignalCard from '@/components/domain/AgentSignalCard.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import { decisionsApi } from '@/api/decisions'
import type { DecisionRun } from '@/types/decision'

const router = useRouter()
const route  = useRoute()

// ── 表单 ──────────────────────────────────────────────────────────────────
const symbolsInput = ref('')
const portfolioInput = ref('')

// ── 状态 ──────────────────────────────────────────────────────────────────
const currentRun   = ref<DecisionRun | null>(null)
const isSubmitting = ref(false)   // 正在提交触发请求
const isPolling    = ref(false)   // 正在轮询结果
const errorMsg     = ref('')
const elapsedTime  = ref(0)

// ── 计时器 ────────────────────────────────────────────────────────────────
let pollTimer:    ReturnType<typeof setTimeout> | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null

function startElapsed() {
  elapsedTime.value = 0
  elapsedTimer = setInterval(() => { elapsedTime.value++ }, 1000)
}

function stopElapsed() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

function stopPolling() {
  isPolling.value = false
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
  stopElapsed()
}

onUnmounted(stopPolling)
// ── 初始化：读取 URL 参数 + 自动填入持仓 ─────────────────────────────────
async function loadPortfolioFromDB() {
  // 优先读取 URL query 参数（从持仓页点「分析」跳转过来）
  const qs = route.query.symbols as string | undefined
  const qp = route.query.portfolio as string | undefined
  if (qs) symbolsInput.value = qs
  if (qp) { portfolioInput.value = qp; return }

  // 没有 query 参数时，自动从后端读取当前持仓
  try {
    const res = await fetch('/api/v1/portfolio/')
    const data = await res.json()
    const holdings: any[] = data.holdings || []
    if (holdings.length > 0) {
      portfolioInput.value = holdings
        .map((h: any) => `${h.symbol}:${h.weight}`)
        .join(', ')
    }
  } catch {
    // 接口不可用时静默忽略
  }
}

onMounted(loadPortfolioFromDB)

// ── 轮询 ──────────────────────────────────────────────────────────────────
function startPolling(id: string) {
  stopPolling()
  isPolling.value = true
  startElapsed()
  let pollCount = 0

  const doPoll = async () => {
    try {
      const run = await decisionsApi.get(id)
      currentRun.value = run
      if (run.status === 'completed' || run.status === 'failed') {
        stopPolling()
        return
      }
    } catch {
      // 网络抖动忽略
    }
    if (!isPolling.value) return
    pollCount++
    // 前5次 1.5s → 5-15次 3s → 之后 5s
    const delay = pollCount < 5 ? 1500 : pollCount < 15 ? 3000 : 5000
    pollTimer = setTimeout(doPoll, delay)
  }

  pollTimer = setTimeout(doPoll, 800)
}

// ── 触发分析 ──────────────────────────────────────────────────────────────
function parsePortfolio(): Record<string, number> | undefined {
  const txt = portfolioInput.value.trim()
  if (!txt) return undefined
  const result: Record<string, number> = {}
  for (const part of txt.split(',')) {
    const [sym, wt] = part.trim().split(':')
    if (sym && wt) result[sym.trim().toUpperCase()] = parseFloat(wt.trim())
  }
  return Object.keys(result).length > 0 ? result : undefined
}

async function handleTrigger() {
  const symbols = symbolsInput.value
    .split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
  if (!symbols.length) return

  // 重置状态
  currentRun.value = null
  errorMsg.value   = ''
  stopPolling()
  isSubmitting.value = true

  try {
    const run = await decisionsApi.trigger({
      symbols,
      current_portfolio: parsePortfolio(),
    })
    currentRun.value = run
    startPolling(run.id)
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.detail
      || e?.message
      || '触发失败，请检查后端服务是否启动'
  } finally {
    isSubmitting.value = false
  }
}

// ── 进度步骤 ──────────────────────────────────────────────────────────────
const AGENT_STEPS = [
  { key: 'technical',   label: '技术分析' },
  { key: 'fundamental', label: '基本面分析' },
  { key: 'news',        label: '新闻分析' },
  { key: 'sentiment',   label: '情绪分析' },
  { key: 'risk',        label: '风控审核' },
  { key: 'executor',    label: '决策输出' },
]

function stepStatus(key: string): 'done' | 'active' | 'waiting' {
  const signals = currentRun.value?.agent_signals ?? []
  if (signals.some((s: any) => s.agent_type === key)) return 'done'
  if (!isPolling.value) return 'waiting'
  // 前4个并行：未完成的都标 active
  const analystKeys = ['technical', 'fundamental', 'news', 'sentiment']
  const analystsDone = signals.filter((s: any) => analystKeys.includes(s.agent_type)).length
  if (analystsDone < 4 && analystKeys.includes(key)) return 'active'
  // 风控和执行顺序
  if (key === 'risk' && analystsDone >= 4 && !signals.some((s: any) => s.agent_type === 'risk')) return 'active'
  if (key === 'executor' && signals.some((s: any) => s.agent_type === 'risk') && !signals.some((s: any) => s.agent_type === 'executor')) return 'active'
  return 'waiting'
}

const progressPct = computed(() => {
  const n = currentRun.value?.agent_signals?.length ?? 0
  return Math.round((n / 6) * 100)
})

// 是否正在运行（提交中 or 轮询中）
const isRunning = computed(() => isSubmitting.value || isPolling.value)

// 是否展示右侧内容区
const showPanel = computed(() =>
  isSubmitting.value || isPolling.value || currentRun.value !== null || !!errorMsg.value
)

const directionLabel: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }
const riskLabel:      Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }
const riskVariant:    Record<string, string> = { low: 'approved', medium: 'pending', high: 'rejected' }
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <h1 class="text-xl font-bold text-[var(--text-primary)] mb-6">触发 Agent 分析</h1>

    <div class="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">

      <!-- ── 左侧：表单 ── -->
      <div class="card p-5 self-start">
        <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-1">分析配置</h3>
        <p class="text-[12px] text-[var(--text-tertiary)] mb-4">
          输入目标标的，多标的用逗号分隔。系统将启动 6 个 AI Agent 并行分析并产出交易决策。
        </p>

        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">分析标的 *</label>
            <input
              v-model="symbolsInput"
              type="text"
              placeholder="AAPL, GOOGL, MSFT"
              :disabled="isRunning"
            />
          </div>

          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">
              当前持仓（可选，格式：AAPL:0.3, GOOGL:0.2）
            </label>
            <input
              v-model="portfolioInput"
              type="text"
              placeholder="AAPL:0.30, CASH:0.70"
              :disabled="isRunning"
            />
          </div>

          <ActionButton
            variant="primary"
            size="lg"
            class="w-full"
            :loading="isRunning"
            :disabled="!symbolsInput.trim() || isRunning"
            @click="handleTrigger"
          >
            {{ isRunning ? `分析中... ${elapsedTime}s` : '开始分析' }}
          </ActionButton>
        </div>
      </div>

      <!-- ── 右侧：进度 & 结果 ── -->
      <div>

        <!-- 空状态 -->
        <div v-if="!showPanel" class="card p-16 text-center">
          <div class="text-4xl mb-3">🤖</div>
          <p class="text-[var(--text-secondary)] text-sm mb-1">
            输入标的代码，启动 AI Agent 多维分析
          </p>
          <p class="text-[var(--text-tertiary)] text-[12px]">
            分析完成后可在「审批」页面处理决策
          </p>
        </div>

        <!-- 内容面板 -->
        <div v-else class="space-y-4">

          <!-- 错误提示 -->
          <div
            v-if="errorMsg"
            class="card p-4 border border-[var(--negative)]/40 bg-[var(--negative)]/5"
          >
            <p class="text-[var(--negative)] font-semibold text-sm mb-1">请求失败</p>
            <p class="text-[12px] text-[var(--text-secondary)]">{{ errorMsg }}</p>
            <p class="text-[11px] text-[var(--text-tertiary)] mt-1">
              请确认后端已启动（uvicorn main:app --reload --port 8000）
            </p>
          </div>

          <!-- Agent 进度步骤 -->
          <div v-if="!errorMsg" class="card p-4">
            <h4 class="text-sm font-semibold text-[var(--text-primary)] mb-3">
              Agent 分析进度
            </h4>

            <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
              <div
                v-for="step in AGENT_STEPS"
                :key="step.key"
                class="flex items-center gap-2 p-2 rounded-lg text-[12px] transition-all duration-300"
                :class="{
                  'bg-[var(--positive)]/10 text-[var(--positive)]':   stepStatus(step.key) === 'done',
                  'bg-[var(--brand-primary)]/10 text-[var(--brand-primary)]': stepStatus(step.key) === 'active',
                  'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]': stepStatus(step.key) === 'waiting',
                }"
              >
                <span class="text-sm leading-none">
                  <template v-if="stepStatus(step.key) === 'done'">✓</template>
                  <template v-else-if="stepStatus(step.key) === 'active'">
                    <span class="inline-block animate-spin">⟳</span>
                  </template>
                  <template v-else>○</template>
                </span>
                <span class="font-medium">{{ step.label }}</span>
              </div>
            </div>

            <!-- 进度条 -->
            <div class="mt-3 flex items-center gap-2">
              <div class="w-full h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
                <div
                  class="h-full bg-[var(--brand-primary)] rounded-full transition-all duration-500"
                  :style="{ width: `${progressPct}%` }"
                />
              </div>
              <span class="text-[11px] text-[var(--text-tertiary)] tabular-nums whitespace-nowrap">
                {{ currentRun?.agent_signals?.length ?? 0 }}/6
              </span>
            </div>
          </div>

          <!-- 失败 -->
          <div
            v-if="currentRun?.status === 'failed'"
            class="card p-5 border border-[var(--negative)]/30"
          >
            <p class="text-[var(--negative)] font-semibold text-sm mb-1">分析失败</p>
            <p class="text-[12px] text-[var(--text-secondary)]">
              {{ currentRun.error_message ?? '未知错误，请重试' }}
            </p>
          </div>

          <!-- 完成：最终决策 -->
          <div v-if="currentRun?.status === 'completed'" class="card p-4">
            <h4 class="text-sm font-semibold text-[var(--text-primary)] mb-3">最终决策</h4>
            <div class="flex items-center gap-3 flex-wrap">
              <div class="flex items-center gap-2">
                <span class="text-[12px] text-[var(--text-secondary)]">交易方向</span>
                <span
                  class="text-lg font-bold"
                  :class="{
                    'text-[var(--positive)]': currentRun.final_direction === 'buy',
                    'text-[var(--negative)]': currentRun.final_direction === 'sell',
                    'text-[var(--text-secondary)]': !currentRun.final_direction || currentRun.final_direction === 'hold',
                  }"
                >
                  {{ directionLabel[currentRun.final_direction ?? ''] ?? currentRun.final_direction ?? '—' }}
                </span>
              </div>

              <div v-if="currentRun.risk_level" class="flex items-center gap-2">
                <span class="text-[12px] text-[var(--text-secondary)]">风险评级</span>
                <TagBadge
                  :variant="(riskVariant[currentRun.risk_level] as any)"
                  :label="riskLabel[currentRun.risk_level] ?? currentRun.risk_level"
                />
              </div>

              <div class="ml-auto flex gap-2">
                <ActionButton
                  variant="ghost"
                  size="sm"
                  @click="router.push(`/decisions/${currentRun!.id}`)"
                >
                  查看完整链路
                </ActionButton>
                <ActionButton
                  variant="primary"
                  size="sm"
                  @click="router.push('/approvals')"
                >
                  前往审批 →
                </ActionButton>
              </div>
            </div>
          </div>

          <!-- Agent 信号卡片（逐步出现） -->
          <div v-if="(currentRun?.agent_signals?.length ?? 0) > 0">
            <h4 class="text-sm font-semibold text-[var(--text-primary)] mb-3">
              各 Agent 信号详情
              <span class="text-[12px] font-normal text-[var(--text-tertiary)] ml-1">
                ({{ currentRun?.agent_signals?.length }}/6)
              </span>
            </h4>
            <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
              <AgentSignalCard
                v-for="signal in currentRun!.agent_signals"
                :key="signal.agent_type"
                :signal="signal"
              />
            </div>
          </div>

        </div><!-- end 内容面板 -->
      </div><!-- end 右侧 -->
    </div>
  </div>
</template>