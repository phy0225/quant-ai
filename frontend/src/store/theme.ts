import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 主题 Store
 * 管理亮色/暗色主题切换，支持 localStorage 持久化和系统主题检测
 * Dark Mode 为默认模式
 */
export const useThemeStore = defineStore('theme', () => {
  // 当前是否为暗色模式（默认 true）
  const isDark = ref(true)

  /**
   * 切换主题
   * Dark Mode 时 data-theme 不设置（:root 默认为暗色）
   * Light Mode 时设置 data-theme="light"
   */
  function toggleTheme() {
    isDark.value = !isDark.value
    applyTheme(isDark.value)
    localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
  }

  /**
   * 应用主题到 DOM
   */
  function applyTheme(dark: boolean) {
    if (dark) {
      // 暗色模式：移除 data-theme 属性（使用 :root 默认样式）
      document.documentElement.removeAttribute('data-theme')
    } else {
      // 亮色模式：设置 data-theme="light" 触发覆盖样式
      document.documentElement.setAttribute('data-theme', 'light')
    }
  }

  /**
   * 初始化主题
   * 优先级：localStorage 保存值 > 系统 prefers-color-scheme > 默认暗色
   * 必须在 App.vue 的 onMounted 中调用，确保 DOM 已就绪
   */
  function initTheme() {
    const savedTheme = localStorage.getItem('theme')

    if (savedTheme) {
      // 使用用户保存的主题偏好
      isDark.value = savedTheme !== 'light'
    } else {
      // 检测系统主题偏好
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      isDark.value = prefersDark
    }

    applyTheme(isDark.value)

    // 监听系统主题变化（仅当用户未手动设置时生效）
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem('theme')) {
        isDark.value = e.matches
        applyTheme(isDark.value)
      }
    })
  }

  return {
    isDark,
    toggleTheme,
    initTheme,
  }
})
