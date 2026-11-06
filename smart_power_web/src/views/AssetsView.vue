<template>
  <section class="assets-page" aria-labelledby="assets-title">
    <header class="assets-heading">
      <div>
        <p class="auth-eyebrow">ASSET MANAGEMENT</p>
        <h1 id="assets-title">站点与设备台账</h1>
      </div>
      <RouterLink to="/overview">← 返回地图工作台</RouterLink>
    </header>
    <p class="asset-note">
      台账状态与现场在线状态分开；模拟身份创建后固定。新站只授权当前创建者，其他账号由账号管理分配。完整WGS84坐标的站点可进入地图，三维场景需另行发布。
    </p>
    <p v-if="error" role="alert" class="asset-error">{{ error }}</p>
    <p v-if="message" role="status" class="asset-success">{{ message }}</p>
    <div class="assets-grid">
      <section class="asset-panel">
        <h2>
          授权站点 <small>{{ total }} 座</small>
        </h2>
        <form class="asset-search" @submit.prevent="searchSites">
          <input
            v-model="query"
            aria-label="搜索站点"
            placeholder="名称 / 编码 / 城市 / 路线"
            maxlength="120"
          /><button :disabled="busy || loading">查询</button>
        </form>
        <button v-if="auth.can('site:create')" :disabled="busy" @click="open('site')">
          ＋ 新增站点
        </button>
        <p v-if="loading">正在读取站点…</p>
        <div class="asset-sites">
          <button
            v-for="row in sites"
            :key="row.id"
            :class="{ selected: site?.id === row.id }"
            :disabled="busy || editLoading"
            @click="chooseSite(row)"
          >
            <strong>{{ row.name }}</strong
            ><span>{{ row.code }} · ID {{ row.id }}</span
            ><small
              >{{ row.cityName || '城市未填' }} · {{ row.isDemo ? '模拟' : '现场' }} ·
              {{ statusLabel(row.assetStatus) }}</small
            >
          </button>
        </div>
        <p v-if="!sites.length && !loading">当前范围没有匹配站点。</p>
        <div class="asset-actions">
          <button :disabled="page <= 1 || loading || busy" @click="turnSitePage(-1)">上一页</button
          ><span>第 {{ page }} 页</span
          ><button :disabled="page * 20 >= total || loading || busy" @click="turnSitePage(1)">
            下一页
          </button>
        </div>
      </section>
      <section class="asset-panel">
        <template v-if="site"
          ><h2>{{ site.name }}</h2>
          <p class="asset-note">
            {{ site.code }} · {{ site.siteType === 'SERVICE' ? '服务区' : '收费站' }} ·
            {{ site.scaleLevel }} · {{ site.coordinateSystem }} ·
            {{ site.longitude ?? '未填经度' }}, {{ site.latitude ?? '未填纬度' }}
          </p>
          <div class="asset-actions">
            <RouterLink :to="{ path: '/admin/site-relations', query: { siteId: site.id } }"
              >维护本站区域 / 高速关联</RouterLink
            >
            <RouterLink
              v-if="auth.can('twin:read')"
              :to="{ path: '/admin/scenes', query: { siteId: site.id } }"
              >配置本站三维场景 →</RouterLink
            >
            <button
              v-if="auth.can('asset:manage')"
              :disabled="busy || editLoading"
              @click="open('site', site)"
            >
              编辑站点 / 停用</button
            ><button
              v-if="auth.can('asset:manage')"
              :disabled="site.assetStatus !== 'ACTIVE' || busy || editLoading"
              @click="open('device')"
            >
              ＋ 新增设备
            </button>
          </div>
          <form class="asset-search" @submit.prevent="searchDevices">
            <input
              v-model="deviceQuery"
              aria-label="搜索设备"
              placeholder="设备名称 / 编码"
              maxlength="120"
            /><button :disabled="deviceLoading || busy">查询设备</button>
          </form>
          <p v-if="deviceLoading">正在读取设备…</p>
          <div class="asset-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>设备 / 编码 / ID</th>
                  <th>系统 / 状态</th>
                  <th>来源</th>
                  <th>额定参数</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="device in devices" :key="device.id">
                  <td>
                    {{ device.name }}<small>{{ device.code }} · {{ device.id }}</small>
                  </td>
                  <td>
                    {{ device.systemType }}<small>{{ statusLabel(device.assetStatus) }}</small>
                  </td>
                  <td>{{ device.isDemo ? '模拟' : '现场' }}</td>
                  <td>
                    {{ device.ratedPowerKw ?? '—' }} kW<small
                      >{{ device.ratedEnergyKwh ?? '—' }} kWh /
                      {{ device.ratedCapacityKva ?? '—' }} kVA</small
                    >
                  </td>
                  <td>
                    <RouterLink
                      v-if="auth.can('monitor:read') && auth.can('device:read')"
                      class="asset-point-link"
                      :to="{
                        path: '/admin/points',
                        query: { siteId: site.id, deviceId: device.id },
                      }"
                      >测点</RouterLink
                    >
                    <button
                      v-if="auth.can('asset:manage')"
                      :disabled="busy || editLoading"
                      @click="open('device', device)"
                    >
                      编辑 / 停用</button
                    ><span v-else>只读</span>
                  </td>
                </tr>
                <tr v-if="!devices.length && !deviceLoading">
                  <td colspan="5">本站无匹配设备或尚未授权设备查询。</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="asset-actions">
            <button
              :disabled="devicePage <= 1 || deviceLoading || busy"
              @click="turnDevicePage(-1)"
            >
              上一页</button
            ><span>{{ deviceTotal }} 台 · 第 {{ devicePage }} 页</span
            ><button
              :disabled="devicePage * 20 >= deviceTotal || deviceLoading || busy"
              @click="turnDevicePage(1)"
            >
              下一页
            </button>
          </div>
        </template>
        <p v-else>
          {{ editLoading ? '正在读取本站资料…' : '先从左侧选择一个站点，再维护本站设备。' }}
        </p>
      </section>
    </div>
    <section v-if="editor" ref="editorPanel" class="asset-panel asset-editor">
      <h2>{{ editor.record ? '编辑' : '新增' }}{{ editor.kind === 'site' ? '站点' : '设备' }}</h2>
      <AssetForm
        :key="`${editor.kind}:${editor.record?.id ?? 'new'}`"
        :kind="editor.kind"
        :record="editor.record"
        :busy="busy"
        :areas="areas"
        :highways="highways"
        @save="save"
        @cancel="cancel"
      />
    </section>
  </section>
