<template>
  <section class="alarm-panel" aria-label="站点数据库告警">
    <div class="alarm-heading">
      <strong>本站告警 · {{ total }} 条匹配</strong>
      <button :disabled="loading || busy" @click="refresh">刷新</button>
    </div>
    <p class="alarm-note">MySQL事件记录 · 模拟/现场来源见详情；状态截至最近一次读取。</p>
    <div class="alarm-filters">
      <select v-model="status" aria-label="告警状态">
        <option value="">全部状态</option>
        <option value="ACTIVE">活动</option>
        <option value="RECOVERED">已恢复</option>
        <option value="CLOSED">已关闭</option>
      </select>
      <select v-model="severity" aria-label="告警级别">
        <option value="">全部级别</option>
        <option value="INFO">提示</option>
        <option value="MINOR">一般</option>
        <option value="MAJOR">重要</option>
        <option value="CRITICAL">紧急</option>
      </select>
      <select v-model="acknowledged" aria-label="告警确认状态">
        <option value="">全部确认状态</option>
        <option value="false">未确认</option>
        <option value="true">已确认</option>
      </select>
    </div>
    <p v-if="error" class="alarm-error" role="alert">{{ error }}</p>
    <p v-else-if="loading">正在查询…</p>
    <p v-else-if="!rows.length" class="alarm-note">当前筛选无记录，不代表设备已恢复或在线。</p>
    <div v-else class="alarm-list">
      <button
        v-for="item in rows"
        :key="item.id"
        :class="{ selected: detail?.id === item.id }"
        :disabled="busy"
        @click="open(item.id)"
      >
        <span class="alarm-item-title">{{ item.message }}</span>
        <small
          >{{ statusLabels[item.status] }} · {{ severityLabels[item.severity] }} ·
          {{ item.acknowledgedAt ? '已确认' : '未确认' }}</small
        >
        <small
          >{{
            item.isDemo || item.source === 'SIMULATED'
              ? '模拟'
              : item.source === 'FIELD'
                ? '现场来源'
                : '来源待核验'
          }}
          · {{ formatTime(item.raisedAt) }}</small
        >
      </button>
    </div>
    <div class="alarm-pagination">
      <button :disabled="loading || busy || page <= 1" @click="page--">上一页</button>
      <span>第 {{ page }} 页</span>
      <button :disabled="loading || busy || !hasNext" @click="page++">下一页</button>
    </div>
    <p v-if="detailLoading" class="alarm-note">正在读取事件详情…</p>
    <p v-if="detailError" class="alarm-error" role="alert">{{ detailError }}</p>
    <article v-if="detail" class="alarm-detail">
      <h4>{{ detail.message }}</h4>
      <p>{{ detail.deviceName ?? '站点级事件' }} · {{ detail.pointName ?? '无关联测点' }}</p>
      <p>{{ detail.isDemo ? '演示资产' : '非演示资产' }} · {{ detail.source }}</p>
      <dl>
        <dt>发生</dt>
        <dd>{{ formatTime(detail.raisedAt) }}</dd>
        <dt>恢复</dt>
        <dd>{{ formatTime(detail.recoveredAt) }}</dd>
        <dt>确认</dt>
        <dd>{{ formatTime(detail.acknowledgedAt) }} {{ detail.acknowledgedByName ?? '' }}</dd>
      </dl>
      <p v-if="detail.handlingNote">处理说明：{{ detail.handlingNote }}</p>
      <details>
        <summary>发生时阈值与数据快照</summary>
        <pre>{{ JSON.stringify(detail.triggerSnapshot, null, 2) }}</pre>
      </details>
      <button v-if="detail.deviceId" class="alarm-locate" @click="emit('locate', detail)">
        定位关联设备 ↗
      </button>
      <template v-if="canAck || canClose">
        <label class="alarm-note" for="alarm-handling-note">本次处理说明（可选）</label>
        <textarea
          id="alarm-handling-note"
          v-model="note"
          maxlength="1000"
          :disabled="busy"
          rows="2"
        />
        <div class="alarm-actions">
          <button v-if="canAck" :disabled="busy" @click="act('acknowledge')">确认告警</button>
          <button v-if="canClose" :disabled="busy" @click="act('close')">关闭事件</button>
        </div>
      </template>
      <p v-if="detail.status === 'ACTIVE'" class="alarm-note">
        活动事件不能关闭；确认只表示已知晓，不代表故障恢复。
      </p>
      <p v-if="feedback" role="status">{{ feedback }}</p>
    </article>
  </section>
