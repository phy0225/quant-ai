<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSidebarStore } from '@/store/sidebar'
import { useThemeStore } from '@/store/theme'

const route = useRoute()
const router = useRouter()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()

const navItems = [
  { path: '/dashboard', label: '总览' },
  { path: '/analyze', label: '触发分析' },
  { path: '/decisions', label: '决策' },
  { path: '/approvals', label: '审批' },
  { path: '/portfolio', label: '持仓' },
  { path: '/factors', label: '因子' },
  { path: '/strategy', label: '策略' },
  { path: '/rules', label: '规则' },
  { path: '/backtest', label: '回测' },
  { path: '/graph', label: '图谱' },
]

function isActive(path: string) {
  if (path === '/decisions') return route.path.startsWith('/decisions')
  if (path === '/approvals') return route.path.startsWith('/approvals')
  return route.path === path
}

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

    <nav class="flex-1 py-2 px-2 space-y-1">
      <button
        v-for="item in navItems"
        :key="item.path"
        class="w-full text-left px-3 py-2 rounded text-[13px] transition-colors"
        :class="isActive(item.path)
          ? 'bg-[var(--brand-primary-subtle)] text-[var(--brand-primary)]'
          : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'"
        @click="router.push(item.path)"
      >
        <span v-show="!sidebarStore.isCollapsed">{{ item.label }}</span>
        <span v-show="sidebarStore.isCollapsed">{{ item.label.slice(0, 1) }}</span>
      </button>
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

