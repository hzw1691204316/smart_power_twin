<template>
  <div class="dashboard-view overview-workspace">
    <MapWorkspaceLayout class="overview-grid" v-model:panels-visible="panelsVisible">
      <template #left>
        <PanelCard title="省域工作空间" eyebrow="REGIONAL WORKSPACE"
          ><div class="sidebar-metrics" aria-label="演示站点统计">
            <MetricCard
              label="授权业务站点"
              :value="summaryData?.siteCount ?? '—'"
              unit="座"
              hint="来自数据库授权台账"
            /><MetricCard
              label="有效台账站点"
              :value="summaryData?.activeSiteCount ?? '—'"
              unit="座"
              hint="ACTIVE台账状态，不代表设备在线"
            />
          </div>
          <MapDisplayControls
            scope="china"
            title="中国 · 省域选择"
            :status="mapStatus"
            v-model:theme="mapTheme"
            v-model:tilted="mapTilted"
            @reset="mapStage?.resetView()"
          />
          <label class="sidebar-city-picker province-switcher"
            >省域快速进入
            <select
              :value="province.code"
              aria-label="选择省级区域"
              @change="
                router.push(provincePath(Number(($event.target as HTMLSelectElement).value)))
              "
            >
              <option v-for="item in provinces" :key="item.code" :value="item.code">
                {{ item.name }}
              </option>
            </select>
          </label>
          <p v-if="provinceError" class="warning-note">{{ provinceError }}</p>
          <div class="region-intro">
            <span class="region-index">{{ String(province.code).slice(0, 2) }}</span>
            <div>
              <h3>{{ province.name }}</h3>
              <p>{{ isHenan ? '高速公路智慧能源示范区域' : '省域已选中 · 业务数据待接入' }}</p>
            </div>
          </div>
          <div class="region-facts">
            <div>
              <span>省域路网</span><strong>{{ isHenan ? '全省公开高速路网' : '尚未接入' }}</strong>
            </div>
            <div>
              <span>业务站点</span
              ><strong>{{
                isHenan ? `${summaryData?.siteCount ?? '—'}座授权台账` : '尚未接入'
              }}</strong>
            </div>
            <div><span>空间层级</span><strong>省域 → 地市 → 站点 → 设备</strong></div>
          </div>
          <button class="primary-button full-width" :disabled="!isHenan" @click="enterHenan">
            {{ isHenan ? '进入河南路网' : '该省业务空间待开放' }} <span>↗</span>
          </button>
          <RouterLink class="directory-shortcut" :to="{ name: 'service-template' }"
            >大型服务区模型 · 光伏 / 储能 / 充电 ↗</RouterLink
          >
          <p class="muted-note">
            点击任意省级区域进入放大的省域地图；河南省另有高速路网与数字孪生演示。
          </p>
          <div class="workflow">
            <span>01 地图定位</span><i>↓</i><span>02 搜索站点</span><i>↓</i
            ><span>03 三维设备与电力信息</span>
          </div></PanelCard
        >
      </template>
      <template #map>
        <CesiumMap
          ref="mapStage"
          scope="china"
          :expanded-view="!panelsVisible"
          external-controls
          v-model:theme="mapTheme"
          v-model:tilted="mapTilted"
          :province-code="province.code"
          @select-province="selectProvince"
          @open-henan="enterHenan"
          @status-change="mapStatus = $event"
        />
      </template>
      <template #right>
        <div class="right-stack">
          <PanelCard title="能源观察" eyebrow="ENERGY INSIGHTS"
            ><div class="sidebar-metrics" aria-label="数据库代表功率统计">
              <MetricCard
                label="并网点代表功率"
                :value="summaryData?.power.GRID.valueKw?.toFixed(1) ?? '—'"
                unit="kW"
                hint="分系统计量，不等于完整负荷"
              /><MetricCard
                label="光伏代表功率"
                :value="summaryData?.power.PV.valueKw?.toFixed(1) ?? '—'"
                unit="kW"
                hint="来源及覆盖见下方"
                accent="#a4b9ff"
              />
            </div>
            <DashboardSummaryPanel
              :data="summaryData"
              :loading="summaryLoading"
              :error="summaryError"
              v-model:source="summarySource"
              @refresh="reloadSummary"
            /> </PanelCard
          ><PanelCard title="建设进度" eyebrow="PROJECT STATUS"
            ><ol class="progress-list">
              <li class="done">
                <span>01</span>
                <div>Cesium地图工作台<small>全国与省域分层导航</small></div>
                <b>已搭建</b>
              </li>
              <li class="done">
                <span>02</span>
                <div>收费站 / 服务区场景<small>可进入模型并查看演示设备</small></div>
                <b>演示</b>
              </li>
              <li>
                <span>03</span>
                <div>真实电力数据接入<small>已接通MySQL查询；等待现场设备点表</small></div>
                <b>待现场对接</b>
              </li>
            </ol></PanelCard
          >
        </div>
      </template>
    </MapWorkspaceLayout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CesiumMap from '@/components/map/CesiumMap.vue'
import MapWorkspaceLayout from '@/layouts/MapWorkspaceLayout.vue'
import MapDisplayControls from '@/components/map/MapDisplayControls.vue'
import PanelCard from '@/components/common/PanelCard.vue'
import MetricCard from '@/components/common/MetricCard.vue'
import DashboardSummaryPanel from '@/components/dashboard/DashboardSummaryPanel.vue'
import { useDashboardSummary } from '@/composables/useDashboardSummary'
import { useSitesStore } from '@/stores/sites'
import { getProvinceRegions } from '@/services/mapService'
import { provincePath } from '@/utils/provinceCatalog'
import type { ProvinceSelection, ProvinceRegion } from '@/types/map'
const store = useSitesStore()
const {
  data: summaryData,
  source: summarySource,
  loading: summaryLoading,
  error: summaryError,
  reload: reloadSummary,
} = useDashboardSummary(
  computed(() => ({})),
  computed(() => true),
)
const router = useRouter()
const province = ref<ProvinceSelection>({ code: 410000, name: '河南省' })
const isHenan = computed(() => province.value.code === 410000)
const mapStage = ref<InstanceType<typeof CesiumMap>>()
const panelsVisible = ref(true)
const mapTheme = ref<'blue' | 'satellite'>('blue')
const mapTilted = ref(true)
const mapStatus = ref('地图初始化中…')
const provinces = ref<ProvinceRegion[]>([])
const provinceError = ref('')
onMounted(() => {
  void store.load()
  void getProvinceRegions()
    .then((data) => (provinces.value = data))
    .catch(() => (provinceError.value = '省域目录加载失败，请刷新重试'))
})
const enterHenan = () => router.push('/province/henan')
function selectProvince(selection: ProvinceSelection) {
  province.value = selection
  void router.push(provincePath(selection.code))
}
</script>
