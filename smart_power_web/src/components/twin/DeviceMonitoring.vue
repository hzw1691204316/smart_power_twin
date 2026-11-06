<template>
  <section class="device-monitoring" aria-label="数据库设备监测" aria-live="polite">
    <div class="monitor-heading">
      <h3>{{ device?.name ?? '设备监测' }}</h3>
      <button :disabled="loading" @click="load">{{ loading ? '读取中…' : '刷新' }}</button>
    </div>
    <p class="monitor-note">
      MySQL · {{ device?.isDemo ? '模拟采样，非现场数据' : '按设备身份读取' }}
    </p>
    <p v-if="error" class="monitor-error" role="alert">{{ error }}</p>
    <p v-else-if="loading && !readings.length">正在读取测点…</p>
    <p v-else-if="!readings.length">暂无测点，请先导入模拟数据或创建测点。</p>
    <dl v-else class="monitor-readings">
      <div v-for="item in readings" :key="item.pointId">
        <dt>
          {{ item.name.replace('（模拟）', '')
          }}<small
            >{{
              !item.enabled
                ? '已停用'
                : !item.sampledAt
                  ? '未采集'
                  : item.isStale
                    ? '数据陈旧'
                    : '采样有效期内'
            }}
            · {{ item.quality ?? '无质量标记' }}</small
          >
        </dt>
        <dd :class="{ muted: item.isStale || item.quality !== 'GOOD' }">
          {{ readingValue(item)
          }}<small v-if="item.valueType === 'NUMERIC'"> {{ item.unit }}</small>
        </dd>
      </div>
    </dl>
    <label class="monitor-auto"
      ><input v-model="automatic" type="checkbox" />30秒自动刷新（可见页面）</label
    >
    <div v-if="definitions.length" class="monitor-history">
      <h4>设备历史采样</h4>
      <div class="monitor-controls">
        <select v-model="pointId" aria-label="历史测点">
          <option v-for="p in definitions" :key="p.id" :value="p.id">
            {{ p.name.replace('（模拟）', '') }} / {{ p.unit }}
          </option></select
        ><select v-model="hours" aria-label="历史范围">
          <option :value="1">采样前1小时</option>
          <option :value="24">采样前24小时</option>
          <option :value="168">采样前7天</option>
        </select>
      </div>
      <p v-if="historyError" class="monitor-error" role="alert">{{ historyError }}</p>
      <p v-else-if="historyLoading">正在查询历史…</p>
      <p v-else-if="!history?.items.length">该时间范围暂无历史采样。</p>
      <template v-else>
        <svg
          v-if="plot.count && selectedPoint?.valueType === 'NUMERIC'"
          viewBox="0 0 320 132"
          role="img"
          :aria-label="`${selectedPoint?.name}历史曲线，单位${history.unit}`"
        >
          <path d="M12 16H308 M12 66H308 M12 116H308" class="monitor-grid" />
          <polyline v-for="(path, i) in plot.paths" :key="i" :points="path" class="monitor-line" />
          <circle
            v-for="(path, i) in plot.paths.filter((p) => !p.includes(' '))"
            :key="`dot-${i}`"
            :cx="path.split(',')[0]"
            :cy="path.split(',')[1]"
            r="3"
            class="monitor-dot"
          />
        </svg>
        <p v-if="selectedPoint?.valueType === 'NUMERIC'" class="monitor-note">
          有效值 {{ plot.count }} 条 · {{ plot.min ?? '—' }} ～ {{ plot.max ?? '—' }}
          {{ history.unit }}
        </p>
        <p v-else class="monitor-note">状态/文本测点按记录查看，不画数值均值曲线。</p>
        <div class="monitor-history-list">
          <div v-for="(item, i) in history.items.slice(-5).reverse()" :key="i">
            <time>{{ formatTime(item.sampledAt) }}</time
            ><span
              >{{ item.quality === 'BAD' ? '—' : (item.valueText ?? item.valueNumeric ?? '—') }} ·
              {{ item.quality }}</span
            >
          </div>
        </div>
        <p v-if="history.hasMore" class="monitor-error">已截断至2000条，请缩小时间范围。</p>
      </template>
      <p class="monitor-note">
        以所选测点最新采样为终点：{{
          formatTime(selectedLatest?.sampledAt)
        }}。历史值不代表当前实时值；累计电量不求和。
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
/** 只负责一个授权设备的监测。切站/换设备/换账号后丢弃迟到响应，不用演示值兜底。 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import * as api from '@/services/monitoringService'
import { historyPlot, readingValue } from '@/utils/monitoringPresentation'
import type {
  BackendDevice,
  LatestReading,
  PointDefinition,
  PointHistory,
} from '@/types/monitoring'

const props = defineProps<{
  deviceId: string
  deviceName: string
  isDemo: boolean
  pointIds: string[]
}>()
const auth = useAuthStore()
const device = computed<BackendDevice>(() => ({
  id: props.deviceId,
  name: props.deviceName,
  isDemo: props.isDemo,
  code: '',
}))
const definitions = ref<PointDefinition[]>([])
const readings = ref<LatestReading[]>([])
const history = ref<PointHistory>()
const loading = ref(false),
  historyLoading = ref(false),
  automatic = ref(false)
const error = ref(''),
  historyError = ref(''),
  pointId = ref(''),
  hours = ref(24)
const selectedPoint = computed(() => definitions.value.find((p) => p.id === pointId.value))
const selectedLatest = computed(() => readings.value.find((p) => p.pointId === pointId.value))
const plot = computed(() =>
  historyPlot(history.value?.items ?? [], selectedPoint.value?.sampleIntervalMs ?? 900000),
)
let generation = 0,
  historyGeneration = 0

/** 手动/定时读取：仅首次解析业务code；成功后显示数据库读数，失败清旧读数防止误认当前值。 */
async function load() {
  if (loading.value) return
  const current = generation
  if (!auth.can('monitor:read')) {
    error.value = '当前账号没有电力监测权限，请导入监测权限补丁后重新登录'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const found = device.value
    if (!props.pointIds.length)
      throw new Error('当前模型对象尚未绑定测点，请先在场景草稿中配置并发布')
    const [points, latest] = await Promise.all([api.getPoints(found.id), api.getLatest(found.id)])
    if (current !== generation) return
    const allowed = new Set(props.pointIds)
    definitions.value = points.data.filter((p) => allowed.has(p.id))
    readings.value = latest.data.filter((p) => allowed.has(p.pointId))
    if (!definitions.value.some((p) => p.id === pointId.value))
      pointId.value = definitions.value[0]?.id ?? ''
  } catch (cause) {
    if (current !== generation) return
    error.value = cause instanceof Error ? cause.message : '监测查询失败'
    readings.value = []
    definitions.value = []
    pointId.value = ''
  } finally {
    if (current === generation) loading.value = false
  }
}

