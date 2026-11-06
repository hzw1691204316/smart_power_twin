<template>
  <div class="dashboard-view province-workspace">
    <MapWorkspaceLayout class="province-grid" v-model:panels-visible="panelsVisible">
      <template #left>
        <PanelCard title="站点检索" eyebrow="SITE DIRECTORY"
          ><template #action
            ><span class="count-chip"
              >{{ state.tab === 'models' ? filtered.length : filteredFacilities.length }} 条</span
            ></template
          >
          <div class="sidebar-metrics" aria-label="站点目录统计">
            <MetricCard
              label="三维样板（演示数据）"
              :value="scopeSites.length"
              unit="座"
              :hint="
                currentCity
                  ? `${currentCity.name}当前授权样板`
                  : `${scopeSites.filter((site) => site.type === 'TOLL').length}座收费站 · ${scopeSites.filter((site) => site.type === 'SERVICE').length}座服务区（授权范围）`
              "
            /><MetricCard
              label="公开服务区位置"
              :value="scopeFacilities.filter((item) => item.type === 'SERVICE').length"
              unit="处"
              hint="青绿色点 · 业务归属待核验"
            />
          </div>
          <MapDisplayControls
            scope="henan"
            :title="currentCity?.name ?? '河南全省路网'"
            :status="mapStatus"
            :cities="cities"
            :city-code="cityCode"
            v-model:theme="mapTheme"
            v-model:tilted="mapTilted"
            v-model:show-roads="showRoads"
            v-model:show-sites="showSites"
            @city="$event ? openCity($event) : router.push('/province/henan')"
            @reset="mapStage?.resetView()"
          />
          <SiteFilters
            v-model:query="query"
            v-model:type="type"
            v-model:highway="highway"
            :highways="highways"
          />
          <div class="directory-tabs" role="group" aria-label="站点目录来源">
            <button :class="{ active: state.tab === 'models' }" @click="state.tab = 'models'">
              三维样板 {{ filtered.length }}
            </button>
            <button :class="{ active: state.tab === 'public' }" @click="state.tab = 'public'">
              公开位置 {{ filteredFacilities.length }}
            </button>
          </div>
          <RouterLink
            class="directory-shortcut"
            :to="{
              name: 'service-template',
              query: { origin: cityCode ? String(cityCode) : 'henan' },
            }"
            >大型服务区模型 · 光伏 / 储能 / 充电 ↗</RouterLink
          >
          <button class="directory-shortcut" @click="openChaoge">
            ⌖ 鹤壁 · 朝歌服务区 / 收费站 ↗
          </button>
          <div v-if="state.tab === 'models' && store.error" class="empty-state">
            {{ store.error }}
          </div>
          <div v-else-if="state.tab === 'models' && store.loading" class="empty-state">
            正在加载站点…
          </div>
          <div v-else-if="state.tab === 'models'" class="site-list">
            <SiteCard
              v-for="site in filtered"
              :key="site.id"
              :site="site"
              :selected="selectedId === site.id"
              @select="selectSite"
            />
            <div v-if="!filtered.length" class="empty-state">
              <p>没有匹配的已绑定演示站点</p>
              <button class="text-button" @click="resetFilters">清空筛选条件</button>
            </div>
          </div>
          <div v-else-if="facilitiesLoading" class="empty-state">正在加载公开位置…</div>
          <PublicFacilityList
            v-else
            :facilities="filteredFacilities"
            :cities="cities"
            :selected-id="state.facilityId"
            :selected-site-id="selectedId"
            :limit="state.limit"
            @select="selectFacility"
            @more="state.limit += 40"
          />
          <button v-if="query || type || highway" class="text-button" @click="resetFilters">
            清空全部筛选
          </button>
          <div class="public-directory-note">
            <span class="live-dot" />地图中匹配 {{ filteredFacilities.length }} 处公开设施
          </div>
          <details class="directory-data-notes">
            <summary>数据与模型说明</summary>
            <p class="muted-note">
              三维样板采用通用模型与演示读数；公开位置仅用于找站。路线筛选同步作用于路网与站点，路线未知的公开位置不参与筛选。朝歌两站位置和模板并非现场测绘成果。
            </p>
          </details>
          <p v-if="highwayError" class="warning-note">{{ highwayError }}</p>
          <p v-if="facilityError" class="warning-note">{{ facilityError }}</p></PanelCard
        >
      </template>
      <template #map>
        <CesiumMap
          ref="mapStage"
          v-if="!cityCode || currentCity"
          :key="cityCode ?? 'henan'"
          scope="henan"
          :expanded-view="!panelsVisible"
          external-controls
          v-model:theme="mapTheme"
          v-model:tilted="mapTilted"
          :city="currentCity"
          :sites="filtered"
          :facilities="filteredFacilities"
          :selected-id="selectedId"
          :selected-facility-id="state.facilityId"
          :highway="highway"
          :show-roads="showRoads"
          :show-sites="showSites"
          @select-site="enterSiteFromMap"
          @select-facility="openFacilityScene"
          @network-ready="onNetworkReady"
          @status-change="mapStatus = $event"
          @select-city="openCity($event.code)"
        />
        <div v-else class="empty-state">
          {{
            cityError || (cities.length ? '未找到该地市，请选择河南省内地市' : '地市目录加载中…')
          }}
        </div>
      </template>
      <template #right>
        <div class="right-stack">
          <PanelCard
            :title="selected ? '站点速览' : selectedPublic ? '公开位置详情' : '选择一个站点'"
            eyebrow="SITE SNAPSHOT"
            ><div class="sidebar-metrics" aria-label="设施与路网统计">
              <MetricCard
                label="公开收费设施位置"
                :value="scopeFacilities.filter((item) => item.type === 'TOLL').length"
                unit="处"
                hint="橙色点 · 邻近收费亭已归并"
                accent="#ffbc67"
              /><MetricCard
                label="高速路网展示折线"
                :value="roadCount"
                unit="段"
                :hint="roadIsDemo ? '数据异常 · 当前为示意线路' : 'OSM省域提取 · 合并简化'"
                accent="#538fff"
              />
            </div>
            <MapLegend />
            <template v-if="selected"
              ><span
                class="status-badge"
                :class="selected.dataPending ? 'unknown' : selected.status"
                >{{ selected.dataPending ? '运行数据待接入' : statusLabel[selected.status] }}</span
              >
              <h3 class="snapshot-title">{{ selected.name }}</h3>
              <p class="snapshot-subtitle">{{ selected.highway }} · {{ selected.direction }}</p>
              <dl class="detail-list">
                <div>
                  <dt>站点类型</dt>
                  <dd>{{ typeLabel[selected.type] }}</dd>
                </div>
                <div>
                  <dt>场景规模</dt>
                  <dd>{{ scaleLabel[selected.scale] }}</dd>
                </div>
                <div>
                  <dt>示例负荷</dt>
                  <dd>
                    {{
                      selected.dataPending
                        ? '待接入'
                        : selected.status === 'offline'
                          ? '暂无数据'
                          : `${selected.powerKw} kW`
                    }}
                  </dd>
                </div>
                <div>
                  <dt>示例日用电</dt>
                  <dd>
                    {{
                      selected.dataPending
                        ? '待接入'
                        : selected.status === 'offline'
                          ? '暂无数据'
                          : `${selected.dailyEnergyKwh} kWh`
                    }}
                  </dd>
                </div>
              </dl>
              <button class="primary-button full-width" @click="openScene(selected.id)">
                进入数字孪生 <span>↗</span>
              </button>
              <p v-if="selected.locationNote" class="muted-note">
                {{ selected.locationNote }}
              </p></template
            >
            <template v-else-if="selectedPublic">
              <span class="status-badge">公开位置 · 未接入</span>
              <h3 class="snapshot-title">{{ selectedPublic.name }}</h3>
              <dl class="detail-list">
                <div>
                  <dt>类型</dt>
                  <dd>{{ typeLabel[selectedPublic.type] }}</dd>
                </div>
                <div>
                  <dt>来源标识</dt>
                  <dd>{{ selectedPublic.id }}</dd>
                </div>
                <div>
                  <dt>参考经度</dt>
                  <dd>{{ selectedPublic.longitude.toFixed(6) }}</dd>
                </div>
                <div>
                  <dt>参考纬度</dt>
                  <dd>{{ selectedPublic.latitude.toFixed(6) }}</dd>
                </div>
                <div>
                  <dt>电力 / 模型</dt>
                  <dd>通用模型 · 演示数据</dd>
                </div>
              </dl>
              <p class="muted-note">
                OpenStreetMap公开参考点，坐标为WGS84，名称、入口及业务归属待核验。可查看同类型通用模型，本站实际布局及电力数据尚未接入。
              </p>
              <button class="primary-button full-width" @click="openFacilityScene(selectedPublic)">
                查看{{ typeLabel[selectedPublic.type] }}三维模板 ↗
              </button>
            </template>
            <div v-else class="selection-placeholder">
              <span>⌖</span>
              <p>地图点直接进入三维</p>
              <small>左侧列表可先查看位置与能源摘要</small>
            </div></PanelCard
          ><PanelCard title="业务能源汇总" eyebrow="ENERGY PROFILE"
            ><DashboardSummaryPanel
              :data="summaryData"
              :loading="summaryLoading"
              :error="summaryError"
              v-model:source="summarySource"
              @refresh="reloadSummary"
          /></PanelCard>
        </div>
      </template>
    </MapWorkspaceLayout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CesiumMap from '@/components/map/CesiumMap.vue'
