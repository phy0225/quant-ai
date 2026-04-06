<script setup lang="ts">
import cytoscape from 'cytoscape'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { graphApi } from '@/api/graph'
import type { GraphEdge, GraphNode, GraphSearchResultItem, GraphStats } from '@/types/graph'

const loading = ref(false)
const error = ref('')
const stats = ref<GraphStats | null>(null)
const nodes = ref<GraphNode[]>([])
const edges = ref<GraphEdge[]>([])
const approvedOnly = ref(false)
const selectedNodeId = ref('')
const enabledNodeTypes = ref<string[]>(['experience', 'symbol', 'market_regime', 'factor'])
const enabledEdgeTypes = ref<string[]>(['shared_symbols', 'same_mode', 'same_market_regime', 'has_symbol', 'in_market_regime', 'has_factor'])
const searchInput = ref('')
const searching = ref(false)
const searchResults = ref<GraphSearchResultItem[]>([])
const expandNeighbors = ref(true)
const graphContainer = ref<HTMLDivElement | null>(null)
let cy: cytoscape.Core | null = null

const modeLabelMap: Record<string, string> = {
  targeted: '定向分析',
  rebalance: '调仓分析',
}

function normalizeMode(mode?: string | null) {
  return mode ? modeLabelMap[mode] || mode : '未定义'
}

function formatPercent(value?: number | null, digits = 1) {
  if (value == null) return '--'
  return `${(value * 100).toFixed(digits)}%`
}

function getFactorCount(node: GraphNode) {
  if (!node.factor_snapshot || typeof node.factor_snapshot !== 'object') return 0
  return Object.keys(node.factor_snapshot).length
}

function getNodeLabel(node: GraphNode) {
  if (node.node_type === 'symbol') return node.display_label || node.symbols?.[0] || '标的'
  if (node.node_type === 'market_regime') return node.display_label || node.market_regime || '市场状态'
  if (node.node_type === 'factor') return node.display_label || node.entity_key || '因子'
  const symbols = node.symbols?.slice(0, 2).join(', ') || '无标的'
  return `${symbols}\n${normalizeMode(node.mode)}`
}

function getNodeTypeLabel(nodeType?: string | null) {
  if (nodeType === 'symbol') return '标的'
  if (nodeType === 'market_regime') return '市场状态'
  if (nodeType === 'factor') return '因子'
  return '经验案例'
}

function getEdgeLabel(edge: GraphEdge) {
  const labels: string[] = []
  if (edge.relation_type === 'has_symbol') return `关联标的 ${edge.shared_symbols[0] || ''}`.trim()
  if (edge.relation_type === 'in_market_regime') return `归属市场状态 ${edge.shared_market_regime || ''}`.trim()
  if (edge.relation_type === 'has_factor') return '关联因子'
  if (edge.shared_symbols?.length) {
    labels.push(`共标的 ${edge.shared_symbols.slice(0, 2).join(', ')}`)
  }
  if (edge.relation_type.includes('same_mode')) {
    labels.push('同模式')
  }
  if (edge.shared_market_regime) {
    labels.push(`同市场状态 ${edge.shared_market_regime}`)
  }
  return labels.join(' / ') || edge.relation_type
}

const visibleNodes = computed(() =>
  nodes.value.filter((node) => enabledNodeTypes.value.includes(node.node_type || 'experience'))
)

const graphEdges = computed(() => {
  const visibleIds = new Set(visibleNodes.value.map((node) => node.node_id))
  return edges.value.filter(
    (edge) =>
      enabledEdgeTypes.value.includes(edge.relation_type) &&
      visibleIds.has(edge.source) &&
      visibleIds.has(edge.target)
  )
})

const selectedNode = computed(() =>
  visibleNodes.value.find((node) => node.node_id === selectedNodeId.value) || visibleNodes.value[0] || null
)

const relatedEdges = computed(() => {
  if (!selectedNode.value) return []
  return graphEdges.value.filter(
    (edge) => edge.source === selectedNode.value?.node_id || edge.target === selectedNode.value?.node_id
  )
})

const neighborNodes = computed(() => {
  if (!selectedNode.value) return []

  return relatedEdges.value
    .map((edge) => {
      const neighborId = edge.source === selectedNode.value?.node_id ? edge.target : edge.source
      const neighbor = visibleNodes.value.find((node) => node.node_id === neighborId)
      if (!neighbor) return null
      return {
        node: neighbor,
        edge,
      }
    })
    .filter((item): item is { node: GraphNode; edge: GraphEdge } => Boolean(item))
    .sort((left, right) => right.edge.strength - left.edge.strength)
})

