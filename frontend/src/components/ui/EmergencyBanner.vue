<script setup lang="ts">
import { ref } from 'vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import { formatDate } from '@/utils/formatters'

interface Props {
  activatedAt: string
  activatedBy?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  activatedBy: null,
})

const emit = defineEmits<{
  deactivate: [password: string]
}>()

const showPasswordInput = ref(false)
const password = ref('')
const isSubmitting = ref(false)

function handleDeactivate() {
  if (!password.value.trim()) return
  isSubmitting.value = true
  emit('deactivate', password.value.trim())
  // Parent is responsible for resetting isSubmitting via re-render or removing the banner
}

function togglePasswordInput() {
  showPasswordInput.value = !showPasswordInput.value
  password.value = ''
}
</script>

<template>
  <div
    class="fixed top-0 left-0 right-0 z-[9999] bg-[var(--negative,#dc2626)] text-white shadow-lg"
    role="alert"
    aria-live="assertive"
  >
    <div class="max-w-[1440px] mx-auto px-4 py-3">
      <div class="flex items-center justify-between gap-4">
        <!-- Warning content -->
        <div class="flex items-center gap-3 min-w-0">
          <svg class="w-5 h-5 flex-shrink-0 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <div class="min-w-0">
            <p class="text-sm font-bold">系统已进入紧急停止状态</p>
            <p class="text-xs opacity-90">
              激活时间: {{ formatDate(props.activatedAt) }}
              <template v-if="props.activatedBy">
                | 操作人: {{ props.activatedBy }}
              </template>
            </p>
          </div>
        </div>

        <!-- Deactivate action -->
        <div class="flex items-center gap-2 flex-shrink-0">
          <template v-if="showPasswordInput">
            <input
              v-model="password"
              type="password"
              placeholder="输入密码确认"
              class="px-2 py-1 text-xs rounded bg-white/20 border border-white/30 text-white placeholder-white/60 focus:outline-none focus:ring-2 focus:ring-white/50 w-36"
              aria-label="输入密码以解除紧急停止"
              @keyup.enter="handleDeactivate"
            />
            <ActionButton
              variant="outline"
              size="sm"
              class="!border-white/50 !text-white hover:!bg-white/20"
              :disabled="!password.trim()"
              :loading="isSubmitting"
              @click="handleDeactivate"
            >
              确认解除
            </ActionButton>
            <button
              class="text-white/70 hover:text-white text-xs underline"
              @click="togglePasswordInput"
            >
              取消
            </button>
          </template>
          <template v-else>
            <ActionButton
              variant="outline"
              size="sm"
              class="!border-white/50 !text-white hover:!bg-white/20"
              @click="togglePasswordInput"
            >
              解除紧急停止
            </ActionButton>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
