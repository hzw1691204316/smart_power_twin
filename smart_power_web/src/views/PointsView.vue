<template>
  <section class="points-page" aria-labelledby="points-title">
    <header class="points-heading">
      <div>
        <p class="auth-eyebrow">MONITORING POINT MANAGEMENT</p>
        <h1 id="points-title">设备测点管理</h1>
      </div>
      <nav>
        <RouterLink to="/admin/assets">站点与设备台账</RouterLink
        ><RouterLink
          v-if="auth.can('twin:read')"
          :to="{ path: '/admin/scenes', query: siteId ? { siteId } : {} }"
          >三维场景配置 →</RouterLink
        ><RouterLink to="/overview">返回地图</RouterLink>
      </nav>
    </header>
    <p class="points-note">
      先选站点与设备，再维护测点。定义保存后即可到三维场景配置中建立绑定；没有采样时显示缺测，不生成模拟读数。
    </p>
    <p v-if="error" role="alert" class="points-error">{{ error }}</p>
    <p v-if="message" role="status" class="points-success">{{ message }}</p>
    <p v-if="busy" role="status">正在读取或保存，请稍候…</p>
    <div class="points-grid">
      <section class="points-panel">
        <h2>1. 选择本站设备</h2>
        <label class="points-label"
          >授权站点<select v-model="siteId" :disabled="busy || !!editor" @change="chooseSite">
            <option value="">无可用站点</option>
            <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select></label
        >
        <form class="points-search" @submit.prevent="searchDevices">
          <input
            v-model="deviceQuery"
            placeholder="设备名称 / 编码"
            aria-label="搜索本站设备"
            maxlength="120"
            :disabled="busy || !!editor"
          /><button :disabled="busy || !!editor || !siteId">查找</button>
        </form>
        <div class="points-devices">
          <button
            v-for="d in devices"
            :key="d.id"
            :disabled="busy || !!editor"
            :class="{ selected: d.id === device?.id }"
            @click="chooseDevice(d)"
          >
            <strong>{{ d.name }}</strong
            ><small>{{ d.code }} · {{ d.systemType }}</small
            ><small
              >{{ d.isDemo ? '模拟设备' : '现场设备' }} · {{ statusName(d.assetStatus) }}</small
            >
          </button>
        </div>
        <p v-if="!devices.length && !busy" class="points-note">
          本站暂无匹配设备。请先在台账中新增设备，或调整搜索条件。
        </p>
        <div class="points-actions">
          <button :disabled="busy || !!editor || devicePage <= 1" @click="turnDevicePage(-1)">
            上一页</button
          ><span>{{ devicePage }} 页 / {{ deviceTotal }} 台</span
          ><button
            :disabled="busy || !!editor || devicePage * 20 >= deviceTotal"
            @click="turnDevicePage(1)"
          >
            下一页
          </button>
        </div>
        <p class="points-note">
          台账“有效/停用”与设备在线状态是两个概念；本页管理测点定义，不直接控制现场设备。
        </p>
      </section>
      <div class="points-main">
        <section class="points-panel">
          <template v-if="device">
            <h2>2. {{ device.name }} 的测点</h2>
            <p class="points-note">
              {{ site?.name }} · 设备ID {{ device.id }} ·
              {{ device.isDemo ? 'SIMULATED · 模拟来源' : 'FIELD · 现场来源' }} ·
              <template v-if="pointsLoaded"
                >共 {{ points.length }} 项，启用
                {{ points.filter((p) => p.enabled).length }} 项</template
              ><template v-else>测点尚未读取成功</template>
            </p>
            <div class="points-actions">
              <button v-if="editable" :disabled="busy || !!editor || !pointsLoaded" @click="open()">
                ＋ 新增测点</button
              ><button :disabled="busy || !!editor" @click="reloadPoints">重读测点</button
              ><input
                v-model="pointQuery"
                aria-label="筛选测点"
                placeholder="筛选名称 / 编码 / 单位"
                maxlength="120"
              />
            </div>
            <p v-if="!editable" class="points-note">
              当前账号只读；新增和修改需要 monitor:configure 权限。
            </p>
            <div class="points-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>测点 / 编码</th>
                    <th>单位 / 类型</th>
                    <th>周期 / 陈旧时间</th>
                    <th>低 / 高阈值</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in visiblePoints" :key="p.id">
                    <td>
                      {{ p.name }}<small>{{ p.code }} · ID {{ p.id }}</small>
                    </td>
                    <td>
                      {{ p.unit }}<small>{{ p.valueType }} / {{ p.aggregationType }}</small>
                    </td>
                    <td>
                      {{ p.sampleIntervalMs }} ms<small>{{ p.staleAfterMs }} ms</small>
                    </td>
                    <td>{{ p.alarmLow ?? '未设置' }} / {{ p.alarmHigh ?? '未设置' }}</td>
                    <td>{{ p.enabled ? '接收样本' : '已停用' }}</td>
                    <td>
                      <button v-if="editable" :disabled="busy || !!editor" @click="open(p)">
                        配置 / 启停</button
                      ><span v-else>只读</span>
                    </td>
                  </tr>
                  <tr v-if="!visiblePoints.length && !busy">
                    <td colspan="6">
                      {{
                        pointQuery.trim()
                          ? '没有匹配的测点，请调整筛选。'
                          : error
                            ? '测点读取未完成，请重读。'
                            : '该设备尚无测点，可以新增定义。'
                      }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
          <p v-else class="points-note">选择一个获授权设备后查看测点定义。</p>
        </section>
        <section v-if="editor && device" ref="editorPanel" class="points-panel points-editor">
          <h2>3. {{ editor.record ? '调整测点配置' : '新增测点定义' }}</h2>
          <p class="points-note">
            当前设备：{{
              device.name
            }}。编辑期间请先保存或取消，再切换站点、设备和分页；离开页面会丢弃未保存内容。
          </p>
          <PointForm
            :key="`${device.id}:${editor.record?.id ?? 'new'}`"
            :record="editor.record"
            :busy="busy"
            @save="save"
            @cancel="cancel"
          />
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/** 测点管理页面：负责列表/表单布局；身份隔离、目录读取及写入由composable处理。 */
import { nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PointForm from '@/components/monitoring/PointForm.vue'
import { useAuthStore } from '@/stores/auth'
import { usePointMaintenance } from '@/composables/usePointMaintenance'
const auth = useAuthStore(),
  route = useRoute()
const {
  sites,
  siteId,
  site,
  devices,
  device,
  devicePage,
  deviceTotal,
  deviceQuery,
  points,
  pointsLoaded,
  pointQuery,
  visiblePoints,
  editor,
  editable,
  busy,
  error,
  message,
  chooseSite,
  chooseDevice,
  loadDevices,
  reloadPoints,
  open,
  save,
  cancel,
} = usePointMaintenance(
  typeof route.query.siteId === 'string' ? route.query.siteId : '',
  typeof route.query.deviceId === 'string' ? route.query.deviceId : '',
)
/** 查询和翻页使用命名处理函数，避免模板多语句在格式化后改变解析结果。 */
function searchDevices() {
  devicePage.value = 1
  void loadDevices()
}
function turnDevicePage(delta: number) {
  devicePage.value += delta
  void loadDevices()
}
const statusName = (status: string) =>
  ({ ACTIVE: '有效', MAINTENANCE: '维护', INACTIVE: '停用', RETIRED: '退役' })[status] ?? status
const editorPanel = ref<HTMLElement>()
watch(editor, async (value) => {
  if (value) {
    await nextTick()
    editorPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
})
</script>

<style scoped>
.points-page {
  max-width: 1600px;
  margin: auto;
  padding: 24px;
  color: var(--ocean-text, #d8efff);
}
.points-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
h1 {
  font-size: 26px;
}
h2 {
  font-size: 20px;
  margin: 0 0 16px;
}
nav,
.points-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.points-grid {
  display: grid;
  grid-template-columns: minmax(260px, 0.7fr) minmax(0, 2fr);
  gap: 18px;
  align-items: start;
}
.points-panel {
  min-width: 0;
  padding: 20px;
  border: 1px solid #36738e;
  border-radius: 20px;
  background: linear-gradient(140deg, #164366dd, #0b2844ee);
}
.points-main {
  min-width: 0;
  display: grid;
  gap: 18px;
}
.points-label {
  display: grid;
  gap: 8px;
}
input,
select,
button {
  font: inherit;
  font-size: 14px;
  padding: 10px;
  color: #def4ff;
  background: #103452;
  border: 1px solid #4b8ca7;
  border-radius: 9px;
  min-width: 0;
}
button {
  cursor: pointer;
}
:disabled {
  opacity: 0.5;
  cursor: default;
}
.points-search {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}
.points-search input {
  flex: 1;
  width: 0;
}
.points-devices {
  display: grid;
  gap: 8px;
  max-height: 530px;
  overflow: auto;
  margin-bottom: 16px;
}
.points-devices button {
  display: grid;
  gap: 6px;
  text-align: left;
}
.points-devices .selected {
  border-color: #52e2f1;
  background: #195782;
}
.points-note {
  color: #a8cddd;
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}
.points-error {
  color: #ffd084;
  overflow-wrap: anywhere;
}
.points-success {
  color: #62e6dc;
  overflow-wrap: anywhere;
}
.points-table-wrap {
  overflow: auto;
  max-height: 560px;
  margin-top: 16px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
th,
td {
  padding: 12px 10px;
  text-align: left;
  border-bottom: 1px solid #34718c66;
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  background: #103452;
}
td small {
  display: block;
  margin-top: 5px;
}
small {
  color: #9fc6d8;
  font-size: 12px;
}
.points-editor {
  scroll-margin-top: 20px;
}
@media (max-width: 1050px) {
  .points-grid {
    grid-template-columns: 1fr;
  }
  .points-devices {
    max-height: 260px;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 650px) {
  .points-page {
    padding: 12px;
  }
  .points-heading {
    flex-direction: column;
    align-items: flex-start;
  }
  .points-panel {
    padding: 14px;
  }
  .points-devices {
    grid-template-columns: 1fr;
  }
}
</style>
