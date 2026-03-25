<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkAreaComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { NavPoint } from '@/types/backtest'
import { useThemeStore } from '@/store/theme'

use([LineChart, TooltipComponent, LegendComponent, GridComponent, DataZoomComponent, MarkAreaComponent, CanvasRenderer])

interface Props {
  data: NavPoint[]
  maxDrawdownStart?: string
  maxDrawdownEnd?: string
  height?: string
}

const props = withDefaults(defineProps<Props>(), {
  height: '360px',
})

const themeStore = useThemeStore()

const validData = computed(() =>
  Array.isArray(props.data)
    ? props.data.filter((p) => p && typeof p.nav === 'number' && isFinite(p.nav) && p.date)
    : []
)

const chartOption = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis' as const,
    backgroundColor: themeStore.isDark ? '#1E2333' : '#FFFFFF',
    borderColor: themeStore.isDark ? '#3A4560' : '#C8D0E0',
    textStyle: {
      color: themeStore.isDark ? '#E8EAF0' : '#1A1D2E',
      fontSize: 12,
    },
    formatter: (params: Array<{ seriesName: string; value: [string, number]; marker: string }>) => {
      if (!params.length) return ''
      const date = params[0].value[0]
      let html = `<div style="font-size:11px;color:${themeStore.isDark ? '#9AA0B4' : '#4A5270'};margin-bottom:4px">${date}</div>`
      params.forEach((p) => {
        html += `<div>${p.marker} ${p.seriesName}: <strong>${p.value[1].toFixed(4)}</strong></div>`
      })
      if (params.length === 2) {
        const excess = params[0].value[1] - params[1].value[1]
        const color = excess >= 0 ? '#2DC87A' : '#F5474F'
        html += `<div style="color:${color};margin-top:2px">超额: ${excess >= 0 ? '+' : ''}${excess.toFixed(4)}</div>`
      }
      return html
    },
  },
  legend: {
    data: ['组合净值', '基准净值'],
    bottom: 30,
    textStyle: { color: themeStore.isDark ? '#9AA0B4' : '#4A5270', fontSize: 11 },
  },
  grid: {
    left: 60,
    right: 20,
    top: 20,
    bottom: 80,
  },
  xAxis: {
    type: 'time' as const,
    axisLine: { lineStyle: { color: themeStore.isDark ? '#3A4560' : '#C8D0E0' } },
    axisLabel: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 11 },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'value' as const,
    scale: true,
    axisLine: { show: false },
    axisLabel: {
      color: themeStore.isDark ? '#5C6380' : '#8A90A8',
      fontSize: 11,
      formatter: (v: number) => v.toFixed(2),
    },
    splitLine: { lineStyle: { color: themeStore.isDark ? '#2A3150' : '#E2E6F0', type: 'dashed' as const } },
  },
  series: [
    {
      name: '组合净值',
      type: 'line' as const,
      data: validData.value.map((p) => [p.date, p.nav]),
      lineStyle: { color: '#4F7EFF', width: 2 },
      itemStyle: { color: '#4F7EFF' },
      showSymbol: false,
      smooth: false,
      markArea: props.maxDrawdownStart
        ? {
            silent: true,
            itemStyle: { color: 'rgba(245,71,79,0.08)' },
            data: [
              [
                { xAxis: props.maxDrawdownStart },
                { xAxis: props.maxDrawdownEnd },
              ],
            ],
          }
        : undefined,
    },
    {
      name: '基准净值',
      type: 'line' as const,
      data: validData.value.map((p) => [p.date, p.benchmark_nav]),
      lineStyle: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', width: 1.5, type: 'dashed' as const },
      itemStyle: { color: themeStore.isDark ? '#5C6380' : '#8A90A8' },
      showSymbol: false,
      smooth: false,
    },
  ],
  dataZoom: [
    { type: 'inside' as const },
    {
      type: 'slider' as const,
      bottom: 5,
      height: 18,
      borderColor: 'transparent',
      backgroundColor: themeStore.isDark ? '#1E2333' : '#F4F6FA',
      fillerColor: themeStore.isDark ? 'rgba(79,126,255,0.15)' : 'rgba(43,92,230,0.1)',
      handleStyle: { color: '#4F7EFF' },
      textStyle: { color: themeStore.isDark ? '#5C6380' : '#8A90A8', fontSize: 10 },
    },
  ],
}))
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
