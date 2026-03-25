<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ActionButton from '@/components/ui/ActionButton.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import { decisionsApi } from '@/api/decisions'

const router = useRouter()

// ── 数据 ────────────────────────────────────────────────────────────────────
interface Holding {
  id: string
  symbol: string
  symbol_name: string | null
  weight: number
  cost_price: number | null
  quantity: number | null
  market_value: number | null
  current_price: number | null
  pnl_pct: number | null
  note: string | null
  updated_at: string | null
}

interface Summary {
  total_weight: number
  total_mv: number
  avg_pnl_pct: number
  holding_count: number
  weight_dist: { symbol: string; symbol_name: string | null; weight: number }[]
}

const holdings   = ref<Holding[]>([])
const summary    = ref<Summary | null>(null)
const isLoading  = ref(false)
const isRefreshing = ref(false)

// 分析次数 Map<symbol, count>
const analysisCountMap = ref<Map<string, number>>(new Map())
const isLoadingStats = ref(true)

// ── 表单 ────────────────────────────────────────────────────────────────────
const showForm  = ref(false)
const editingId = ref<string | null>(null)
const form = ref({
  symbol:      '',
  symbol_name: '',
  weight:      '',
  cost_price:  '',
  quantity:    '',
  note:        '',
})

function resetForm() {
  form.value = { symbol: '', symbol_name: '', weight: '', cost_price: '', quantity: '', note: '' }
  editingId.value = null
}

function openAdd() {
  resetForm()
  showForm.value = true
}

function openEdit(h: Holding) {
  form.value = {
    symbol:      h.symbol,
    symbol_name: h.symbol_name || '',
    weight:      String((h.weight * 100).toFixed(2)),
    cost_price:  h.cost_price ? String(h.cost_price) : '',
    quantity:    h.quantity ? String(h.quantity) : '',
    note:        h.note || '',
  }
  editingId.value = h.id
  showForm.value  = true
}

// ── Toast ────────────────────────────────────────────────────────────────────
const toast = ref<{ msg: string; type: 'success' | 'error' } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(msg: string, type: 'success' | 'error' = 'success') {
  if (toastTimer) clearTimeout(toastTimer)
  toast.value = { msg, type }
  toastTimer = setTimeout(() => { toast.value = null }, 3000)
}

// ── API ─────────────────────────────────────────────────────────────────────
async function fetchAll() {
  isLoading.value = true
  try {
    const [hRes, sRes] = await Promise.all([
      fetch('/api/v1/portfolio/').then(r => r.json()),
      fetch('/api/v1/portfolio/summary').then(r => r.json()),
    ])
    holdings.value = hRes.holdings || []
    summary.value  = sRes
  } catch (e) {
    showToast('加载失败', 'error')
  } finally {
    isLoading.value = false
  }
}

async function fetchStats() {
  isLoadingStats.value = true
  try {
    const res = await decisionsApi.stats()
    const map = new Map<string, number>()
    for (const stat of res.symbol_stats) {
      map.set(stat.symbol, stat.decision_count)
    }
    analysisCountMap.value = map
  } catch {
    // 静默失败，不影响主流程
  } finally {
    isLoadingStats.value = false
  }
}

