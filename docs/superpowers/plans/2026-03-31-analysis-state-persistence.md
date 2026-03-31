# 分析任务状态持久化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户离开「触发分析」页后再返回，分析任务自动恢复进度；刷新浏览器后同样恢复；侧边栏在任务运行中显示脉冲圆点。

**Architecture:** 新增 Pinia store (`store/analysis.ts`) 作为唯一状态持久化层，通过 `sessionStorage` 在页面刷新后恢复 `run.id`。`AnalyzePage.vue` 的 `currentRun`/`isPolling` 迁移到 store；`onUnmounted` 只清计时器不清 store；`onMounted` 若检测到 `store.activeRunId` 则直接恢复轮询。`Sidebar.vue` 读取 `store.isRunning` 显示指示器。

**Tech Stack:** Vue 3 Composition API, Pinia ^2.1.7, TypeScript, storeToRefs, sessionStorage

---

## 文件清单

| 操作 | 路径 |
|------|------|
| 新增 | `frontend/src/store/analysis.ts` |
| 修改 | `frontend/src/pages/AnalyzePage.vue` |
| 修改 | `frontend/src/components/ui/Sidebar.vue` |

---

## Task 1.1：新增 Pinia store

**Files:**
- Create: `frontend/src/store/analysis.ts`

- [ ] **Step 1: 创建 store 文件**

内容完全如下（不要添加多余注释）：

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DecisionRun } from '@/types/decision'

export const useAnalysisStore = defineStore('analysis', () => {
  const activeRunId = ref<string | null>(sessionStorage.getItem('activeRunId'))
  const currentRun  = ref<DecisionRun | null>(null)
  const isPolling   = ref(false)

  const isRunning = computed(
    () => isPolling.value || currentRun.value?.status === 'running'
  )

  function setActiveRun(run: DecisionRun) {
    currentRun.value  = run
    activeRunId.value = run.id
    sessionStorage.setItem('activeRunId', run.id)
  }

  function clearActiveRun() {
    currentRun.value  = null
    activeRunId.value = null
    isPolling.value   = false
    sessionStorage.removeItem('activeRunId')
  }

  return { activeRunId, currentRun, isPolling, isRunning, setActiveRun, clearActiveRun }
})
```

- [ ] **Step 2: TypeScript 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错误输出（或仅现有的无关错误）。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store/analysis.ts
git commit -m "feat: 新增 analysis Pinia store，支持 sessionStorage 持久化"
```

---

## Task 1.2：改造 AnalyzePage.vue

**Files:**
- Modify: `frontend/src/pages/AnalyzePage.vue`（script setup 部分全量替换）

核心变更：
- `currentRun`/`isPolling` 迁移到 store（用 `storeToRefs` 解构）
- `onUnmounted` → `clearTimer()`（只清计时器，不动 store）
- `onMounted` → 加载持仓后，若 `store.activeRunId` 存在则恢复轮询
- `handleTrigger` 成功 → `store.setActiveRun(run)`
- 轮询结束/404 → `stopPolling()`（内部调 `store.clearActiveRun()`）

- [ ] **Step 1: 替换 `<script setup>` 内容**

将 `frontend/src/pages/AnalyzePage.vue` 的 `<script setup lang="ts">` 到 `</script>` 之间的全部内容替换为：