</template>
<script setup lang="ts">
/** 台账管理页：只负责布局和交互；列表/保存/权限竞态由composable统一处理。 */
import { ref, watch, nextTick } from 'vue'
import AssetForm from '@/components/assets/AssetForm.vue'
import { useAssetMaintenance } from '@/composables/useAssetMaintenance'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
const {
  sites,
  total,
  page,
  query,
  loading,
  error,
  message,
  site,
  devices,
  deviceTotal,
  devicePage,
  deviceQuery,
  deviceLoading,
  editLoading,
  areas,
  highways,
  editor,
  busy,
  loadSites,
  loadDevices,
  chooseSite,
  open,
  save,
  cancel,
} = useAssetMaintenance()
/** 页码与搜索由命名事件处理，避免模板内多条语句在格式化后失去分隔。 */
function searchSites() {
  page.value = 1
  void loadSites()
}
function searchDevices() {
  devicePage.value = 1
  void loadDevices()
}
function turnSitePage(delta: number) {
  page.value += delta
  void loadSites()
}
function turnDevicePage(delta: number) {
  devicePage.value += delta
  void loadDevices()
}
const editorPanel = ref<HTMLElement>()
watch(editor, async (value) => {
  if (value) {
    await nextTick()
    editorPanel.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
})
const statusLabel = (status: string) =>
  ({ ACTIVE: '有效', INACTIVE: '停用', RETIRED: '退役', MAINTENANCE: '维护' })[
    status as 'ACTIVE'
  ] ?? status
</script>
<style>
.assets-page {
  padding: 24px;
  max-width: 1500px;
  margin: auto;
  color: #d8efff;
}
.assets-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 16px;
}
.assets-heading h1 {
  font-size: 26px;
}
.assets-grid {
  display: grid;
  grid-template-columns: minmax(260px, 0.7fr) minmax(0, 1.6fr);
  gap: 18px;
}
.asset-panel {
  padding: 20px;
  border: 1px solid #36738e;
  border-radius: 20px;
  background: linear-gradient(140deg, #164366dd, #0b2844ee);
  min-width: 0;
}
.asset-panel h2 {
  margin: 0 0 16px;
  font-size: 20px;
}
.asset-panel h2 small {
  font-size: 13px;
}
.assets-page button,
.assets-page input,
.assets-page select {
  font: inherit;
  font-size: 14px;
  border: 1px solid #4b8ca7;
  border-radius: 9px;
  padding: 9px;
  color: #def4ff;
  background: #103452;
}
.assets-page button {
  cursor: pointer;
}
.assets-page button:disabled {
  opacity: 0.45;
  cursor: default;
}
.asset-note {
  font-size: 13px;
  line-height: 1.8;
  color: #a8cddd;
}
.asset-error {
  color: #ffd084;
  overflow-wrap: anywhere;
}
.asset-success {
  color: #62e6dc;
}
.asset-search {
  display: flex;
  gap: 8px;
  margin: 15px 0;
}
.asset-search input {
  min-width: 0;
  flex: 1;
}
.asset-sites {
  display: grid;
  gap: 8px;
  margin: 14px 0;
  max-height: 550px;
  overflow: auto;
}
.asset-sites button {
  text-align: left;
  display: grid;
  gap: 5px;
}
.asset-sites button.selected {
  background: #195782;
  border-color: #52e2f1;
}
.asset-sites span,
.asset-sites small {
  font-size: 12px;
  color: #9acada;
  overflow-wrap: anywhere;
}
.asset-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 12px;
}
.asset-point-link {
  display: inline-block;
  margin-right: 10px;
}
.asset-table-wrap {
  overflow: auto;
}
.asset-table-wrap table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.asset-table-wrap th,
.asset-table-wrap td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #34718c66;
  white-space: nowrap;
}
.asset-table-wrap small {
  display: block;
  color: #9fc6d8;
  margin-top: 4px;
}
.asset-editor {
  margin-top: 18px;
}
.asset-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.asset-form label {
  display: grid;
  gap: 7px;
  font-size: 14px;
  min-width: 0;
}
.asset-form input,
.asset-form select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.asset-form > .asset-note,
.asset-form > .asset-actions {
  grid-column: 1/-1;
}
.asset-editor {
  scroll-margin-top: 20px;
}
@media (max-width: 900px) {
  .assets-grid {
    grid-template-columns: 1fr;
  }
  .asset-sites {
    max-height: 330px;
  }
}
@media (max-width: 560px) {
  .assets-page {
    padding: 12px;
  }
  .asset-form {
    grid-template-columns: 1fr;
  }
  .assets-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .asset-panel {
    padding: 14px;
  }
}
</style>
