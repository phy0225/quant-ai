<script setup lang="ts">
interface Props {
  variant?: 'primary' | 'success' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  loading: false,
  disabled: false,
})

const emit = defineEmits<{
  click: [e: MouseEvent]
}>()

const variantClasses: Record<string, string> = {
  primary: 'bg-[var(--brand-primary)] text-white hover:bg-[var(--brand-primary-hover)] active:bg-[var(--brand-primary-active)]',
  success: 'bg-[var(--positive)] text-white hover:bg-[var(--positive-hover)]',
  danger: 'bg-[var(--negative)] text-white hover:bg-[var(--negative-hover)]',
  ghost: 'bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]',
  outline: 'bg-transparent text-[var(--text-primary)] border border-[var(--border-default)] hover:bg-[var(--bg-hover)]',
}

const sizeClasses: Record<string, string> = {
  sm: 'px-2.5 py-1 text-[12px] rounded-[var(--radius-sm)]',
  md: 'px-3.5 py-1.5 text-[13px] rounded-[var(--radius-md)]',
  lg: 'px-5 py-2.5 text-[14px] rounded-[var(--radius-md)]',
}

function handleClick(e: MouseEvent) {
  if (!props.loading && !props.disabled) {
    emit('click', e)
  }
}
</script>

<template>
  <button
    :class="[
      'inline-flex items-center justify-center gap-1.5 font-medium transition-all',
      'focus:outline-none focus:ring-2 focus:ring-[var(--brand-primary)] focus:ring-offset-1 focus:ring-offset-[var(--bg-base)]',
      variantClasses[props.variant],
      sizeClasses[props.size],
      (props.disabled || props.loading) && 'opacity-50 cursor-not-allowed',
    ]"
    :disabled="props.disabled || props.loading"
    @click="handleClick"
  >
    <svg
      v-if="props.loading"
      class="animate-spin -ml-0.5 h-3.5 w-3.5"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
    <slot />
  </button>
</template>
