<template>
  <section class="dashboard-summary" aria-label="授权业务大屏汇总">
    <div class="dashboard-controls">
      <label
        >设备与功率来源<select
          :value="source"
          aria-label="汇总数据来源"
          @change="
            emit('update:source', ($event.target as HTMLSelectElement).value as DashboardSource)
          "
        >
          <option value="FIELD">现场数据</option>
          <option value="SIMULATED">模拟数据</option>
        </select></label
      >
      <button :disabled="loading" @click="emit('refresh')">刷新</button>
    </div>
    <p v-if="loading" role="status">正在读取数据库汇总…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <template v-else-if="data">
      <p class="dashboard-scope">
        {{ data.siteCount }} 个授权站点（{{ data.demoSiteCount }} 个模拟台账） ·
        {{ data.serviceCount }} 服务区 / {{ data.tollCount }} 收费站
      </p>
      <dl class="dashboard-counts">
        <div>
          <dt>所选来源设备</dt>
          <dd>{{ data.deviceCount }}</dd>
        </div>
        <div>
          <dt>数据正常 / 关注</dt>
          <dd>{{ data.deviceStates.normal }} / {{ data.deviceStates.warning }}</dd>
        </div>
        <div>
          <dt>无有效新值 / 未知</dt>
          <dd>{{ data.deviceStates.offline }} / {{ data.deviceStates.unknown }}</dd>
        </div>
        <div>
          <dt>活动 / 待确认告警</dt>
          <dd>{{ data.activeAlarmCount }} / {{ data.unacknowledgedAlarmCount }}</dd>
        </div>
      </dl>
      <article v-for="item in systems" :key="item.key" class="dashboard-power">
        <div>
          <span>{{ item.label }}</span
          ><strong>{{ formatPower(data.power[item.key].valueKw) }} <small>kW</small></strong>
        </div>
        <p>
          覆盖 {{ data.power[item.key].contributingSites }} /
          {{ data.power[item.key].eligibleSites }} 站
          <span v-if="data.power[item.key].isPartial"> · 缺测或部分覆盖</span
          ><span v-if="data.power[item.key].ambiguousSites">
            · {{ data.power[item.key].ambiguousSites }} 站口径待配置</span
          >
        </p>
        <small v-if="data.power[item.key].oldestSampledAt"
          >采样 {{ clock(data.power[item.key].oldestSampledAt) }} —
          {{ clock(data.power[item.key].newestSampledAt) }}</small
        >
      </article>
      <details>
        <summary>汇总口径 · {{ source === 'SIMULATED' ? '模拟数据' : '现场数据' }}</summary>
        <p>{{ data.note }}</p>
        <p>
          “无有效新值”不等于设备故障。日用电尚未建立计量边界；不同系统功率不可直接相加。当前没有有效值时显示“—”。
        </p>
        <p>计算于 {{ clock(data.asOf) }}（北京时间），刷新不会启动采集。</p>
      </details>
    </template>
  </section>
</template>
<script setup lang="ts">
/** 汇总展示组件：只接收数据、加载/错误状态与来源，手动刷新和切来源由父页面管理。 */
import type { DashboardSource, DashboardSummary } from '@/types/dashboard'
defineProps<{ data?: DashboardSummary; loading: boolean; error: string; source: DashboardSource }>()
const emit = defineEmits<{ refresh: []; 'update:source': [DashboardSource] }>()
const systems = [
  { key: 'GRID', label: '并网点代表功率' },
  { key: 'PV', label: '光伏代表功率' },
  { key: 'ESS', label: '储能代表功率' },
  { key: 'CHARGING', label: '充电代表功率' },
] as const
/** 明确区分0与缺测，避免模板对重复索引的空值判断失效。 */
const formatPower = (value: number | null) => (value === null ? '—' : value.toFixed(1))
/** UTC采样/计算时间以北京时间展示；空值不能推算成当前时刻。 */
const clock = (value: string | null) =>
  value
    ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
    : '—'
</script>
<style scoped>
.dashboard-summary {
  color: #c6e6f4;
  font-size: 13px;
  line-height: 1.6;
  min-width: 0;
}
.dashboard-controls {
  display: flex;
  gap: 8px;
  align-items: end;
  flex-wrap: wrap;
}
.dashboard-controls label {
  display: grid;
  gap: 4px;
  flex: 1;
  min-width: 120px;
}
.dashboard-controls select,
.dashboard-controls button {
  background: #103855;
  color: #dcf3ff;
  border: 1px solid #4385a4;
  border-radius: 8px;
  padding: 7px;
  font: inherit;
}
.dashboard-controls button:disabled {
  opacity: 0.5;
}
.dashboard-scope {
  margin: 12px 0;
}
.dashboard-counts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0;
}
.dashboard-counts div {
  min-width: 0;
}
.dashboard-counts dt {
  color: #a4cbdc;
}
.dashboard-counts dd {
  margin: 0;
  font-size: 19px;
  font-weight: 650;
  color: #e3f6ff;
}
.dashboard-power {
  border-top: 1px solid #38728b66;
  padding: 10px 0;
}
.dashboard-power > div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.dashboard-power strong {
  font-size: 19px;
  color: #69e4f5;
}
.dashboard-power strong small {
  font-size: 12px;
}
.dashboard-power p {
  margin: 3px 0;
  font-size: 12px;
  color: #a6cada;
}
.dashboard-power > small {
  font-size: 11px;
}
.dashboard-summary details {
  border-top: 1px solid #38728b66;
  padding-top: 8px;
  overflow-wrap: anywhere;
}
.dashboard-summary summary {
  cursor: pointer;
}
.dashboard-summary p {
  overflow-wrap: anywhere;
}
</style>
