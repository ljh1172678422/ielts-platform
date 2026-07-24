/**
 * ECharts 6 按需引入 composable（system-architecture §5.5 学习数据页）。
 *
 * 设计要点：
 * - echarts 6 推荐 tree-shaking：从 'echarts/core' 引入核心 + 仅注册使用到的图表/组件
 * - 提供 initChart(dom) 返回 echarts 实例 + setOptions(options) 包装
 * - onBeforeUnmount 自动 dispose 防内存泄漏
 * - 监听 window resize 自适应
 */
import { onBeforeUnmount, ref, shallowRef, type Ref } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

export type { EChartsOption }

export interface UseEChartsReturn {
  /** chart 容器 ref（template 里 ref="chartRef" 绑定） */
  chartRef: Ref<HTMLElement | null>
  /** 是否已就绪（initChart 成功后 true） */
  ready: Ref<boolean>
  /** 初始化图表（在 onMounted 后调用） */
  initChart: () => echarts.ECharts | null
  /** 设置 option（自动等待 init） */
  setOptions: (options: EChartsOption) => void
  /** 获取底层实例（可能为 null） */
  getInstance: () => echarts.ECharts | null
  /** 销毁实例 */
  dispose: () => void
}

export function useECharts(): UseEChartsReturn {
  const chartRef = ref<HTMLElement | null>(null)
  const ready = ref(false)
  // shallowRef 避免 echarts 实例被 Vue 深度代理（性能 + 避免内部状态被篡改）
  const instance = shallowRef<echarts.ECharts | null>(null)

  let resizeHandler: (() => void) | null = null

  function initChart(): echarts.ECharts | null {
    if (!chartRef.value) return null
    if (instance.value) return instance.value
    instance.value = echarts.init(chartRef.value)
    ready.value = true
    resizeHandler = (): void => {
      instance.value?.resize()
    }
    window.addEventListener('resize', resizeHandler)
    return instance.value
  }

  function setOptions(options: EChartsOption): void {
    if (!instance.value) {
      initChart()
    }
    instance.value?.setOption(options, { notMerge: true })
  }

  function getInstance(): echarts.ECharts | null {
    return instance.value
  }

  function dispose(): void {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    if (instance.value) {
      instance.value.dispose()
      instance.value = null
      ready.value = false
    }
  }

  onBeforeUnmount(() => {
    dispose()
  })

  return {
    chartRef,
    ready,
    initChart,
    setOptions,
    getInstance,
    dispose,
  }
}
