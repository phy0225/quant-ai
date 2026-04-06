<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSidebarStore } from '@/store/sidebar'
import { useThemeStore } from '@/store/theme'

const route = useRoute()
const router = useRouter()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()

type NavItem = {
  path: string
  label: string
  aliases?: string[]
}

type NavSection = {
  id: string
  label: string
  shortLabel: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    id: 'assets',
    label: '资产监控',
    shortLabel: '监',
    items: [
      { path: '/dashboard', label: '总览' },
      { path: '/portfolio', label: '持仓' },
    ],
  },
  {
    id: 'research',
    label: '策略研究',
    shortLabel: '研',
    items: [
      { path: '/lab', label: 'AI实验室' },
      { path: '/factors', label: '因子' },
      { path: '/graph', label: '图谱' },
    ],
  },
  {
    id: 'dev',
    label: '开发回测',
    shortLabel: '测',
    items: [
      { path: '/strategy', label: '策略' },
      { path: '/backtest', label: '回测' },
      { path: '/rules', label: '规则' },
    ],
  },
  {
    id: 'decision',
    label: '决策中心',
    shortLabel: '决',
    items: [
      { path: '/analyze', label: '正式触发' },
      { path: '/decisions', label: '列表', aliases: ['/decisions'] },
      { path: '/approvals', label: '审批', aliases: ['/approvals'] },
    ],
  },
]

function isActive(item: NavItem) {
  const candidates = [item.path, ...(item.aliases ?? [])]
  return candidates.some((candidate) => {
    if (candidate === '/decisions' || candidate === '/approvals') {
      return route.path.startsWith(candidate)
    }
    return route.path === candidate
  })
}

function isSectionActive(section: NavSection) {
  return section.items.some((item) => isActive(item))
}

const expandedSections = ref<string[]>([])

function ensureActiveSectionExpanded() {
  const activeSection = navSections.find((section) => isSectionActive(section))
  if (!activeSection) return
  if (!expandedSections.value.includes(activeSection.id)) {
    expandedSections.value = [activeSection.id]
  }
}

function isSectionExpanded(section: NavSection) {
  if (sidebarStore.isCollapsed) return false
  return expandedSections.value.includes(section.id)
}

function toggleSection(section: NavSection) {
  if (sidebarStore.isCollapsed) {
    return
  }

  expandedSections.value = expandedSections.value.includes(section.id) ? [] : [section.id]
}

watch(
  () => route.path,
  () => {
    ensureActiveSectionExpanded()
  },
  { immediate: true }
)

const sidebarWidth = computed(() => (sidebarStore.isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'))
</script>

<template>
  <aside
    class="fixed left-0 top-0 h-screen bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] z-40 flex flex-col transition-all duration-200 overflow-hidden"
    :style="{ width: sidebarWidth }"
  >
    <div class="flex items-center h-14 px-4 border-b border-[var(--border-subtle)]">
      <div class="w-7 h-7 rounded-lg bg-[var(--brand-primary)] text-white text-xs font-bold flex items-center justify-center">AI</div>
      <span v-show="!sidebarStore.isCollapsed" class="ml-2 text-sm font-semibold">Quant AI</span>
    </div>

    <nav class="flex-1 py-3 px-2 space-y-3 overflow-y-auto">
      <div v-for="section in navSections" :key="section.id" class="space-y-1">
        <button
          class="w-full flex items-center justify-between rounded-lg px-3 py-2 text-left transition-colors"
          :class="isSectionActive(section)
            ? 'bg-[var(--brand-primary-subtle)] text-[var(--brand-primary)]'
            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'"
          @click="toggleSection(section)"
        >
          <span class="text-[14px] font-bold tracking-[0.03em]" :class="sidebarStore.isCollapsed ? 'w-full text-center' : ''">
            <span v-show="!sidebarStore.isCollapsed">{{ section.label }}</span>
            <span v-show="sidebarStore.isCollapsed">{{ section.shortLabel }}</span>
          </span>
          <span
            v-show="!sidebarStore.isCollapsed"
            class="text-sm transition-transform duration-200"
            :class="isSectionExpanded(section) ? 'rotate-90' : ''"
          >
            >
          </span>
        </button>

        <div v-show="isSectionExpanded(section)" class="space-y-1 pl-2">
          <button
            v-for="item in section.items"
            :key="`${section.id}-${item.label}`"
            class="w-full text-left px-3 py-2 rounded text-[13px] transition-colors"
            :class="isActive(item)
              ? 'bg-[var(--brand-primary-subtle)] text-[var(--brand-primary)]'
              : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'"
            @click="router.push(item.path)"
          >
            {{ item.label }}
          </button>
        </div>
      </div>
    </nav>

    <div class="p-2 border-t border-[var(--border-subtle)] space-y-1">
      <button
        class="w-full px-3 py-2 rounded text-left text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        @click="themeStore.toggleTheme()"
      >
        <span v-show="!sidebarStore.isCollapsed">{{ themeStore.isDark ? '亮色模式' : '暗色模式' }}</span>
        <span v-show="sidebarStore.isCollapsed">{{ themeStore.isDark ? '亮' : '暗' }}</span>
      </button>
      <button
        class="w-full px-3 py-2 rounded text-left text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
        @click="sidebarStore.toggle()"
      >
        <span v-show="!sidebarStore.isCollapsed">折叠</span>
        <span v-show="sidebarStore.isCollapsed">展</span>
      </button>
    </div>
  </aside>
</template>
