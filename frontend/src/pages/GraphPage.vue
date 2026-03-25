<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { use } from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import StatusCard from '@/components/ui/StatusCard.vue'
import TagBadge from '@/components/ui/TagBadge.vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import { graphApi } from '@/api/graph'
import { formatPercent, formatNumber, formatDate } from '@/utils/formatters'
import { useThemeStore } from '@/store/theme'
import type { GraphNode, CytoscapeNodeData } from '@/types/graph'

use([LineChart, PieChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const themeStore = useThemeStore()

// Data
const { data: stats, isLoading: isLoadingStats } = useQuery({
  queryKey: ['graph-stats'],
  queryFn: () => graphApi.getStats(),
  staleTime: 60_000,
})

const approvedOnly = ref(false)
const layoutName = ref<'cose' | 'grid'>('cose')
const MAX_DISPLAY_NODES = 300

const { data: nodesData, isLoading: isLoadingNodes, refetch: refetchNodes } = useQuery({
  queryKey: computed(() => ['graph-nodes', approvedOnly.value]),
  queryFn: () => graphApi.listNodes({ limit: MAX_DISPLAY_NODES, approved_only: approvedOnly.value }),
})

// Cytoscape
const cyContainer = ref<HTMLElement | null>(null)
let cy: any = null
const selectedNode = ref<CytoscapeNodeData | null>(null)

function getNodeType(node: GraphNode): CytoscapeNodeData['nodeType'] {
  if (!node.approved) return 'rejected'
  return node.outcome_return > 0 ? 'positive' : 'negative'
}

function getNodeColor(nodeType: string): string {
  if (themeStore.isDark) {
    switch (nodeType) {
      case 'positive': return '#2DC87A'
      case 'negative': return '#F5A623'
      case 'rejected': return '#5C6380'
      default: return '#4F7EFF'
    }
  } else {
    switch (nodeType) {
      case 'positive': return '#0E9E58'
      case 'negative': return '#C47E00'
      case 'rejected': return '#8A90A8'
      default: return '#2B5CE6'
    }
  }
}

async function initCytoscape() {
  if (!cyContainer.value || !nodesData.value?.nodes?.length) return

  const cytoscape = (await import('cytoscape')).default

  if (cy) {
    cy.destroy()
    cy = null
  }

  const nodes = nodesData.value.nodes
  const elements: Array<{ data: Record<string, unknown>; group: 'nodes' | 'edges' }> = []

  nodes.forEach((node) => {
    const nodeType = getNodeType(node)
    elements.push({
      group: 'nodes',
      data: {
        id: node.node_id,
        label: node.symbols.slice(0, 2).join(','),
        approved: node.approved,
        outcomeReturn: node.outcome_return,
        timestamp: node.timestamp,
        symbols: node.symbols,
        nodeType,
      },
    })
  })

  // Create edges between consecutive nodes
  for (let i = 1; i < Math.min(nodes.length, 200); i++) {
    elements.push({
      group: 'edges',
      data: {
        id: `e-${i}`,
        source: nodes[i - 1].node_id,
        target: nodes[i].node_id,
      },
    })
  }

  cy = cytoscape({
    container: cyContainer.value,
    elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': (ele: any) => getNodeColor(ele.data('nodeType')),
          'label': 'data(label)',
          'font-size': '8px',
          'color': themeStore.isDark ? '#9AA0B4' : '#4A5270',
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'width': 16,
          'height': 16,
        } as any,
      },
      {
        selector: 'node[nodeType = "positive"]',
        style: {
          'width': 20,
          'height': 20,
          'border-width': 2,
          'border-color': '#064e3b',
        } as any,
      },
      {
        selector: 'edge',
        style: {
          'width': 0.8,
          'line-color': themeStore.isDark ? '#2A3150' : '#E2E6F0',
          'opacity': 0.5,
          'curve-style': 'bezier',
        } as any,
      },
      {
        selector: ':selected',
        style: {
          'border-width': 3,
          'border-color': '#4F7EFF',
        } as any,
      },
    ],
    layout: {
      name: nodes.length > 200 ? 'grid' : layoutName.value,
      animate: false,
      randomize: layoutName.value === 'cose',
    } as any,
    minZoom: 0.2,
    maxZoom: 3,
  })

  cy.on('tap', 'node', (event: any) => {
    const node = event.target
    selectedNode.value = node.data() as CytoscapeNodeData
  })

  cy.on('tap', (event: any) => {
    if (event.target === cy) {
      selectedNode.value = null
    }
  })
}

