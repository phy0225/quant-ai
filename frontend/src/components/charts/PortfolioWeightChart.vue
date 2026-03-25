<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useThemeStore } from '@/store/theme'

use([LineChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

interface WeightSnapshot {
  date: string
  weights: Record<string, number>
}

interface Props {
  weightHistory: WeightSnapshot[]
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  height: '300px',
})

const themeStore = useThemeStore()

const colors = [
  '#4F7EFF', '#7C5CFC', '#2DC87A', '#F5A623', '#F5474F',
  '#5C7EC7', '#3AD988', '#FFB73A',
]

const chartOption = computed(() => {
  const symbols = Object.keys(props.weightHistory[0]?.weights || {})

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis' as const,
      backgroundColor: themeStore.isDark ? '#1E2333' : '#FFFFFF',
      borderColor: themeStore.isDark ? '#3A4560' : '#C8D0E0',
      textStyle: {
        color: themeStore.isDark ? '#E8EAF0' : '#1A1D2E',
        fontSize: 12,
      },
      formatter: (params: Array<{ marker: string; seriesName: string; value: [string, number] }>) => {
        if (!params.length) return ''
        let html = `<div style="font-size:11px;color:${themeStore.isDark ? '#9AA0B4' : '#4A5270'};margin-bottom:4px">${params[0].value[0]}</div>`
        params.forEach((p) => {
          html += `<div>${p.marker} ${p.seriesName}: ${(p.value[1] * 100).toFixed(1)}%</div>`
        })
        return html
      },
    },
    legend: {
      top: 0,
      type: 'scroll' as const,
      textStyle: { color: themeStore.isDark ? '#9AA0B4' : '#4A5270', fontSize: 11 },
    },
    grid: {
      left: 50,
      right: 20,
      top: 35,
      bottom: 20,
    },
    xAxis: {
      type: 'time' as const,
      axisLine: { lineStyle: { color: themeStore.isDark ? '#3A4560' : '#C8D0E0' } },
      axisLabel: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value' as const,
      min: 0,
      max: 1,
      axisLine: { show: false },
      axisLabel: {
        color: themeStore.isDark ? '#5C6380' : '#8A90A8',
        fontSize: 10,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: themeStore.isDark ? '#2A3150' : '#E2E6F0', type: 'dashed' as const } },
    },
    series: symbols.map((symbol, idx) => ({
      name: symbol,
      type: 'line' as const,
      stack: 'weights',
      areaStyle: { opacity: 0.6 },
      data: props.weightHistory.map((h) => [h.date, h.weights[symbol] || 0]),
      lineStyle: { width: 0 },
      itemStyle: { color: colors[idx % colors.length] },
      showSymbol: false,
      emphasis: { focus: 'series' as const },
    })),
  }
})
</script>

<template>
  <div class="echarts-container">
    <VChart
      :option="chartOption"
      autoresize
      :style="{ height: props.height, width: '100%' }"
    />
  </div>
</template>
