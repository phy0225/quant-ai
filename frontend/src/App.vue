<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { RouterView } from 'vue-router'
import { useThemeStore } from '@/store/theme'
import { useSidebarStore } from '@/store/sidebar'
import { useEmergencyStore } from '@/store/emergency'
import Sidebar from '@/components/ui/Sidebar.vue'
import EmergencyDialog from '@/components/ui/EmergencyDialog.vue'
import { ref } from 'vue'
import { riskApi } from '@/api/risk'

const themeStore = useThemeStore()
const sidebarStore = useSidebarStore()
const emergencyStore = useEmergencyStore()

const showDeactivateDialog = ref(false)
const isDeactivating = ref(false)

const mainMargin = computed(() =>
  sidebarStore.isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'
)

onMounted(() => {
  themeStore.initTheme()
  sidebarStore.init()
})

async function handleDeactivate(data: { password: string; deactivated_by: string }) {
  isDeactivating.value = true
  try {
    await riskApi.deactivateEmergencyStop(data)
    emergencyStore.deactivateEmergencyStop()
    showDeactivateDialog.value = false
  } catch {
    alert('解除失败，请检查密码是否正确')
  } finally {
    isDeactivating.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-[var(--bg-base)]">
    <!-- Emergency Banner -->
    <div
      v-if="emergencyStore.isEmergencyActive"
      class="emergency-banner fixed top-0 left-0 right-0 z-50 px-4 py-2 flex items-center justify-center gap-3"
    >
      <svg class="w-4 h-4 animate-blink" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
      <span class="text-sm font-semibold">
        系统已进入紧急停止状态
      </span>
      <span v-if="emergencyStore.activatedAt" class="text-xs opacity-80">
        {{ new Date(emergencyStore.activatedAt).toLocaleString('zh-CN') }}
      </span>
      <button
        class="ml-4 px-2.5 py-0.5 text-xs font-medium bg-white/20 rounded hover:bg-white/30 transition-colors"
        @click="showDeactivateDialog = true"
      >
        解除
      </button>
    </div>

    <!-- Sidebar -->
    <Sidebar />

    <!-- Main content -->
    <main
      class="transition-all duration-200"
      :style="{
        marginLeft: mainMargin,
        paddingTop: emergencyStore.isEmergencyActive ? '40px' : '0',
      }"
    >
      <RouterView />
    </main>

    <!-- Emergency deactivate dialog -->
    <EmergencyDialog
      :visible="showDeactivateDialog"
      mode="deactivate"
      :loading="isDeactivating"
      @update:visible="showDeactivateDialog = $event"
      @deactivate="handleDeactivate"
      @cancel="showDeactivateDialog = false"
    />
  </div>
</template>