```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import ActionButton from '@/components/ui/ActionButton.vue'
import AgentSignalCard from '@/components/domain/AgentSignalCard.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import { decisionsApi } from '@/api/decisions'
import { useAnalysisStore } from '@/store/analysis'

const router = useRouter()
const route  = useRoute()
const store  = useAnalysisStore()
const { currentRun, isPolling } = storeToRefs(store)

// ── 表单 ──────────────────────────────────────────────────────────────────
const symbolsInput   = ref('')
const portfolioInput = ref('')

// ── 局部状态 ──────────────────────────────────────────────────────────────
const isSubmitting = ref(false)
const errorMsg     = ref('')
const elapsedTime  = ref(0)

// ── 计时器 ────────────────────────────────────────────────────────────────
let pollTimer:    ReturnType<typeof setTimeout>  | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null

function startElapsed() {
  elapsedTime.value = 0
  elapsedTimer = setInterval(() => { elapsedTime.value++ }, 1000)
}

function stopElapsed() {
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

// 仅清理计时器——路由离开时调用，store 状态保留
function clearTimer() {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
  stopElapsed()
}

// 完全停止轮询：清计时器 + 清 store（任务完成/失败/404 时调用）
function stopPolling() {
  clearTimer()
  store.clearActiveRun()
}

onUnmounted(clearTimer)

// ── 初始化 ────────────────────────────────────────────────────────────────
async function loadPortfolioFromDB() {
  const qs = route.query.symbols as string | undefined
  const qp = route.query.portfolio as string | undefined
  if (qs) symbolsInput.value = qs
  if (qp) { portfolioInput.value = qp; return }

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

onMounted(async () => {
  await loadPortfolioFromDB()
  // 恢复未完成的分析任务（路由返回 或 刷新浏览器）
  if (store.activeRunId) {
    startPolling(store.activeRunId)
  }
})

// ── 轮询 ──────────────────────────────────────────────────────────────────
function startPolling(id: string) {
  clearTimer()             // 清旧计时器，store 保留
  isPolling.value = true
  startElapsed()
  let pollCount = 0

  const doPoll = async () => {
    try {
      const run = await decisionsApi.get(id)
      store.setActiveRun(run)
      if (run.status === 'completed' || run.status === 'failed') {
        stopPolling()
        return
      }
    } catch (err: any) {
      if (err?.response?.status === 404) {
        stopPolling()
        return
      }
      // 其他网络抖动忽略
    }
    if (!isPolling.value) return
    pollCount++
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

  store.clearActiveRun()
  errorMsg.value     = ''
  clearTimer()
  isSubmitting.value = true

  try {
    const run = await decisionsApi.trigger({
      symbols,
      current_portfolio: parsePortfolio(),
    })
    store.setActiveRun(run)
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
  const analystKeys = ['technical', 'fundamental', 'news', 'sentiment']
  const analystsDone = signals.filter((s: any) => analystKeys.includes(s.agent_type)).length
  if (analystsDone < 4 && analystKeys.includes(key)) return 'active'
  if (key === 'risk' && analystsDone >= 4 && !signals.some((s: any) => s.agent_type === 'risk')) return 'active'
  if (key === 'executor' && signals.some((s: any) => s.agent_type === 'risk') && !signals.some((s: any) => s.agent_type === 'executor')) return 'active'
  return 'waiting'
}

const progressPct = computed(() => {
  const n = currentRun.value?.agent_signals?.length ?? 0
  return Math.round((n / 6) * 100)
})

const isRunning = computed(() => isSubmitting.value || isPolling.value)

const showPanel = computed(() =>
  isSubmitting.value || isPolling.value || currentRun.value !== null || !!errorMsg.value
)

const directionLabel: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有' }
const riskLabel:      Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }
const riskVariant:    Record<string, string> = { low: 'approved', medium: 'pending', high: 'rejected' }
```

`<template>` 部分**不需要任何改动**，保持原样。

- [ ] **Step 2: TypeScript 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无新增错误。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AnalyzePage.vue
git commit -m "feat: AnalyzePage 接入 analysisStore，支持离页恢复和刷新恢复"
```

---

## Task 1.3：Sidebar 添加运行中指示器

**Files:**
- Modify: `frontend/src/components/ui/Sidebar.vue`

- [ ] **Step 1: 在 `<script setup>` 顶部引入 store**

在 `frontend/src/components/ui/Sidebar.vue` 的 `<script setup>` 中，找到现有 import 块的末尾（约第 6 行 `const themeStore = useThemeStore()` 之后），添加：

```typescript
import { useAnalysisStore } from '@/store/analysis'
const analysisStore = useAnalysisStore()
```

即在文件第 6 行后插入这两行，最终 script 顶部如下：

```typescript
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSidebarStore } from '@/store/sidebar'
import { useThemeStore } from '@/store/theme'
import { useAnalysisStore } from '@/store/analysis'

