<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ data: Array<{ date: string; count: number }> }>()
const chartElement = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

function render() {
  chart?.setOption({
    animation: !window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    grid: { left: 34, right: 12, top: 16, bottom: 28 },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.data.map((item) => item.date.slice(5)),
      axisLine: { lineStyle: { color: '#cbd8ed' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#e8eef8' } },
    },
    series: [
      {
        type: 'line',
        smooth: 0.32,
        data: props.data.map((item) => item.count),
        symbolSize: 7,
        lineStyle: { width: 3, color: '#3978e9' },
        itemStyle: { color: '#f45d8c' },
        areaStyle: { color: 'rgba(57,120,233,.12)' },
      },
    ],
  })
}
onMounted(() => {
  if (!chartElement.value) return
  chart = echarts.init(chartElement.value)
  render()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(chartElement.value)
})
watch(() => props.data, render, { deep: true })
onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <div
    ref="chartElement"
    class="activity-chart"
    role="img"
    aria-label="14 day sign-in activity line chart"
  />
</template>

<style scoped>
.activity-chart {
  width: 100%;
  height: 250px;
}
</style>
