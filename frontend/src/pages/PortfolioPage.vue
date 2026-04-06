<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { decisionsApi } from '@/api/decisions'
import { portfolioApi } from '@/api/portfolio'
import type { PortfolioHolding, PortfolioSummary, RebalanceOrder } from '@/types/portfolio'

const router = useRouter()

const loading = ref(false)
const holdings = ref<PortfolioHolding[]>([])
const summary = ref<PortfolioSummary | null>(null)
const orders = ref<RebalanceOrder[]>([])
const latestRebalanceDecisionId = ref('')

const stockHoldings = computed(() =>
  holdings.value.filter((h) => /^\d{6}$/.test(h.symbol))
)

async function loadPortfolio() {
  const [h, s] = await Promise.all([portfolioApi.list(), portfolioApi.summary()])
  holdings.value = h.holdings
  summary.value = s
}

async function loadLatestOrders() {
  const list = await decisionsApi.list({ page: 1, page_size: 30 })
  const latest = list.items.find((item) => item.mode === 'rebalance' && item.status === 'completed')
  if (!latest) {
    orders.value = []
    latestRebalanceDecisionId.value = ''
    return
  }
  latestRebalanceDecisionId.value = latest.id
  orders.value = (await decisionsApi.getOrders(latest.id)).map((row) => ({
    symbol: row.symbol,
    action: row.action,
    current_weight: row.current_weight,
    target_weight: row.target_weight,
    weight_delta: row.weight_delta,
  }))
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadPortfolio(), loadLatestOrders()])
  } finally {
    loading.value = false
  }
}

async function refreshPrices() {
  await portfolioApi.refreshPrices()
  await loadPortfolio()
}

onMounted(refreshAll)
</script>

<template>
  <div class="p-6 max-w-[1250px] mx-auto space-y-5">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-[var(--text-primary)]">持仓管理</h1>
      <div class="flex gap-2">
        <button class="px-3 py-1.5 rounded border text-sm" @click="refreshPrices">刷新价格</button>
        <button class="px-3 py-1.5 rounded bg-[var(--brand-primary)] text-white text-sm" @click="refreshAll">刷新</button>
      </div>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">股票持仓数量</p>
        <p class="text-2xl font-semibold">{{ stockHoldings.length }}</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">总权重</p>
        <p class="text-2xl font-semibold">{{ ((summary?.total_weight || 0) * 100).toFixed(1) }}%</p>
      </div>
      <div class="card p-4">
        <p class="text-xs text-[var(--text-secondary)]">组合浮盈</p>
        <p class="text-2xl font-semibold">{{ ((summary?.avg_pnl_pct || 0) * 100).toFixed(2) }}%</p>
      </div>
    </div>

    <div class="card p-4">
      <h2 class="font-semibold mb-2">当前持仓（股票执行）</h2>
      <p v-if="loading" class="text-sm text-[var(--text-tertiary)]">加载中...</p>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">代码</th>
            <th class="py-2">名称</th>
            <th class="py-2">权重</th>
            <th class="py-2">浮盈</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in stockHoldings" :key="h.id" class="border-b border-[var(--border-subtle)]">
            <td class="py-2">{{ h.symbol }}</td>
            <td class="py-2">{{ h.symbol_name || '--' }}</td>
            <td class="py-2">{{ (h.weight * 100).toFixed(1) }}%</td>
            <td class="py-2">{{ h.pnl_pct == null ? '--' : `${(h.pnl_pct * 100).toFixed(2)}%` }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card p-4">
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-semibold">最近调仓订单</h2>
        <button
          v-if="latestRebalanceDecisionId"
          class="text-sm text-[var(--brand-primary)] hover:underline"
          @click="router.push(`/decisions/${latestRebalanceDecisionId}`)"
        >
          查看决策
        </button>
      </div>
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left border-b border-[var(--border-subtle)]">
            <th class="py-2">代码</th>
            <th class="py-2">动作</th>
            <th class="py-2">当前权重</th>
            <th class="py-2">目标权重</th>
            <th class="py-2">变化幅度</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="order in orders" :key="order.symbol" class="border-b border-[var(--border-subtle)]">
            <td class="py-2">{{ order.symbol }}</td>
            <td class="py-2">{{ order.action === 'buy' ? '买入' : order.action === 'sell' ? '卖出' : '持有' }}</td>
            <td class="py-2">{{ (order.current_weight * 100).toFixed(1) }}%</td>
            <td class="py-2">{{ (order.target_weight * 100).toFixed(1) }}%</td>
            <td class="py-2">{{ (order.weight_delta * 100).toFixed(1) }}%</td>
          </tr>
          <tr v-if="!orders.length">
            <td class="py-3 text-[var(--text-tertiary)]" colspan="5">暂无调仓订单</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
