import { defineStore } from 'pinia'
import { ref, onMounted } from 'vue'

/**
 * 侧边栏 Store
 * 管理侧边栏折叠状态，支持移动端自动折叠
 */
export const useSidebarStore = defineStore('sidebar', () => {
  // 是否折叠（默认展开）
  const isCollapsed = ref(false)
  // 当前激活的路由路径
  const activeRoute = ref('')

  /**
   * 切换折叠状态
   */
  function toggle() {
    isCollapsed.value = !isCollapsed.value
  }

  /**
   * 设置折叠状态
   */
  function setCollapsed(collapsed: boolean) {
    isCollapsed.value = collapsed
  }

  /**
   * 设置当前激活路由
   */
  function setActive(route: string) {
    activeRoute.value = route
  }

  /**
   * 根据窗口宽度自动适配侧边栏状态
   */
  function handleResize() {
    if (window.innerWidth < 768) {
      // 移动端自动折叠
      isCollapsed.value = true
    } else if (window.innerWidth >= 1280) {
      // 大屏幕自动展开
      isCollapsed.value = false
    }
  }

  /**
   * 初始化侧边栏（从 localStorage 恢复状态，监听窗口大小）
   */
  function init() {
    // 恢复保存的折叠状态
    const saved = localStorage.getItem('sidebar-collapsed')
    if (saved !== null) {
      isCollapsed.value = saved === 'true'
    }

    // 初始检查屏幕尺寸
    handleResize()

    // 监听窗口大小变化
    window.addEventListener('resize', handleResize)
  }

  return {
    isCollapsed,
    activeRoute,
    toggle,
    setCollapsed,
    setActive,
    init,
  }
})