const graphSummaryText = computed(() => {
  if (!nodes.value.length) return '当前还没有沉淀出可视化关系网络。'
  return '当前画布展示的是案例节点、标的节点与市场状态节点共同组成的经验图谱，可用于查看案例归属与相似关系。'
})

const visibleSearchResults = computed(() =>
  searchResults.value.filter((item) => item.node_id)
)

const highlightedNodeIds = computed(() => visibleSearchResults.value.map((item) => item.node_id))

const focusedNodeIds = computed(() => {
  if (!expandNeighbors.value || !selectedNode.value) {
    return new Set(visibleNodes.value.map((node) => node.node_id))
  }

  const ids = new Set<string>([selectedNode.value.node_id])
  for (const edge of graphEdges.value) {
    if (edge.source === selectedNode.value.node_id) ids.add(edge.target)
    if (edge.target === selectedNode.value.node_id) ids.add(edge.source)
  }
  return ids
})

const renderedNodes = computed(() =>
  visibleNodes.value.filter((node) => focusedNodeIds.value.has(node.node_id))
)

const renderedEdges = computed(() =>
  graphEdges.value.filter(
    (edge) => focusedNodeIds.value.has(edge.source) && focusedNodeIds.value.has(edge.target)
  )
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [s, n] = await Promise.all([
      graphApi.getStats(),
      graphApi.getNetwork({ limit: 100, approved_only: approvedOnly.value }),
    ])
    stats.value = s
    nodes.value = n.nodes || []
    edges.value = n.edges || []
    if (!visibleNodes.value.find((node) => node.node_id === selectedNodeId.value)) {
      selectedNodeId.value = visibleNodes.value[0]?.node_id || ''
    }
    await nextTick()
    renderGraph()
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载图谱数据失败。'
  } finally {
    loading.value = false
  }
}

async function runSearch() {
  const symbols = searchInput.value
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)

  if (!symbols.length) {
    searchResults.value = []
    return
  }

  searching.value = true
  try {
    searchResults.value = await graphApi.search({ symbols, top_k: 6 })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '搜索相似案例失败。'
  } finally {
    searching.value = false
  }
}

function focusSelectedNode() {
  if (!cy || !selectedNode.value) return
  const node = cy.getElementById(selectedNode.value.node_id)
  if (!node || node.empty()) return
  cy.elements().removeClass('is-selected')
  node.addClass('is-selected')
  cy.animate({
    fit: {
      eles: node.closedNeighborhood(),
      padding: 80,
    },
    duration: 250,
  })
}

function renderGraph() {
  if (!graphContainer.value) return

  cy?.destroy()

  const elements = [
    ...renderedNodes.value.map((node) => ({
      data: {
        id: node.node_id,
        label: getNodeLabel(node),
        approved: node.approved,
        outcomeReturn: node.outcome_return,
        mode: normalizeMode(node.mode),
        nodeType: node.node_type || 'experience',
        isHighlighted: highlightedNodeIds.value.includes(node.node_id),
      },
    })),
    ...renderedEdges.value.map((edge) => ({
      data: {
        id: edge.edge_id,
        source: edge.source,
        target: edge.target,
        label: getEdgeLabel(edge),
        strength: edge.strength,
        isHighlighted: highlightedNodeIds.value.includes(edge.source) || highlightedNodeIds.value.includes(edge.target),
      },
    })),
  ]

  cy = cytoscape({
    container: graphContainer.value,
    elements,
    layout: {
      name: 'cose',
      animate: false,
      fit: true,
      padding: 24,
      nodeRepulsion: 100000,
      idealEdgeLength: 140,
      edgeElasticity: 80,
    },
    style: [
      {
        selector: 'node',
        style: {
          label: 'data(label)',
          'text-wrap': 'wrap',
          'text-max-width': 120,
          'font-size': 11,
          'text-valign': 'center',
          'text-halign': 'center',
          color: '#E8EAF0',
          'background-color': (ele) => {
            const nodeType = String(ele.data('nodeType') || 'experience')
            if (nodeType === 'symbol') return '#2563EB'
            if (nodeType === 'market_regime') return '#7C3AED'
            if (nodeType === 'factor') return '#D97706'
            const outcomeReturn = Number(ele.data('outcomeReturn') || 0)
            const approved = Boolean(ele.data('approved'))
            if (!approved) return '#6B7280'
            return outcomeReturn >= 0 ? '#16A34A' : '#DC2626'
          },
          width: (ele) => {
            const nodeType = String(ele.data('nodeType') || 'experience')
            return nodeType === 'experience' ? 58 : 44
          },
          height: (ele) => {
            const nodeType = String(ele.data('nodeType') || 'experience')
            return nodeType === 'experience' ? 58 : 44
          },
          shape: (ele) => {
            const nodeType = String(ele.data('nodeType') || 'experience')
            if (nodeType === 'symbol') return 'round-rectangle'
            if (nodeType === 'market_regime') return 'diamond'
            if (nodeType === 'factor') return 'hexagon'
            return 'ellipse'
          },
          'border-width': 2,
          'border-color': (ele) => (Boolean(ele.data('isHighlighted')) ? '#FACC15' : '#E5E7EB'),
        },
      },
      {
        selector: 'edge',
        style: {
          width: (ele) => Math.max(1.5, Number(ele.data('strength') || 0) * 4),
          'line-color': (ele) => (Boolean(ele.data('isHighlighted')) ? '#FACC15' : '#4F7EFF'),
          opacity: (ele) => (Boolean(ele.data('isHighlighted')) ? 0.9 : 0.45),
          'curve-style': 'bezier',
          label: 'data(label)',
          'font-size': 9,
          color: '#9AA0B4',
          'text-background-color': '#171B26',
          'text-background-opacity': 0.7,
          'text-background-padding': 2,
        },
      },
      {
        selector: '.is-selected',
        style: {
          'border-color': '#F8FAFC',
          'border-width': 4,
          'overlay-color': '#93C5FD',
          'overlay-opacity': 0.18,
          'overlay-padding': 8,
        },
      },
    ],
  })

  cy.on('tap', 'node', (event) => {
    selectedNodeId.value = event.target.id()
  })

  focusSelectedNode()
}

