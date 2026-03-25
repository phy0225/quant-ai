<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import ActionButton from './ActionButton.vue'

interface Props {
  visible: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  confirmWord?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  confirmText: '确认执行',
  cancelText: '取消',
  confirmWord: 'CONFIRM',
  loading: false,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: []
  cancel: []
}>()

const inputValue = ref('')

const canConfirm = computed(() => inputValue.value === props.confirmWord)

function close() {
  emit('update:visible', false)
  emit('cancel')
  inputValue.value = ''
}

function confirm() {
  if (canConfirm.value) {
    emit('confirm')
  }
}

watch(() => props.visible, (val) => {
  if (!val) {
    inputValue.value = ''
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="props.visible"
        class="fixed inset-0 z-[9990] flex items-center justify-center"
        role="alertdialog"
        aria-modal="true"
      >
        <!-- Overlay (no close on click) -->
        <div class="absolute inset-0 modal-overlay" />

        <!-- Dialog -->
        <div class="relative z-10 w-full max-w-md mx-4 bg-[var(--bg-surface)] rounded-xl border-2 border-[var(--negative)] shadow-[var(--shadow-modal)] p-6">
          <!-- Warning icon -->
          <div class="flex items-center gap-3 mb-4">
            <div class="flex-shrink-0 w-10 h-10 rounded-full bg-[var(--negative-subtle)] flex items-center justify-center">
              <svg class="w-5 h-5 text-[var(--negative)] animate-blink" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h3 class="text-lg font-semibold text-[var(--negative)]">
              {{ props.title }}
            </h3>
          </div>

          <p class="text-sm text-[var(--text-secondary)] mb-4">
            {{ props.message }}
          </p>

          <slot />

          <!-- Confirmation input -->
          <div class="mb-4">
            <label class="block text-xs text-[var(--text-tertiary)] mb-1">
              请输入 <code class="text-[var(--negative)] font-bold">{{ props.confirmWord }}</code> 以确认操作
            </label>
            <input
              v-model="inputValue"
              type="text"
              :placeholder="props.confirmWord"
              class="w-full"
              autocomplete="off"
            />
          </div>

          <div class="flex justify-end gap-3">
            <ActionButton variant="ghost" @click="close" :disabled="props.loading">
              {{ props.cancelText }}
            </ActionButton>
            <ActionButton
              variant="danger"
              :loading="props.loading"
              :disabled="!canConfirm"
              @click="confirm"
            >
              {{ props.confirmText }}
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
