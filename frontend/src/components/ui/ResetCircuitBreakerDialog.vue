<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import ActionButton from './ActionButton.vue'

interface Props {
  visible: boolean
  currentLevel: 0 | 1 | 2 | 3
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), { loading: false })

const emit = defineEmits<{
  'update:visible': [value: boolean]
  confirm: [data: { target_level: number; authorized_by: string }]
}>()

const authorizedBy = ref('')
const targetLevel = ref<number>(0)

const levelOptions = computed(() => {
  const names = ['正常 (L0)', '警告 (L1)', '暂停 (L2)', '紧急 (L3)']
  return Array.from({ length: props.currentLevel }, (_, i) => ({ value: i, label: names[i] }))
})

const canConfirm = computed(() => authorizedBy.value.trim().length > 0 && levelOptions.value.length > 0)

watch(() => props.visible, (val) => {
  if (val) {
    authorizedBy.value = ''
    targetLevel.value = Math.max(0, props.currentLevel - 1)
  }
})

function close() {
  emit('update:visible', false)
}

function confirm() {
  if (!canConfirm.value) return
  emit('confirm', { target_level: targetLevel.value, authorized_by: authorizedBy.value.trim() })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="visible"
        class="fixed inset-0 z-[9999] flex items-center justify-center"
      >
        <div class="absolute inset-0 bg-black/50" @click="close" />
        <div class="relative z-10 w-full max-w-md mx-4 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-default)] shadow-[var(--shadow-modal)] p-6">
          <h3 class="text-base font-bold text-[var(--text-primary)] mb-1">重置熔断等级</h3>
          <p class="text-[12px] text-[var(--text-tertiary)] mb-4">
            当前等级 <span class="font-semibold text-[var(--negative)]">L{{ currentLevel }}</span>，重置后系统将恢复对应权限。
          </p>

          <div v-if="currentLevel === 3" class="mb-4 p-3 rounded-lg bg-[var(--negative)]/10 border border-[var(--negative)]/30 text-[12px] text-[var(--negative)]">
            ⚠ 当前为最高级紧急熔断，重置操作不可逆，请谨慎操作。
          </div>

          <div class="space-y-3 mb-4">
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">重置目标等级</label>
              <select v-model.number="targetLevel" class="w-full">
                <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-[var(--text-secondary)] mb-1">授权操作人 *</label>
              <input v-model="authorizedBy" type="text" placeholder="请输入您的姓名" />
            </div>
          </div>

          <div class="flex justify-end gap-2">
            <ActionButton variant="ghost" @click="close" :disabled="loading">取消</ActionButton>
            <ActionButton variant="primary" :disabled="!canConfirm" :loading="loading" @click="confirm">
              确认重置
            </ActionButton>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
</style>