watch(selectedNodeId, () => {
  focusSelectedNode()
})

watch(approvedOnly, () => {
  load()
})

watch([enabledNodeTypes, enabledEdgeTypes], async () => {
  if (!visibleNodes.value.find((node) => node.node_id === selectedNodeId.value)) {
    selectedNodeId.value = visibleNodes.value[0]?.node_id || ''
  }
  await nextTick()
  renderGraph()
}, { deep: true })

watch([expandNeighbors, highlightedNodeIds], async () => {
  await nextTick()
  renderGraph()
}, { deep: true })

onMounted(load)

onBeforeUnmount(() => {
  cy?.destroy()
  cy = null
})
</script>

<template>
  <div class="p-6 max-w-[1440px] mx-auto space-y-5">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-[var(--text-primary)]">经验图谱</h1>
        <p class="mt-1 text-sm text-[var(--text-secondary)]">{{ graphSummaryText }}</p>
      </div>
      <div class="flex items-center gap-3">
        <label class="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input v-model="approvedOnly" type="checkbox" />
          仅看已审批
        </label>
        <button class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm" @click="load">刷新</button>
      </div>
    </div>

    <div v-if="loading" class="card p-4 text-sm text-[var(--text-tertiary)]">加载中...</div>
    <div v-else-if="error" class="card p-4 text-sm text-[var(--negative)]">{{ error }}</div>
    <template v-else>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">节点数</p><p class="text-2xl font-semibold">{{ stats?.node_count ?? 0 }}</p></div>
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">连边数</p><p class="text-2xl font-semibold">{{ graphEdges.length }}</p></div>
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">平均准确率</p><p class="text-2xl font-semibold">{{ stats ? `${(stats.avg_accuracy * 100).toFixed(1)}%` : '--' }}</p></div>
        <div class="card p-4"><p class="text-xs text-[var(--text-secondary)]">审批通过率</p><p class="text-2xl font-semibold">{{ stats ? `${(stats.approval_rate * 100).toFixed(1)}%` : '--' }}</p></div>
      </div>

      <div class="card p-4 space-y-3">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h2 class="font-semibold">相似案例搜索</h2>
            <p class="text-xs text-[var(--text-secondary)]">输入标的代码，定位历史相似经验节点。</p>
          </div>
          <div class="flex w-full max-w-[480px] gap-2">
            <input v-model="searchInput" placeholder="例如 600519,300750" @keydown.enter.prevent="runSearch" />
            <button class="px-3 py-2 rounded bg-[var(--brand-primary)] text-white text-sm whitespace-nowrap" @click="runSearch">
              {{ searching ? '搜索中...' : '搜索' }}
            </button>
          </div>
        </div>
        <div v-if="visibleSearchResults.length" class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <button
            v-for="item in visibleSearchResults"
            :key="item.node_id"
            class="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-left hover:border-[var(--border-focus)]"
            @click="selectedNodeId = item.node_id"
          >
            <div class="text-sm font-medium text-[var(--text-primary)]">{{ item.node_id.slice(0, 8) }}</div>
            <div class="mt-1 text-xs text-[var(--text-secondary)]">相似度：{{ ((item.similarity_score || 0) * 100).toFixed(1) }}%</div>
            <div class="mt-1 text-xs text-[var(--text-secondary)]">结果收益：{{ formatPercent(item.outcome_return ?? null, 2) }}</div>
          </button>
        </div>
        <p v-else class="text-sm text-[var(--text-tertiary)]">输入标的后可查看相似历史案例。</p>
        <div class="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
          <span class="inline-block h-3 w-3 rounded-full bg-yellow-400" />
          搜索结果会在图中高亮显示
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div class="card p-4 space-y-3">
          <h2 class="font-semibold">节点图例</h2>
          <div class="flex flex-wrap gap-3 text-sm">
            <label class="inline-flex items-center gap-2">
              <input v-model="enabledNodeTypes" type="checkbox" value="experience" />
              <span class="inline-flex items-center gap-2"><span class="inline-block h-3 w-3 rounded-full bg-green-600" />经验案例</span>
            </label>
            <label class="inline-flex items-center gap-2">
              <input v-model="enabledNodeTypes" type="checkbox" value="symbol" />
              <span class="inline-flex items-center gap-2"><span class="inline-block h-3 w-3 rounded bg-blue-600" />标的</span>
            </label>
            <label class="inline-flex items-center gap-2">
              <input v-model="enabledNodeTypes" type="checkbox" value="market_regime" />
              <span class="inline-flex items-center gap-2"><span class="inline-block h-3 w-3 rotate-45 bg-violet-600" />市场状态</span>
            </label>
            <label class="inline-flex items-center gap-2">
              <input v-model="enabledNodeTypes" type="checkbox" value="factor" />
              <span class="inline-flex items-center gap-2"><span class="inline-block h-3 w-3 bg-amber-600" />因子</span>
            </label>
          </div>
        </div>

        <div class="card p-4 space-y-3">
          <h2 class="font-semibold">关系筛选</h2>
          <div class="flex flex-wrap gap-3 text-sm">
            <label class="inline-flex items-center gap-2"><input v-model="enabledEdgeTypes" type="checkbox" value="shared_symbols" />共标的</label>
            <label class="inline-flex items-center gap-2"><input v-model="enabledEdgeTypes" type="checkbox" value="same_mode" />同模式</label>
            <label class="inline-flex items-center gap-2"><input v-model="enabledEdgeTypes" type="checkbox" value="same_market_regime" />同市场状态</label>
            <label class="inline-flex items-center gap-2"><input v-model="enabledEdgeTypes" type="checkbox" value="has_symbol" />案例-标的</label>
            <label class="inline-flex items-center gap-2"><input v-model="enabledEdgeTypes" type="checkbox" value="in_market_regime" />案例-市场状态</label>
            <label class="inline-flex items-center gap-2"><input v-model="enabledEdgeTypes" type="checkbox" value="has_factor" />案例-因子</label>
          </div>
          <label class="inline-flex items-center gap-2 text-sm">
            <input v-model="expandNeighbors" type="checkbox" />
            聚焦显示当前节点及其一阶邻居
          </label>
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_360px] gap-5">
        <div class="card p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="font-semibold">关系画布</h2>
              <p class="text-xs text-[var(--text-secondary)]">已包含案例、标的、市场状态和因子四类节点，并支持关系过滤、搜索定位和邻居聚焦。</p>
            </div>
            <span class="text-xs text-[var(--text-tertiary)]">绿/红/灰为案例收益表现，蓝色为标的，紫色为市场状态，橙色为因子</span>
          </div>
          <div ref="graphContainer" class="graph-canvas rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]" />
        </div>

        <div class="space-y-5">
          <div class="card p-4 space-y-3">
            <h2 class="font-semibold">节点详情</h2>
            <template v-if="selectedNode">
              <div class="space-y-2 text-sm">
                <div>节点类型：{{ getNodeTypeLabel(selectedNode.node_type) }}</div>
                <div v-if="selectedNode.display_label">显示名称：{{ selectedNode.display_label }}</div>
                <div>节点编号：<span class="font-mono text-xs">{{ selectedNode.node_id }}</span></div>
                <div v-if="selectedNode.node_type === 'experience'">分析模式：{{ normalizeMode(selectedNode.mode) }}</div>
                <div v-if="selectedNode.node_type === 'experience'">审批结果：{{ selectedNode.approved ? '已通过' : '未通过' }}</div>
                <div>市场状态：{{ selectedNode.market_regime || '--' }}</div>
                <div>标的代码：{{ selectedNode.symbols.join(', ') || '--' }}</div>
                <div v-if="selectedNode.node_type === 'experience'">因子快照字段数：{{ getFactorCount(selectedNode) }}</div>
                <div v-if="selectedNode.node_type === 'experience'">结果收益：{{ formatPercent(selectedNode.outcome_return, 2) }}</div>
                <div v-if="selectedNode.node_type === 'experience'">结果夏普：{{ selectedNode.outcome_sharpe ?? '--' }}</div>
                <div v-if="selectedNode.node_type === 'factor'">因子标识：{{ selectedNode.entity_key || '--' }}</div>
              </div>
            </template>
            <p v-else class="text-sm text-[var(--text-tertiary)]">暂无可查看的图谱节点。</p>
          </div>

          <div class="card p-4 space-y-3">
            <div class="flex items-center justify-between">
              <h2 class="font-semibold">邻居节点</h2>
              <span class="text-xs text-[var(--text-tertiary)]">{{ neighborNodes.length }} 个关联节点</span>
            </div>
            <div v-if="neighborNodes.length" class="space-y-2">
              <button
                v-for="item in neighborNodes"
                :key="`${selectedNode?.node_id}-${item.node.node_id}-${item.edge.edge_id}`"
                class="w-full rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-3 text-left hover:border-[var(--border-focus)]"
                @click="selectedNodeId = item.node.node_id"
              >
                <div class="flex items-center justify-between gap-3">
                  <div>
                    <div class="text-sm font-medium text-[var(--text-primary)]">{{ item.node.display_label || getNodeLabel(item.node) }}</div>
                    <div class="mt-1 text-xs text-[var(--text-secondary)]">{{ getNodeTypeLabel(item.node.node_type) }}</div>
                  </div>
                  <span class="text-xs text-[var(--brand-primary)]">切换中心</span>
                </div>
                <div class="mt-2 text-xs text-[var(--text-secondary)]">{{ getEdgeLabel(item.edge) }}</div>
                <div class="mt-1 text-xs text-[var(--text-tertiary)]">关系强度：{{ item.edge.strength.toFixed(2) }}</div>
              </button>
            </div>
            <p v-else class="text-sm text-[var(--text-tertiary)]">当前节点暂无可切换的邻居节点。</p>
          </div>
        </div>
      </div>

      <div class="card p-4">
        <h2 class="font-semibold mb-2">图谱节点列表</h2>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left border-b border-[var(--border-subtle)]">
              <th class="py-2">节点编号</th>
              <th class="py-2">类型</th>
              <th class="py-2">模式</th>
              <th class="py-2">市场状态</th>
              <th class="py-2">因子数</th>
              <th class="py-2">结果收益</th>
              <th class="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in visibleNodes" :key="row.node_id" class="border-b border-[var(--border-subtle)]">
              <td class="py-2 font-mono text-xs">{{ row.node_id.slice(0, 8) }}</td>
              <td class="py-2">{{ getNodeTypeLabel(row.node_type) }}</td>
              <td class="py-2">{{ row.node_type === 'experience' ? normalizeMode(row.mode) : '--' }}</td>
              <td class="py-2">{{ row.market_regime || '--' }}</td>
              <td class="py-2">{{ row.node_type === 'experience' ? getFactorCount(row) : '--' }}</td>
              <td class="py-2">{{ row.node_type === 'experience' ? formatPercent(row.outcome_return, 2) : '--' }}</td>
              <td class="py-2">
                <button class="text-[var(--brand-primary)] hover:underline" @click="selectedNodeId = row.node_id">查看关系</button>
              </td>
            </tr>
            <tr v-if="!visibleNodes.length">
              <td class="py-3 text-[var(--text-tertiary)]" colspan="7">当前筛选条件下暂无图谱节点。</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card p-4 text-sm text-[var(--text-secondary)]">
        当前页面已补齐“图谱可视化”能力，但关系边仍是基于现有节点数据推导的经验关系，不等同于完整知识图谱。若要完全符合知识图谱语义，后端还需要补充显式边模型与网络接口。
      </div>
    </template>
  </div>
</template>

<style scoped>
.graph-canvas {
  min-height: 560px;
}
</style>
