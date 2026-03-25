<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import ActionButton from './ActionButton.vue'

interface Props {
  visible: boolean
  mode: 'activate' | 'deactivate'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  activate: [data: { reason: string; activated_by: string }]
  deactivate: [data: { password: string; deactivated_by: string }]
  cancel: []
}>()

const reason = ref('')
const operatorName = ref('')
const password = ref('')
const countdown = ref(5)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const canConfirm = computed(() => {
  if (props.mode === 'activate') {
    return reason.value.trim().length > 0 && operatorName.value.trim().length > 0
  }
  return password.value.trim().length > 0 && operatorName.value.trim().length > 0 && countdown.value === 0
})

function startCountdown() {
  countdown.value = 5
  countdownTimer = setInterval(() => {
    if (countdown.value > 0) {
      countdown.value--
    } else if (countdownTimer) {
      clearInterval(countdownTimer)
      countdownTimer = null
    }
  }, 1000)
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

watch(() => props.visible, (val) => {
  if (val && props.mode === 'deactivate') {
    startCountdown()
  }
  if (!val) {
    reason.value = ''
    operatorName.value = ''
    password.value = ''
    countdown.value = 5
    stopCountdown()
  }
})

onUnmounted(stopCountdown)

function close() {
  if (props.mode === 'activate') {
    emit('update:visible', false)
    emit('cancel')
  }
  // Deactivate mode does not close on overlay click
}

function handleCancel() {
  emit('update:visible', false)
  emit('cancel')
}

function confirm() {
  if (!canConfirm.value) return

  if (props.mode === 'activate') {
    emit('activate', {
      reason: reason.value.trim(),
      activated_by: operatorName.value.trim(),
    })
  } else {
    emit('deactivate', {
      password: password.value,
      deactivated_by: operatorName.value.trim(),
    })
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="props.visible"
        class="fixed inset-0 z-[9999] flex items-center justify-center"
        role="alertdialog"
        aria-modal="true"
      >
        <!-- Overlay (no close on click for both modes) -->
        <div class="absolute inset-0 modal-overlay" />

        <!-- Dialog -->
        <div class="relative z-10 w-full max-w-lg mx-4 bg-[var(--bg-surface)] rounded-xl border-2 border-[var(--negative)] shadow-[var(--shadow-modal)] p-6">
          <!-- Header -->
          <div class="flex items-center gap-3 mb-4">
            <div class="flex-shrink-0 w-12 h-12 rounded-full bg-[var(--negative-subtle)] flex items-center justify-center">
              <svg class="w-6 h-6 text-[var(--negative)] animate-blink" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <h3 class="text-lg font-bold text-[var(--negative)]">
                {{ props.mode === 'activate' ? '激活紧急停止' : '解除紧急停止' }}
              </h3>
              <p class="text-xs text-[var(--text-tertiary)]">
                {{ props.mode === 'activate' ? '此操作将立即停止系统所有操作' : '请输入管理员密码以解除' }}
              </p>
            </div>
          </div>

          <!-- Activate mode fields -->
          <template v-if="props.mode === 'activate'">
            <div class="space-y-3 mb-4">
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">停止原因</label>
                <textarea
                  v-model="reason"
                  rows="3"
                  placeholder="请输入紧急停止原因..."
                  class="w-full resize-none"
                />
              </div>
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">操作人</label>
                <input
                  v-model="operatorName"
                  type="text"
                  placeholder="请输入您的姓名"
                />
              </div>
            </div>
          </template>

          <!-- Deactivate mode fields -->
          <template v-else>
            <div class="space-y-3 mb-4">
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">管理员密码</label>
                <input
                  v-model="password"
                  type="password"
                  placeholder="请输入管理员密码"
                />
              </div>
              <div>
                <label class="block text-xs text-[var(--text-secondary)] mb-1">操作人</label>
                <input
                  v-model="operatorName"
                  type="text"
                  placeholder="请输入您的姓名"
                />
              </div>
            </div>
          </template>

          <div class="flex justify-end gap-3">
            <ActionButton variant="ghost" @click="handleCancel" :disabled="props.loading">
              取消
            </ActionButton>
            <ActionButton
              variant="danger"
              :loading="props.loading"
              :disabled="!canConfirm"
              @click="confirm"
            >
              <template v-if="props.mode === 'deactivate' && countdown > 0">
                {{ countdown }}s 后可操作
              </template>
              <template v-else>
                {{ props.mode === 'activate' ? '确认激活' : '确认解除' }}
              </template>
            </ActionButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--duration-modal) var(--ease-default);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
</style>