watch([nodesData, () => themeStore.isDark], async () => {
  await nextTick()
  initCytoscape()
})

watch(layoutName, () => {
  if (cy) {
    cy.layout({ name: layoutName.value, animate: true }).run()
  }
})

onMounted(async () => {
  await nextTick()
  if (nodesData.value) {
    initCytoscape()
  }
})

onUnmounted(() => {
  if (cy) {
    cy.destroy()
    cy = null
  }
})

// Charts
const trendChartOption = computed(() => {
  const trend = stats.value?.similarity_trend || []
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: themeStore.isDark ? '#1E2333' : '#FFFFFF',
      textStyle: { color: themeStore.isDark ? '#E8EAF0' : '#1A1D2E', fontSize: 11 },
    },
    grid: { left: 40, right: 10, top: 10, bottom: 20 },
    xAxis: {
      type: 'category' as const,
      data: trend.map((t) => t.timestamp?.slice(0, 10) ?? ''),
      axisLabel: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10 },
      axisLine: { lineStyle: { color: themeStore.isDark ? '#3A4560' : '#C8D0E0' } },
    },
    yAxis: {
      type: 'value' as const,
      min: 0,
      max: 1,
      axisLabel: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10, formatter: (v: number) => v.toFixed(1) },
      splitLine: { lineStyle: { color: themeStore.isDark ? '#2A3150' : '#E2E6F0', type: 'dashed' as const } },
    },
    series: [{
      type: 'line' as const,
      data: trend.map((t) => t.avg_similarity),
      smooth: true,
      lineStyle: { color: '#4F7EFF', width: 2 },
      areaStyle: { color: 'rgba(79,126,255,0.1)' },
      itemStyle: { color: '#4F7EFF' },
    }],
  }
})

