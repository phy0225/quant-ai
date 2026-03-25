<script setup lang="ts">
interface Column {
  key: string
  label: string
  width?: string
  align?: 'left' | 'center' | 'right'
}

interface Props {
  columns: Column[]
  data: Record<string, unknown>[]
  loading?: boolean
  emptyText?: string
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  emptyText: '暂无数据',
})

const alignClass = (align?: string) => {
  if (align === 'center') return 'text-center'
  if (align === 'right') return 'text-right'
  return 'text-left'
}
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-[var(--border-subtle)]">
    <table class="w-full border-collapse">
      <thead>
        <tr class="bg-[var(--bg-elevated)] border-b border-[var(--border-subtle)]">
          <th
            v-for="col in props.columns"
            :key="col.key"
            class="px-4 py-2.5 text-[12px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider"
            :class="alignClass(col.align)"
            :style="col.width ? { width: col.width } : {}"
          >
            <slot :name="`header-${col.key}`">{{ col.label }}</slot>
          </th>
        </tr>
      </thead>
      <tbody>
        <!-- Loading skeleton -->
        <template v-if="props.loading">
          <tr
            v-for="i in 5"
            :key="`skeleton-${i}`"
            class="border-b border-[var(--border-subtle)]"
          >
            <td
              v-for="col in props.columns"
              :key="`skeleton-${i}-${col.key}`"
              class="px-4 py-3"
            >
              <div class="skeleton h-4 rounded" :style="{ width: `${40 + Math.random() * 40}%` }" />
            </td>
          </tr>
        </template>

        <!-- Empty state -->
        <tr v-else-if="props.data.length === 0">
          <td
            :colspan="props.columns.length"
            class="px-4 py-12 text-center text-[var(--text-tertiary)] text-sm"
          >
            {{ props.emptyText }}
          </td>
        </tr>

        <!-- Data rows -->
        <tr
          v-else
          v-for="(row, rowIndex) in props.data"
          :key="rowIndex"
          class="border-b border-[var(--border-subtle)] transition-colors hover:bg-[var(--bg-hover)]"
        >
          <td
            v-for="col in props.columns"
            :key="`${rowIndex}-${col.key}`"
            class="px-4 py-2.5 text-[13px] text-[var(--text-primary)]"
            :class="alignClass(col.align)"
          >
            <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]" :index="rowIndex">
              {{ row[col.key] ?? '--' }}
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
