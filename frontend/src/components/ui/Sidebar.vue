<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSidebarStore } from '@/store/sidebar'
import { useThemeStore } from '@/store/theme'

const route = useRoute()
const router = useRouter()
const sidebarStore = useSidebarStore()
const themeStore = useThemeStore()

interface NavItem {
  path: string
  label: string
  icon: string
}

const navItems: NavItem[] = [
  { path: '/dashboard',  label: '总览',   icon: 'dashboard'  },  // 1. 看整体状态
  { path: '/portfolio',  label: '持仓',   icon: 'portfolio'  },  // 2. 查当前持仓
  { path: '/analyze',    label: '触发分析', icon: 'analyze'  },  // 3. 发起 Agent 分析
  { path: '/approvals',  label: '审批',   icon: 'approvals'  },  // 4. 审批决策
  { path: '/rules',      label: '规则',   icon: 'rules'      },  // 5. 风控规则
  { path: '/backtest',   label: '回测',   icon: 'backtest'   },  // 6. 策略回测
  { path: '/graph',      label: '图谱',   icon: 'graph'      },  // 7. 经验图谱
]

const isActive = (path: string) => {
  if (path === '/approvals') return route.path.startsWith('/approvals')
  if (path === '/analyze') return route.path === '/analyze' || route.path.startsWith('/decisions/')
  return route.path === path
}

watch(() => route.path, (path) => {
  sidebarStore.setActive(path)
}, { immediate: true })

const sidebarWidth = computed(() =>
  sidebarStore.isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'
)
</script>

<template>
  <aside
    class="fixed left-0 top-0 h-screen bg-[var(--bg-surface)] border-r border-[var(--border-subtle)] z-40 flex flex-col transition-all duration-200 overflow-hidden"
    :style="{ width: sidebarWidth }"
  >
    <!-- Logo -->
    <div class="flex items-center h-14 px-4 border-b border-[var(--border-subtle)]">
      <div class="flex items-center gap-2 overflow-hidden">
        <div class="flex-shrink-0 w-7 h-7 rounded-lg bg-[var(--brand-primary)] flex items-center justify-center">
          <span class="text-white text-xs font-bold">AI</span>
        </div>
        <span
          v-show="!sidebarStore.isCollapsed"
          class="text-sm font-semibold text-[var(--text-primary)] whitespace-nowrap"
        >
          Quant AI
        </span>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 py-2 px-2 space-y-0.5">
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
          <template v-if="item.icon === 'dashboard'">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="4" rx="1" />
            <rect x="14" y="11" width="7" height="10" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
          </template>
          <template v-else-if="item.icon === 'analyze'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </template>
          <template v-else-if="item.icon === 'approvals'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </template>
          <template v-else-if="item.icon === 'portfolio'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
          </template>
          <template v-else-if="item.icon === 'rules'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </template>
          <template v-else-if="item.icon === 'graph'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </template>
          <template v-else-if="item.icon === 'portfolio'">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </template>
          <template v-else-if="item.icon === 'backtest'">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </template>
        </svg>
        <span v-show="!sidebarStore.isCollapsed" class="whitespace-nowrap">{{ item.label }}</span>
      </button>
    </nav>

    <!-- Bottom controls -->
    <div class="p-2 border-t border-[var(--border-subtle)] space-y-0.5">
      <button
        class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors"
        @click="themeStore.toggleTheme()"
        :title="themeStore.isDark ? '切换亮色' : '切换暗色'"
      >
        <svg class="flex-shrink-0 w-[18px] h-[18px]" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8">
          <template v-if="themeStore.isDark">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </template>
          <template v-else>
            <path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </template>
        </svg>
        <span v-show="!sidebarStore.isCollapsed" class="whitespace-nowrap">
          {{ themeStore.isDark ? '亮色模式' : '暗色模式' }}
        </span>
      </button>

      <button
        class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors"
        @click="sidebarStore.toggle()"
        :title="sidebarStore.isCollapsed ? '展开侧边栏' : '折叠侧边栏'"
      >
        <svg
          class="flex-shrink-0 w-[18px] h-[18px] transition-transform"
          :class="sidebarStore.isCollapsed ? 'rotate-180' : ''"
          fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.8"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
        <span v-show="!sidebarStore.isCollapsed" class="whitespace-nowrap">折叠</span>
      </button>
    </div>
  </aside>
</template>