const distributionChartOption = computed(() => {
  const dist = stats.value?.outcome_distribution
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item' as const,
      backgroundColor: themeStore.isDark ? '#1E2333' : '#FFFFFF',
      textStyle: { color: themeStore.isDark ? '#E8EAF0' : '#1A1D2E', fontSize: 11 },
    },
    series: [{
      type: 'pie' as const,
      radius: ['45%', '72%'],
      center: ['50%', '50%'],
      data: [
        { value: dist?.positive || 0, name: '盈利', itemStyle: { color: '#2DC87A' } },
        { value: dist?.negative || 0, name: '亏损', itemStyle: { color: '#F5474F' } },
      ],
      label: {
        show: true,
        color: themeStore.isDark ? '#9AA0B4' : '#4A5270',
        fontSize: 11,
      },
    }],
  }
})
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto">
    <h1 class="text-xl font-bold text-[var(--text-primary)] mb-6">经验图谱</h1>

    <!-- Stats cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
      <StatusCard title="节点总数" :value="stats?.node_count ?? '--'" />
      <StatusCard title="边总数" :value="stats?.edge_count ?? '--'" />
      <StatusCard
        title="平均准确率"
        :value="stats?.avg_accuracy !== undefined ? `${(stats.avg_accuracy * 100).toFixed(1)}%` : '--'"
      />
      <StatusCard
        title="审批通过率"
        :value="stats?.approval_rate !== undefined ? `${(stats.approval_rate * 100).toFixed(1)}%` : '--'"
      />
    </div>

    <!-- Main layout -->
    <div class="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
      <!-- Left: Cytoscape graph -->
      <div>
        <!-- Controls -->
        <div class="flex items-center gap-3 mb-3">
          <div class="flex items-center gap-1">
            <ActionButton
              :variant="layoutName === 'cose' ? 'primary' : 'outline'"
              size="sm"
              @click="layoutName = 'cose'"
            >
              力导向
            </ActionButton>
            <ActionButton
              :variant="layoutName === 'grid' ? 'primary' : 'outline'"
              size="sm"
              @click="layoutName = 'grid'"
            >
              网格
            </ActionButton>
          </div>
          <label class="flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)]">
            <input
              v-model="approvedOnly"
              type="checkbox"
              class="w-3.5 h-3.5 rounded accent-[var(--brand-primary)]"
            />
            仅显示已批准
          </label>
        </div>

        <!-- Canvas -->
        <div
          ref="cyContainer"
          class="w-full bg-[var(--bg-surface)] rounded-lg border border-[var(--border-subtle)]"
          style="height: calc(100vh - 340px); min-height: 400px"
        >
          <div v-if="isLoadingNodes" class="flex items-center justify-center h-full text-[var(--text-tertiary)] text-sm">
            加载图谱数据中...
          </div>
          <div
            v-else-if="!nodesData?.nodes?.length"
            class="flex flex-col items-center justify-center h-full text-center gap-2"
          >
            <p class="text-[var(--text-tertiary)] text-sm">图谱暂无数据</p>
            <p class="text-[var(--text-tertiary)] text-[12px] max-w-[260px]">图谱会在审批通过后自动积累历史案例，完成第一次审批后刷新查看</p>
          </div>
        </div>

        <!-- Legend -->
        <div class="flex items-center gap-4 mt-2 text-[11px] text-[var(--text-tertiary)]">
          <span class="flex items-center gap-1">
            <span class="w-2.5 h-2.5 rounded-full" style="background: #2DC87A" /> 审批通过 & 盈利
          </span>
          <span class="flex items-center gap-1">
            <span class="w-2.5 h-2.5 rounded-full" style="background: #F5A623" /> 审批通过 & 亏损
          </span>
          <span class="flex items-center gap-1">
            <span class="w-2.5 h-2.5 rounded-full" style="background: #5C6380" /> 未审批通过
          </span>
        </div>
      </div>

      <!-- Right: Charts and details -->
      <div class="space-y-4">
        <!-- Similarity trend -->
        <div class="card p-4">
          <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">
            检索相似度趋势
          </h4>
          <div class="echarts-container" v-if="stats?.similarity_trend?.length">
            <VChart :option="trendChartOption" autoresize style="height: 160px; width: 100%" />
          </div>
          <p v-else class="text-[12px] text-[var(--text-tertiary)] py-8 text-center">
            {{ (stats?.node_count ?? 0) < 5 ? '数据不足，请先完成更多决策' : '暂无趋势数据' }}
          </p>
        </div>

        <!-- Distribution -->
        <div class="card p-4">
          <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">
            结果分布
          </h4>
          <div class="echarts-container" v-if="stats?.outcome_distribution">
            <VChart :option="distributionChartOption" autoresize style="height: 180px; width: 100%" />
          </div>
          <p v-else class="text-[12px] text-[var(--text-tertiary)] py-8 text-center">暂无分布数据</p>
        </div>

        <!-- Selected node detail -->
        <div v-if="selectedNode" class="card p-4">
          <h4 class="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3">
            节点详情
          </h4>
          <div class="space-y-2 text-[12px]">
            <div class="flex justify-between">
              <span class="text-[var(--text-tertiary)]">ID</span>
              <span class="text-[var(--text-primary)] tabular-nums">{{ (selectedNode.id as string).slice(0, 8) }}...</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-tertiary)]">时间</span>
              <span class="text-[var(--text-primary)]">{{ formatDate(selectedNode.timestamp) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-tertiary)]">状态</span>
              <TagBadge
                :variant="selectedNode.approved ? 'approved' : 'rejected'"
                :label="selectedNode.approved ? '已通过' : '未通过'"
                size="sm"
              />
            </div>
            <div class="flex justify-between">
              <span class="text-[var(--text-tertiary)]">收益率</span>
              <span
                class="tabular-nums font-medium"
                :class="selectedNode.outcomeReturn >= 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'"
              >
                {{ formatPercent(selectedNode.outcomeReturn) }}
              </span>
            </div>
            <div>
              <span class="text-[var(--text-tertiary)]">涉及标的</span>
              <div class="flex flex-wrap gap-1 mt-1">
                <TagBadge
                  v-for="s in selectedNode.symbols"
                  :key="s"
                  variant="info"
                  :label="s"
                  size="sm"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
