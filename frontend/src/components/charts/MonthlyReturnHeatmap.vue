<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import {
  TooltipComponent,
  VisualMapComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { MonthlyReturnPoint } from '@/types/backtest'
import { useThemeStore } from '@/store/theme'

use([HeatmapChart, TooltipComponent, VisualMapComponent, GridComponent, CanvasRenderer])

interface Props {
  data: MonthlyReturnPoint[]
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  height: '240px',
})

const themeStore = useThemeStore()

const validData = computed(() =>
  Array.isArray(props.data)
    ? props.data.filter(
        (d) => d && typeof d.year === 'number' && typeof d.month === 'number' && typeof d.return === 'number' && isFinite(d.return)
      )
    : []
)

const chartOption = computed(() => {
  const years = [...new Set(validData.value.map((d) => d.year))].sort()
  const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']

  const heatmapData = validData.value.map((d) => [
    d.month - 1,
    years.indexOf(d.year),
    d.return,
  ])

  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: themeStore.isDark ? '#1E2333' : '#FFFFFF',
      borderColor: themeStore.isDark ? '#3A4560' : '#C8D0E0',
      textStyle: {
        color: themeStore.isDark ? '#E8EAF0' : '#1A1D2E',
        fontSize: 12,
      },
      formatter: (params: { data: [number, number, number] }) => {
        const [monthIdx, yearIdx, ret] = params.data
        const sign = ret >= 0 ? '+' : ''
        return `${years[yearIdx]}年${monthIdx + 1}月<br/>月度收益: <strong>${sign}${(ret * 100).toFixed(2)}%</strong>`
      },
    },
    visualMap: {
      min: -0.15,
      max: 0.15,
      calculable: true,
      orient: 'horizontal' as const,
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#F5474F', themeStore.isDark ? '#1E2333' : '#f9fafb', '#2DC87A'],
      },
      textStyle: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10 },
    },
    xAxis: {
      type: 'category' as const,
      data: months,
      axisLine: { lineStyle: { color: themeStore.isDark ? '#3A4560' : '#C8D0E0' } },
      axisLabel: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10 },
      splitArea: { show: false },
    },
    yAxis: {
      type: 'category' as const,
      data: years.map(String),
      axisLine: { lineStyle: { color: themeStore.isDark ? '#3A4560' : '#C8D0E0' } },
      axisLabel: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10 },
      splitArea: { show: false },
    },
    grid: {
      left: 50,
      right: 20,
      top: 10,
      bottom: 60,
    },
    series: [
      {
        type: 'heatmap' as const,
        data: heatmapData,
        label: {
          show: true,
          formatter: (params: { data: [number, number, number] }) =>
            `${(params.data[2] * 100).toFixed(1)}%`,
          fontSize: 10,
          color: themeStore.isDark ? '#E8EAF0' : '#1A1D2E',
        },
        itemStyle: {
          borderWidth: 1,
          borderColor: themeStore.isDark ? '#171B26' : '#FFFFFF',
        },
      },
    ],
  }
})
</script>

<template>
  <div class="echarts-container">
    <template v-if="validData.length > 0">
      <VChart
        :option="chartOption"
        autoresize
        :style="{ height: props.height, width: '100%' }"
      />
    </template>
    <div v-else class="flex items-center justify-center text-[var(--text-tertiary)] text-sm" :style="{ height: props.height }">
      暂无图表数据
    </div>
  </div>
</template>