const route = useRoute()
const router = useRouter()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()
const analysisStore = useAnalysisStore()
```

- [ ] **Step 2: 在导航按钮中添加脉冲圆点**

在 `<template>` 里，找到导航按钮内的 `<span v-show="!sidebarStore.isCollapsed" ...>{{ item.label }}</span>` 这一行（约第 114 行），在其**前面**插入脉冲圆点元素，使导航按钮内部变为：

```html
<button
  v-for="item in navItems"
  :key="item.path"
  class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-colors"
  :class="[
    isActive(item.path)
      ? 'bg-[var(--brand-primary-subtle)] text-[var(--brand-primary)]'
      : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
  ]"
  @click="router.push(item.path)"
  :title="item.label"
>
  <svg class="flex-shrink-0 w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
    <!-- ... 原有 SVG 模板内容不变 ... -->
  </svg>
  <span v-show="!sidebarStore.isCollapsed" class="whitespace-nowrap flex-1">{{ item.label }}</span>
  <!-- 分析运行中指示器 -->
  <span
    v-if="item.path === '/analyze' && analysisStore.isRunning"
    class="flex-shrink-0 w-2 h-2 rounded-full bg-[var(--brand-primary)] animate-pulse"
  />
</button>
```

具体操作：只需在原有的 `<span v-show="!sidebarStore.isCollapsed" class="whitespace-nowrap">{{ item.label }}</span>` 一行：
1. 将 `class="whitespace-nowrap"` 改为 `class="whitespace-nowrap flex-1"`
2. 在该 `<span>` 之后（`</button>` 之前）插入：

```html
  <span
    v-if="item.path === '/analyze' && analysisStore.isRunning"
    class="flex-shrink-0 w-2 h-2 rounded-full bg-[var(--brand-primary)] animate-pulse"
  />
```

- [ ] **Step 3: TypeScript 类型检查**

```bash
cd frontend && npx tsc --noEmit
```

预期：无错误。

- [ ] **Step 4: 构建验证**

```bash
cd frontend && npm run build
```

预期：Build 成功，无 TypeScript 错误，无 Vue 编译错误。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Sidebar.vue
git commit -m "feat: Sidebar 添加分析运行中脉冲圆点指示器"
```

---

## Task 1.4：手动验收

后端需先启动：`cd backend && uvicorn main:app --reload --port 8000`
前端需先启动：`cd frontend && npm run dev`

- [ ] **AC-01：离页恢复**
  1. 在「触发分析」页输入标的，点「开始分析」
  2. 看到进度面板出现，Agent 步骤开始运行
  3. 立即切换到「持仓」页，再切回「触发分析」
  4. ✅ 进度面板自动恢复，轮询继续更新

- [ ] **AC-02：分析完成后返回**
  1. 触发分析后切换页面，等待分析完成（约 30s）
  2. 切回「触发分析」页
  3. ✅ 直接显示最终决策结果，「前往审批」按钮可用，不再轮询

- [ ] **AC-03：侧边栏指示器**
  1. 触发分析后，查看侧边栏
  2. ✅「触发分析」菜单项右侧显示蓝色脉冲圆点
  3. 分析完成后，✅ 圆点消失

- [ ] **AC-04：刷新浏览器恢复**
  1. 触发分析后，按 F5 刷新浏览器
  2. ✅ 页面重新加载后自动恢复分析状态，继续轮询

- [ ] **AC-05：触发新分析覆盖旧状态**
  1. 等一次分析完成
  2. 修改标的，点「开始分析」
  3. ✅ 旧结果面板清空，新分析开始，sessionStorage 中 run.id 更新

- [ ] **AC-06：后端 404 静默清除**
  1. 在浏览器 DevTools 中手动设置 `sessionStorage.setItem('activeRunId', 'nonexistent-id')`
  2. 刷新页面
  3. ✅ 页面显示空状态，无错误提示，sessionStorage 中的 key 已被清除

- [ ] **AC-07：并发保护**
  1. 分析进行中，尝试点击「开始分析」按钮
  2. ✅ 按钮保持禁用状态

---

## 验收完成后

```bash
git log --oneline -5
```

应看到 3 个 feat commits：
- `feat: Sidebar 添加分析运行中脉冲圆点指示器`
- `feat: AnalyzePage 接入 analysisStore，支持离页恢复和刷新恢复`
- `feat: 新增 analysis Pinia store，支持 sessionStorage 持久化`