/** 范围锚定最新采样，便于查看一次性导入的旧快照；标签明确说明不是“现在的24小时”。 */
watch([pointId, hours, selectedLatest], async () => {
  const current = ++historyGeneration
  history.value = undefined
  historyError.value = ''
  historyLoading.value = false
  if (!pointId.value || !selectedLatest.value?.sampledAt) return
  historyLoading.value = true
  const end = new Date(Date.parse(selectedLatest.value.sampledAt) + 1)
  const start = new Date(end.getTime() - hours.value * 3600000)
  try {
    const result = await api.getHistory(pointId.value, start.toISOString(), end.toISOString())
    if (current === historyGeneration) history.value = result.data
  } catch (cause) {
    if (current === historyGeneration)
      historyError.value = cause instanceof Error ? cause.message : '历史查询失败'
  } finally {
    if (current === historyGeneration) historyLoading.value = false
  }
})
watch(
  () => [props.deviceId, props.pointIds.join(','), auth.scopeKey, auth.can('monitor:read')],
  () => {
    generation++
    historyGeneration++
    definitions.value = []
    readings.value = []
    pointId.value = ''
    history.value = undefined
    loading.value = false
    historyLoading.value = false
    void load()
  },
  { immediate: true },
)
const timer = setInterval(() => {
  if (automatic.value && !document.hidden) void load()
}, 30000)
onUnmounted(() => {
  generation++
  historyGeneration++
  clearInterval(timer)
})
/** 仅显示北京时间；无采样不伪造时间。 */
function formatTime(value?: string | null) {
  return value
    ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
    : '未采集'
}
</script>

<style scoped>
.device-monitoring {
  font-size: 14px;
  min-width: 0;
  line-height: 1.6;
}
.monitor-heading,
.monitor-readings > div,
.monitor-history-list > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.monitor-heading h3 {
  font-size: 16px;
  margin: 0;
}
.device-monitoring button,
.device-monitoring select {
  border: 1px solid var(--ocean-border);
  border-radius: 10px;
  background: #0c2b49;
  color: var(--ocean-text);
  padding: 7px 9px;
  font: inherit;
}
.device-monitoring button {
  cursor: pointer;
  white-space: nowrap;
}
.device-monitoring button:disabled {
  opacity: 0.6;
}
.monitor-note,
.monitor-auto {
  color: var(--ocean-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.monitor-error {
  color: var(--amber);
  overflow-wrap: anywhere;
}
.monitor-readings {
  margin: 10px 0;
}
.monitor-readings > div {
  padding: 9px 0;
  border-bottom: 1px solid #28618c55;
}
.monitor-readings dt {
  min-width: 0;
}
.monitor-readings dt small {
  display: block;
  color: var(--ocean-muted);
  font-size: 11px;
}
.monitor-readings dd {
  margin: 0;
  font-size: 18px;
  color: var(--ocean-cyan);
  overflow-wrap: anywhere;
  text-align: right;
}
.monitor-readings dd small {
  font-size: 12px;
}
.monitor-readings dd.muted {
  color: var(--amber);
}
.monitor-auto {
  display: flex;
  align-items: center;
  gap: 6px;
}
.monitor-history {
  border-top: 1px solid var(--ocean-border);
  margin-top: 14px;
  padding-top: 10px;
}
.monitor-history h4 {
  margin: 0 0 8px;
  font-size: 15px;
}
.monitor-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
}
.monitor-controls select {
  min-width: 0;
  width: 100%;
}
.device-monitoring svg {
  display: block;
  width: 100%;
  margin-top: 10px;
}
.monitor-grid {
  stroke: #28618c88;
  fill: none;
  stroke-dasharray: 3 5;
}
.monitor-line {
  stroke: var(--ocean-cyan);
  stroke-width: 2;
  fill: none;
  stroke-linejoin: round;
}
.monitor-dot {
  fill: var(--ocean-cyan);
}
.monitor-history-list {
  font-size: 11px;
  color: var(--ocean-secondary);
}
.monitor-history-list > div {
  flex-wrap: wrap;
  padding: 3px 0;
}
</style>