import MapWorkspaceLayout from '@/layouts/MapWorkspaceLayout.vue'
import MapDisplayControls from '@/components/map/MapDisplayControls.vue'
import MapLegend from '@/components/map/MapLegend.vue'
import MetricCard from '@/components/common/MetricCard.vue'
import PanelCard from '@/components/common/PanelCard.vue'
import SiteCard from '@/components/sites/SiteCard.vue'
import SiteFilters from '@/components/sites/SiteFilters.vue'
import PublicFacilityList from '@/components/sites/PublicFacilityList.vue'
import { useDirectoryStore } from '@/stores/directory'
import { matchesHighway, matchesQuery } from '@/utils/directory'
import { siteSceneTarget, facilitySceneTarget } from '@/utils/sceneNavigation'
import DashboardSummaryPanel from '@/components/dashboard/DashboardSummaryPanel.vue'
import { useDashboardSummary } from '@/composables/useDashboardSummary'
import { scaleLabel, statusLabel, typeLabel } from '@/data/demo'
import { useSitesStore } from '@/stores/sites'
import { getPublicFacilities, getCityRegions, getHighwayOptions } from '@/services/mapService'
import type { PublicFacility, CityRegion } from '@/types/map'
const store = useSitesStore()
const router = useRouter()
const route = useRoute()
const directory = useDirectoryStore()
const state = computed(() => directory.scope(String(cityCode.value ?? 'henan')))
const cities = ref<CityRegion[]>([])
const cityError = ref('')
const cityCode = computed(() => (route.params.cityCode ? Number(route.params.cityCode) : undefined))
const currentCity = computed(() => cities.value.find((item) => item.code === cityCode.value))
const {
  data: summaryData,
  source: summarySource,
  loading: summaryLoading,
  error: summaryError,
  reload: reloadSummary,
} = useDashboardSummary(
  computed(() => ({ provinceCode: '410000', cityName: currentCity.value?.name })),
  computed(() => !cityCode.value || !!currentCity.value),
)
const scopeSites = computed(() =>
  store.sites.filter(
    (site) =>
      (site.provinceCode ?? '410000') === '410000' &&
      (!currentCity.value ||
        site.cityCode === currentCity.value.code ||
        site.city === currentCity.value.name.replace(/市$/, '')),
  ),
)
const scopeFacilities = computed(() =>
  facilities.value.filter(
    (item) => item.cityCode != null && (!cityCode.value || item.cityCode === cityCode.value),
  ),
)
function openCity(code: number) {
  void router.push(`/province/henan/cities/${code}`)
}
const query = computed({
  get: () => state.value.query,
  set: (value) => (state.value.query = value),
})
const type = computed({ get: () => state.value.type, set: (value) => (state.value.type = value) })
const highway = computed({
  get: () => state.value.highway,
  set: (value) => (state.value.highway = value),
})
const selectedId = computed({
  get: () => state.value.selectedId,
  set: (value) => (state.value.selectedId = value),
})
const highways = ref<string[]>([])
const highwayError = ref('')
const showRoads = ref(true)
const showSites = ref(true)
const facilities = ref<PublicFacility[]>([])
const facilityError = ref('')
const roadCount = ref(0)
const roadIsDemo = ref(false)
const mapStage = ref<InstanceType<typeof CesiumMap>>()
const panelsVisible = ref(true)
const mapTheme = ref<'blue' | 'satellite'>('blue')
const mapTilted = ref(true)
const mapStatus = ref('地图初始化中…')
const facilitiesLoading = ref(true)
const selectedPublic = computed(() =>
  filteredFacilities.value.find((item) => item.id === state.value.facilityId),
)
function selectSite(id: string) {
  selectedId.value = id
  state.value.facilityId = ''
  showSites.value = true
}
function selectFacility(facility: PublicFacility) {
  if (facility.boundSiteId) {
    selectSite(facility.boundSiteId)
  } else {
    selectedId.value = ''
    state.value.facilityId = facility.id
    showSites.value = true
  }
}
function openScene(id: string) {
  void router.push(siteSceneTarget(id, cityCode.value))
}
function enterSiteFromMap(id: string) {
  selectSite(id)
  openScene(id)
}
function openFacilityScene(facility: PublicFacility) {
  selectFacility(facility)
  void router.push(facilitySceneTarget(facility, cityCode.value))
}
function openChaoge() {
  const target = directory.scope('410600')
  Object.assign(target, {
    query: '朝歌',
    type: '',
    highway: '',
    selectedId: 'henan-service-01',
    facilityId: '',
    tab: 'models',
  })
  openCity(410600)
}
const filteredFacilities = computed(() =>
  scopeFacilities.value.filter(
    (item) =>
      (!type.value || item.type === type.value) &&
      matchesHighway(item.ref, highway.value) &&
      matchesQuery(
        query.value,
        item.name,
        item.ref,
        item.id,
        cities.value.find((city) => city.code === item.cityCode)?.name,
      ),
  ),
)
function onNetworkReady(count: number, isDemo: boolean) {
  roadCount.value = count
  roadIsDemo.value = isDemo
}
const filtered = computed(() =>
  scopeSites.value.filter(
    (site) =>
      (!type.value || site.type === type.value) &&
      matchesHighway(site.highway, highway.value) &&
      matchesQuery(
        query.value,
        site.name,
        site.city,
        `${site.city}市`,
        site.code,
        site.highway,
        site.publicFacilityId,
      ),
  ),
)
const selected = computed(() => filtered.value.find((site) => site.id === selectedId.value))
watch([query, type, highway], () => {
  state.value.limit = 40
  if (!filtered.value.some((site) => site.id === selectedId.value)) selectedId.value = ''
  if (!filteredFacilities.value.some((item) => item.id === state.value.facilityId))
    state.value.facilityId = ''
})
onMounted(() => {
  void store.load()
  void getCityRegions()
    .then((data) => {
      cities.value = data
    })
    .catch(() => {
      cityError.value = '地市目录加载失败，请刷新重试'
    })
  void getPublicFacilities()
    .then((data) => {
      facilities.value = data
    })
    .catch(() => {
      facilityError.value = '公开设施数据暂未加载'
    })
    .finally(() => (facilitiesLoading.value = false))
})
function resetFilters() {
  query.value = ''
  type.value = ''
  highway.value = ''
}
watch(
  cityCode,
  async (code, _old, onCleanup) => {
    let stale = false
    onCleanup(() => (stale = true))
    roadCount.value = 0
    highways.value = []
    highwayError.value = ''
    try {
      const options = await getHighwayOptions(code)
      if (!stale) highways.value = options
    } catch {
      if (!stale) highwayError.value = '路线目录暂不可用，请刷新重试'
    }
  },
  { immediate: true },
)
</script>
