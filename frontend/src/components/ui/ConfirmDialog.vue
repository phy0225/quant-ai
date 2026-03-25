<script setup lang="ts">
import { watch } from 'vue'
import ActionButton from './ActionButton.vue'

interface Props {
  visible: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'default' | 'danger'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  confirmText: '确认',
  cancelText: '取消',
  variant: 'default',
  loading: false,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: []
  cancel: []
}>()

function close() {
  emit('update:visible', false)
  emit('cancel')
}

function confirm() {
  emit('confirm')
}

// ESC key handler
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    close()
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    document.addEventListener('keydown', handleKeydown)
  } else {
    document.removeEventListener('keydown', handleKeydown)
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="props.visible"
        class="fixed inset-0 z-[9990] flex items-center justify-center"
        role="dialog"
        aria-modal="true"
      >
        <!-- Overlay -->
        <div
          class="absolute inset-0 modal-overlay"
          @click="close"
        />

        <!-- Dialog -->
        <div class="relative z-10 w-full max-w-md mx-4 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-default)] shadow-[var(--shadow-modal)] p-6">
          <h3 class="text-lg font-semibold text-[var(--text-primary)] mb-2">
            {{ props.title }}
          </h3>
          <p class="text-sm text-[var(--text-secondary)] mb-6">
            {{ props.message }}
          </p>
          <slot />
          <div class="flex justify-end gap-3 mt-4">
            <ActionButton variant="ghost" @click="close" :disabled="props.loading">
              {{ props.cancelText }}
            </ActionButton>
            <ActionButton
              :variant="props.variant === 'danger' ? 'danger' : 'primary'"
              :loading="props.loading"
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