</template>

<script setup lang="ts">
/** 站点告警面板：筛选/详情/确认/关闭/定位；不改变地图和模型样式，不以演示告警兜底。 */
import { computed, toRef } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAlarmEvents } from '@/composables/useAlarmEvents'
import type { AlarmEvent, AlarmSeverity, AlarmStatus } from '@/types/alarms'
const props = defineProps<{ siteCode: string }>()
const emit = defineEmits<{ locate: [event: AlarmEvent] }>()
const auth = useAuthStore()
const {
  rows,
  total,
  page,
  hasNext,
  status,
  severity,
  acknowledged,
  loading,
  error,
  detail,
  detailLoading,
  detailError,
  busy,
  note,
  feedback,
  load,
  open,
  act,
} = useAlarmEvents(toRef(props, 'siteCode'))
const statusLabels: Record<AlarmStatus, string> = {
  ACTIVE: '活动',
  RECOVERED: '已恢复',
  CLOSED: '已关闭',
}
const severityLabels: Record<AlarmSeverity, string> = {
  INFO: '提示',
  MINOR: '一般',
  MAJOR: '重要',
  CRITICAL: '紧急',
}
const canAck = computed(
  () =>
    auth.can('alarm:ack') &&
    detail.value &&
    !detail.value.acknowledgedAt &&
    detail.value.status !== 'CLOSED',
)
const canClose = computed(
  () =>
    auth.can('alarm:close') &&
    detail.value?.status === 'RECOVERED' &&
    !!detail.value.acknowledgedAt,
)
/** 服务端UTC时间仅在展示层转换为北京时间，空值保持缺失。 */
function formatTime(value: string | null) {
  return value
    ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
    : '—'
}
/** 手动刷新列表与仍选中的详情，不以本地时钟推测事件恢复状态。 */
async function refresh() {
  await load()
  if (detail.value) await open(detail.value.id)
}
</script>

<style scoped>
.alarm-panel {
  min-width: 0;
  font-size: 13px;
  line-height: 1.65;
}
.alarm-heading,
.alarm-pagination,
.alarm-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.alarm-panel button,
.alarm-panel select,
.alarm-panel textarea {
  color: #d9f4ff;
  background: #0c314dd9;
  border: 1px solid #387995;
  border-radius: 8px;
  padding: 7px 9px;
  font: inherit;
}
.alarm-panel button {
  cursor: pointer;
}
.alarm-panel button:disabled {
  opacity: 0.45;
  cursor: default;
}
.alarm-panel button:focus-visible,
.alarm-panel select:focus-visible,
.alarm-panel textarea:focus-visible {
  outline: 2px solid #62e5ff;
  outline-offset: 2px;
}
.alarm-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0;
}
.alarm-filters select {
  min-width: 0;
  flex: 1 1 95px;
}
.alarm-note {
  font-size: 12px;
  color: #96c4da;
}
.alarm-error {
  color: #ffce91;
  overflow-wrap: anywhere;
}
.alarm-list {
  display: grid;
  gap: 7px;
  max-height: 240px;
  overflow: auto;
}
.alarm-list button {
  text-align: left;
  width: 100%;
  overflow-wrap: anywhere;
}
.alarm-list button.selected {
  border-color: #52d8ef;
  background: #18567ac9;
}
.alarm-item-title,
.alarm-list small {
  display: block;
}
.alarm-list small {
  color: #a0c7da;
  font-size: 12px;
}
.alarm-pagination {
  margin-top: 10px;
  font-size: 12px;
}
.alarm-detail {
  border-top: 1px solid #3f7c9559;
  margin-top: 12px;
  padding-top: 10px;
  overflow-wrap: anywhere;
}
.alarm-detail h4 {
  margin: 0;
  font-size: 14px;
}
.alarm-detail dl {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 5px;
  font-size: 12px;
}
.alarm-detail dd {
  margin: 0;
}
.alarm-detail pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 160px;
  overflow: auto;
  font-size: 12px;
}
.alarm-detail summary {
  cursor: pointer;
  color: #81d9f4;
}
.alarm-detail textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
}
.alarm-locate {
  margin: 8px 0;
}
</style>