async function submitForm() {
  const weightNum = parseFloat(form.value.weight) / 100
  if (isNaN(weightNum) || weightNum < 0 || weightNum > 1) {
    showToast('权重须在 0-100% 之间', 'error')
    return
  }
  const body = {
    symbol:      form.value.symbol.trim().toUpperCase(),
    symbol_name: form.value.symbol_name.trim() || null,
    weight:      weightNum,
    cost_price:  form.value.cost_price ? parseFloat(form.value.cost_price) : null,
    quantity:    form.value.quantity   ? parseInt(form.value.quantity)    : null,
    note:        form.value.note.trim() || null,
  }
  try {
    if (editingId.value) {
      await fetch(`/api/v1/portfolio/${editingId.value}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      showToast('持仓已更新')
    } else {
      await fetch('/api/v1/portfolio/', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      showToast('持仓已添加')
    }
    showForm.value = false
    resetForm()
    await fetchAll()
  } catch {
    showToast('保存失败', 'error')
  }
}

async function deleteHolding(id: string, symbol: string) {
  if (!confirm(`确认清仓 ${symbol}？`)) return
  await fetch(`/api/v1/portfolio/${id}`, { method: 'DELETE' })
  showToast(`已清仓 ${symbol}`)
  await fetchAll()
}

async function refreshPrices() {
  isRefreshing.value = true
  try {
    await fetch('/api/v1/portfolio/refresh-prices', { method: 'POST' })
    await fetchAll()
    showToast('价格已刷新')
  } catch {
    showToast('刷新失败', 'error')
  } finally {
    isRefreshing.value = false
  }
}

// ── 辅助 ────────────────────────────────────────────────────────────────────
const totalWeight = computed(() => holdings.value.reduce((s, h) => s + h.weight, 0))
const remainWeight = computed(() => Math.max(0, 1 - totalWeight.value))

function pnlClass(pnl: number | null) {
  if (pnl === null) return 'text-[var(--text-tertiary)]'
  return pnl > 0 ? 'text-[var(--positive)]' : pnl < 0 ? 'text-[var(--negative)]' : 'text-[var(--text-tertiary)]'
}
function fmtPct(v: number | null) {
  if (v === null) return '--'
  return (v >= 0 ? '+' : '') + (v * 100).toFixed(2) + '%'
}
function fmtPrice(v: number | null) {
  return v !== null ? '¥' + v.toFixed(2) : '--'
}
function fmtMv(v: number | null) {
  if (v === null) return '--'
  return v >= 10000 ? (v / 10000).toFixed(1) + '万' : v.toFixed(0)
}
function weightBarStyle(w: number) {
  return { width: Math.min(w * 100, 100) + '%' }
}
function getAnalysisCount(symbol: string): string {
  if (isLoadingStats.value) return '--'
  const count = analysisCountMap.value.get(symbol)
  return count !== undefined ? `${count} 次` : '--'
}

onMounted(() => {
  fetchAll()
  fetchStats()
})
</script>

<template>
  <div class="p-6 max-w-[1400px] mx-auto">
    <!-- Toast -->
    <Transition name="toast">
      <div v-if="toast"
        class="fixed top-5 right-5 z-50 px-4 py-3 rounded-lg shadow-lg text-[13px] font-medium"
        :class="toast.type === 'success' ? 'bg-[var(--positive)] text-white' : 'bg-[var(--negative)] text-white'">
        {{ toast.msg }}
      </div>
    </Transition>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-xl font-bold text-[var(--text-primary)]">持仓管理</h1>
        <p class="text-[12px] text-[var(--text-tertiary)] mt-0.5">审批通过后自动同步，也可手动维护</p>
      </div>
      <div class="flex items-center gap-2">
        <ActionButton variant="outline" size="sm" :loading="isRefreshing" @click="refreshPrices">
          刷新价格
        </ActionButton>
        <ActionButton variant="primary" size="sm" @click="openAdd">
          + 添加持仓
        </ActionButton>
      </div>
    </div>

    <!-- Summary Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="card p-4">
        <p class="text-[11px] text-[var(--text-tertiary)] mb-1">持仓标的</p>
        <p class="text-2xl font-bold text-[var(--text-primary)]">{{ holdings.length }}</p>
      </div>
      <div class="card p-4">
        <p class="text-[11px] text-[var(--text-tertiary)] mb-1">已用仓位</p>
        <p class="text-2xl font-bold text-[var(--text-primary)]">
          {{ (totalWeight * 100).toFixed(1) }}%
        </p>
        <div class="mt-2 h-1.5 bg-[var(--bg-overlay)] rounded-full">
          <div class="h-full bg-[var(--brand-primary)] rounded-full transition-all"
            :style="{ width: Math.min(totalWeight * 100, 100) + '%' }" />
        </div>
      </div>
      <div class="card p-4">
        <p class="text-[11px] text-[var(--text-tertiary)] mb-1">剩余仓位</p>
        <p class="text-2xl font-bold" :class="remainWeight > 0.1 ? 'text-[var(--positive)]' : 'text-[var(--text-secondary)]'">
          {{ (remainWeight * 100).toFixed(1) }}%
        </p>
      </div>
      <div class="card p-4">
        <p class="text-[11px] text-[var(--text-tertiary)] mb-1">组合浮盈</p>
        <p class="text-2xl font-bold" :class="pnlClass(summary?.avg_pnl_pct ?? null)">
          {{ fmtPct(summary?.avg_pnl_pct ?? null) }}
        </p>
      </div>
    </div>

    <!-- Holdings Table -->
    <div class="card overflow-hidden mb-6">
      <div class="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">当前持仓</h3>
        <span class="text-[12px] text-[var(--text-tertiary)]">
          价格更新时间：{{ holdings[0]?.updated_at?.slice(0,16).replace('T',' ') ?? '--' }}
        </span>
      </div>

      <div v-if="isLoading" class="p-8 text-center text-[var(--text-tertiary)] text-sm">加载中...</div>

      <div v-else-if="!holdings.length" class="p-10 text-center">
        <p class="text-[var(--text-tertiary)] text-sm mb-2">暂无持仓记录</p>
        <p class="text-[12px] text-[var(--text-tertiary)]">审批通过后自动同步，或点击「添加持仓」手动录入</p>
      </div>

      <table v-else class="w-full text-[13px]">
        <thead>
          <tr class="border-b border-[var(--border-subtle)] text-[11px] text-[var(--text-tertiary)] uppercase">
            <th class="px-4 py-3 text-left">标的</th>
            <th class="px-4 py-3 text-right">仓位权重</th>
            <th class="px-4 py-3 text-right">成本价</th>
            <th class="px-4 py-3 text-right">最新价</th>
            <th class="px-4 py-3 text-right">浮动盈亏</th>
            <th class="px-4 py-3 text-right">持股数</th>
            <th class="px-4 py-3 text-right">市值</th>
            <th class="px-4 py-3 text-right">分析次数</th>
            <th class="px-4 py-3 text-center">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in holdings" :key="h.id"
            class="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)] transition-colors">
            <td class="px-4 py-3">
              <div class="font-medium text-[var(--text-primary)]">{{ h.symbol }}</div>
              <div v-if="h.symbol_name" class="text-[11px] text-[var(--text-tertiary)]">{{ h.symbol_name }}</div>
            </td>
            <td class="px-4 py-3 text-right">
              <div class="font-medium tabular-nums">{{ (h.weight * 100).toFixed(1) }}%</div>
              <div class="mt-1 h-1 bg-[var(--bg-overlay)] rounded-full w-16 ml-auto">
                <div class="h-full bg-[var(--brand-primary)] rounded-full"
                  :style="weightBarStyle(h.weight)" />
              </div>
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-[var(--text-secondary)]">
              {{ fmtPrice(h.cost_price) }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums font-medium">
              {{ fmtPrice(h.current_price) }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums font-medium" :class="pnlClass(h.pnl_pct)">
              {{ fmtPct(h.pnl_pct) }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-[var(--text-secondary)]">
              {{ h.quantity ? h.quantity.toLocaleString() : '--' }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-[var(--text-secondary)]">
              {{ fmtMv(h.market_value) }}
            </td>
            <td class="px-4 py-3 text-right tabular-nums text-[var(--text-secondary)]">
              {{ getAnalysisCount(h.symbol) }}
            </td>
            <td class="px-4 py-3 text-center">
              <div class="flex items-center justify-center gap-1">
                <button class="text-[12px] text-[var(--brand-primary)] hover:underline px-1"
                  @click="openEdit(h)">编辑</button>
                <span class="text-[var(--border-subtle)]">|</span>
                <button class="text-[12px] text-[var(--negative)] hover:underline px-1"
                  @click="deleteHolding(h.id, h.symbol)">清仓</button>
                <span class="text-[var(--border-subtle)]">|</span>
                <button class="text-[12px] text-[var(--text-secondary)] hover:underline px-1"
                  @click="() => {
                    const portfolio = holdings.map((ph: any) => `${ph.symbol}:${ph.weight}`).join(',')
                    router.push(`/analyze?symbols=${h.symbol}&portfolio=${encodeURIComponent(portfolio)}`)
                  }">分析</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 仓位分布（简单条形图）-->
    <div v-if="holdings.length" class="card p-4 mb-6">
      <h3 class="text-sm font-semibold text-[var(--text-primary)] mb-4">仓位分布</h3>
      <div class="space-y-2">
        <div v-for="h in holdings" :key="h.id" class="flex items-center gap-3">
          <span class="w-20 text-[12px] font-medium text-[var(--text-primary)] text-right shrink-0">{{ h.symbol }}</span>
          <div class="flex-1 h-5 bg-[var(--bg-overlay)] rounded relative">
            <div class="h-full bg-[var(--brand-primary)] rounded transition-all flex items-center justify-end pr-2"
              :style="weightBarStyle(h.weight)">
              <span class="text-[10px] font-medium text-white">{{ (h.weight * 100).toFixed(1) }}%</span>
            </div>
          </div>
          <span class="w-16 text-[12px] text-right shrink-0" :class="pnlClass(h.pnl_pct)">
            {{ fmtPct(h.pnl_pct) }}
          </span>
        </div>
        <!-- 剩余仓位 -->
        <div class="flex items-center gap-3">
          <span class="w-20 text-[12px] text-[var(--text-tertiary)] text-right shrink-0">现金/空余</span>
          <div class="flex-1 h-5 bg-[var(--bg-overlay)] rounded relative">
            <div class="h-full bg-[var(--bg-elevated)] border border-dashed border-[var(--border-subtle)] rounded transition-all"
              :style="{ width: (remainWeight * 100) + '%' }" />
          </div>
          <span class="w-16 text-[12px] text-[var(--text-tertiary)] text-right shrink-0">
            {{ (remainWeight * 100).toFixed(1) }}%
          </span>
        </div>
      </div>
    </div>

    <!-- 添加/编辑 表单 -->
    <div v-if="showForm" class="fixed inset-0 z-40 flex items-center justify-center bg-black/40"
      @click.self="showForm = false">
      <div class="card p-6 w-full max-w-md mx-4">
        <h3 class="text-base font-semibold mb-4">{{ editingId ? '编辑持仓' : '添加持仓' }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">股票代码 *</label>
            <input v-model="form.symbol" placeholder="如 000629" :disabled="!!editingId"
              class="w-full" :class="editingId ? 'opacity-50' : ''" />
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">股票名称</label>
            <input v-model="form.symbol_name" placeholder="如 西南证券（可选）" class="w-full" />
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">仓位权重 % *</label>
            <input v-model="form.weight" type="number" min="0" max="100" step="0.1"
              placeholder="如 15（表示15%）" class="w-full" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">成本价（元）</label>
              <input v-model="form.cost_price" type="number" step="0.01" placeholder="可选" class="w-full" />
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">持股数量（股）</label>
              <input v-model="form.quantity" type="number" placeholder="可选" class="w-full" />
            </div>
          </div>
          <div>
            <label class="block text-xs text-[var(--text-secondary)] mb-1">备注</label>
            <input v-model="form.note" placeholder="可选" class="w-full" />
          </div>
        </div>
        <div class="flex gap-3 mt-5">
          <ActionButton variant="primary" class="flex-1" @click="submitForm">保存</ActionButton>
          <ActionButton variant="outline" @click="showForm = false; resetForm()">取消</ActionButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
