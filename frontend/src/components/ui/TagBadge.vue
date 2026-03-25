<script setup lang="ts">
interface Props {
  variant: 'pending' | 'approved' | 'rejected' | 'auto_approved' | 'modified' | 'info' | 'warning' | 'success' | 'danger'
  label: string
  size?: 'sm' | 'md'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const variantStyles: Record<string, string> = {
  pending: 'bg-[var(--warning-subtle)] text-[var(--warning)] border-[var(--warning)]',
  approved: 'bg-[var(--positive-subtle)] text-[var(--positive)] border-[var(--positive)]',
  rejected: 'bg-[var(--negative-subtle)] text-[var(--negative)] border-[var(--negative)]',
  auto_approved: 'bg-[var(--brand-primary-subtle)] text-[var(--brand-primary)] border-[var(--brand-primary)]',
  modified: 'bg-purple-50 text-purple-600 border-purple-300',
  info: 'bg-[var(--brand-secondary-subtle)] text-[var(--brand-secondary)] border-[var(--brand-secondary)]',
  warning: 'bg-[var(--warning-subtle)] text-[var(--warning)] border-[var(--warning)]',
  success: 'bg-[var(--positive-subtle)] text-[var(--positive)] border-[var(--positive)]',
  danger: 'bg-[var(--negative-subtle)] text-[var(--negative)] border-[var(--negative)]',
}

const sizeStyles: Record<string, string> = {
  sm: 'px-1.5 py-0.5 text-[11px]',
  md: 'px-2 py-0.5 text-[12px]',
}
</script>

<template>
  <span
    class="inline-flex items-center rounded-full border font-medium leading-tight whitespace-nowrap"
    :class="[variantStyles[props.variant], sizeStyles[props.size]]"
  >
    {{ props.label }}
  </span>
</template>