<template>
  <TwinDashboardLayout
    v-if="site"
    title="高速智慧电力数字孪生"
    :subtitle="`${site.publicModel ? '能源设施方案 · ' : isPublicPreview ? '通用模板预览 · ' : ''}${site.city} · ${site.name.replace(' · 演示', '')} · ${typeLabel[site.type]}`"
    :description="
      site.publicModel
        ? '双侧服务区能源设施方案 · 电力采集尚未接入'
        : !isPublicPreview
          ? 'MySQL授权汇总与设备监测 · 现场与模拟来源分开'
          : undefined
    "
    :return-to="returnPath"
    :active-tab="activeTab"
    @update:active-tab="selectTab"
  >
    <template #scene
      ><TwinScene
        v-if="isPublicPreview || publishedScene"
        ref="stage"
        :key="`${publishedScene?.id ?? site.id}:${isPublicPreview ? site.modelUrl : publishedScene?.modelUrl}`"
        :model-url="isPublicPreview ? site.modelUrl : (publishedScene?.modelUrl ?? '')"
        :devices="interactiveDevices"
        :selected-id="selectedDeviceId"
        dashboard
        @select="selectDevice"
      />
      <div v-else class="scene-loading">
        <strong>{{
          sceneLoading ? '正在读取已发布场景…' : sceneError || '本站尚无已发布场景'
        }}</strong
        ><button class="hud-locate-button" @click="reloadScene">重新读取场景</button>
      </div></template
    >
    <template #summary
      ><div class="hud-summary-item">
        <span>{{
          site.publicModel ? '模型能源对象' : isPublicPreview ? '示例站点负荷' : '并网点代表功率'
        }}</span
        ><strong
          >{{
            site.publicModel
              ? interactiveDevices.length
              : !isPublicPreview
                ? (summaryData?.power.GRID.valueKw?.toFixed(1) ?? '—')
                : site.status === 'offline'
                  ? '—'
                  : site.powerKw
          }}<small>{{ site.publicModel ? '个' : 'kW' }}</small></strong
        >
      </div>
      <div class="hud-summary-item">
        <span>{{
          site.publicModel ? '光伏组件' : isPublicPreview ? '示例光伏出力' : '光伏代表功率'
        }}</span
        ><strong
          >{{
            site.publicModel
              ? site.publicModel.pvPanelCount
              : !isPublicPreview
                ? (summaryData?.power.PV.valueKw?.toFixed(1) ?? '—')
                : site.status === 'offline'
                  ? '—'
                  : site.pvKw
          }}<small>{{ site.publicModel ? '片' : 'kW' }}</small></strong
        >
      </div>
      <div class="hud-summary-item">
        <span>{{
          site.publicModel ? '电力数据' : isPublicPreview ? '可用演示设备' : '所选来源设备'
        }}</span
        ><strong
          >{{
            site.publicModel
              ? '待接入'
              : !isPublicPreview
                ? (summaryData?.deviceCount ?? '—')
                : onlineCount
          }}<small v-if="isPublicPreview && !site.publicModel"
            >/ {{ site.devices.length }}</small
          ></strong
        >
      </div></template
    >
    <template #left>
      <HudPanel
        v-if="isPublicPreview && site.type === 'SERVICE'"
        title="服务区模型"
        caption="MODEL CATALOG"
      >
        <template v-if="route.name === 'service-template'"
          ><strong>大型服务区 · 双侧能源设施</strong>
          <p class="hud-data-caption">
            通用模板，可用于大型服务区场景。选择设备可定位查看。
          </p></template
        >
        <label v-else class="service-model-picker"
          >预览规模<select
            :value="site.scale"
            aria-label="服务区模型规模"
            @change="selectModelScale"
          >
            <option value="M">中型服务区</option>
            <option value="L">大型服务区 · 双侧能源设施</option>
          </select></label
        >
      </HudPanel>
      <HudPanel v-if="!isPublicPreview" title="本站业务汇总" caption="DATABASE SUMMARY"
        ><DashboardSummaryPanel
          :data="summaryData"
          :loading="summaryLoading"
          :error="summaryError"
          v-model:source="summarySource"
          @refresh="reloadSummary"
      /></HudPanel>
      <HudPanel v-else-if="site.publicModel" title="能源设施方案" caption="MODEL FACILITIES">
        <dl class="detail-list">
          <div v-for="item in modelFacilityCounts" :key="item.name">
            <dt>{{ item.name }}</dt>
            <dd>{{ item.count }} 个</dd>
          </div>
        </dl>
        <p class="hud-data-caption">设备状态未接入，可点击模型或下方目录定位。</p>
      </HudPanel>
      <HudPanel v-else title="模板设备状态（示意）" caption="DEVICE STATUS"
        ><DeviceStatusRing :devices="site.devices"
      /></HudPanel>
      <HudPanel
        v-if="isPublicPreview"
        :title="site.publicModel ? '模型与数据说明' : '站点电力概览（示意）'"
        caption="POWER OVERVIEW"
        :accent="activeTab === 'energy'"
        ><p v-if="site.publicModel" class="hud-data-caption">{{ site.publicModel.description }}</p>
        <PowerOverview v-else :site="site"
      /></HudPanel>
      <HudPanel
        :title="explorerTitle"
        caption="ASSET EXPLORER"
        :accent="activeTab === 'devices' || activeTab === 'power'"
        ><SceneVersionManager
          v-if="publishedScene"
          :key="publishedScene.id"
          :current="publishedScene"
          @refresh="reloadScene"
        /><DeviceExplorer
          :devices="visibleDevices"
          :selected-id="selectedDeviceId"
          @select="selectDevice"
        />
        <p class="hud-data-caption">选择设备后，可在右侧查看指标并定位场景</p></HudPanel
      >
    </template>
    <template #right>
      <HudPanel
        :title="
          site.publicModel
            ? '能源对象 · 待接入监测'
            : activeTab === 'energy'
              ? isPublicPreview
                ? '能耗指标（示意）'
                : '日计量与历史说明'
              : isPublicPreview
                ? '设备电力信息（示意）'
                : '设备监测 · MySQL'
        "
        caption="TELEMETRY"
        accent
        ><div v-if="site.publicModel" class="device-details">
          <template v-if="selectedDevice"
            ><h3 class="snapshot-title">{{ selectedDevice.name }}</h3>
            <p class="snapshot-subtitle">{{ selectedDevice.category }}</p>
            <dl class="detail-list">
              <div>
                <dt>采集状态</dt>
                <dd>未接入</dd>
              </div>
            </dl>
            <p class="hud-data-caption">{{ selectedDevice.objectKey }}</p>
            <p class="hud-data-caption">
              此对象来自能源设施方案，尚无实测读数或设备运行状态。
            </p></template
          >
          <p v-else class="hud-data-caption">请从模型或能源设备目录选择对象。</p>
        </div>
        <p v-else-if="activeTab === 'energy' && !isPublicPreview" class="hud-data-caption">
          本站日计量边界尚未配置，请在设备监测中查看各测点历史。各系统当前代表功率及覆盖见左侧数据库汇总。
        </p>
        <PowerOverview v-else-if="activeTab === 'energy'" :site="site" /><DeviceMonitoring
          v-else-if="!isPublicPreview && selectedObject?.device"
          :device-id="selectedObject.device.id"
          :device-name="selectedObject.device.name"
          :is-demo="selectedObject.device.isDemo"
          :point-ids="boundPointIds"
        /><DeviceDetails v-else :device="selectedPublicDevice" /><button
          v-if="selectedDevice && activeTab !== 'energy'"
          class="hud-locate-button"
          @click="focusDevice()"
        >
          ⌖ 定位当前设备
        </button></HudPanel
      >
      <HudPanel
        v-if="!site.publicModel && isPublicPreview"
        :title="
          activeTab === 'energy'
            ? '日内能耗趋势'
            : activeTab === 'power'
              ? '光伏出力趋势'
              : '站点功率趋势'
        "
        caption="ENERGY TREND"
        ><EnergyTrend :title="activeTab === 'energy' ? '能耗形态示意' : '日内功率形态示意'" />
        <div class="hud-trend-legend">
          <span><i />{{ activeTab === 'power' ? '光伏' : '功率' }}趋势示意</span
          ><small>00:00 — 24:00</small>
        </div></HudPanel
      >
      <HudPanel
        :title="
          site.publicModel
            ? '告警 · 待接入'
            : isPublicPreview
              ? '告警演示（通用模板）'
              : '站点告警 · MySQL'
        "
        caption="EVENT MONITORING"
        :accent="activeTab === 'alarms'"
        ><p v-if="site.publicModel" class="hud-data-caption">
          未接入本站采集与告警数据，暂无可判断的设备状态。
        </p>
        <AlarmPanel v-else-if="!isPublicPreview" :site-code="sceneSiteCode" @locate="locateAlarm" />
        <AlarmSummary v-else :site="site" @locate="focusDevice"
      /></HudPanel>
    </template>
    <template #categories
      ><button
        v-for="item in categories"
        :key="item.id"
        :class="{ active: category === item.id }"
        :aria-label="`筛选${item.label}设备`"
        @click="selectCategory(item.id)"
      >
        <span>{{ item.icon }}</span
        ><b>{{ item.label }}</b>
      </button></template
    >
    <template #toolbar
      ><button @click="stage?.resetView()"><span>↺</span>场景复位</button
      ><button @click="stage?.topView()"><span>⌗</span>俯视场景</button
      ><button @click="focusDevice()"><span>⌖</span>设备定位</button
      ><button
        v-if="relatedSite"
        @click="
          router.push({
            name: 'site',
            params: { siteId: relatedSite.id },
            query: { ...route.query },
          })
        "
      >
        <span>⇄</span>切换{{ relatedSite.type === 'TOLL' ? '收费站' : '服务区' }}
      </button></template
    >
  </TwinDashboardLayout>
  <div v-else class="route-empty">
    <h1>
      {{
        facilityLoading || store.loading
          ? '正在加载站点…'
          : facilityError || store.error || '该站点不存在或当前账号未获授权'
      }}
    </h1>
    <RouterLink class="primary-button" :to="returnPath">返回路网</RouterLink>
  </div>
  <p v-if="feedback" class="hud-toast">{{ feedback }}</p>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TwinDashboardLayout from '@/layouts/TwinDashboardLayout.vue'
import HudPanel from '@/components/twin/HudPanel.vue'
import DeviceStatusRing from '@/components/twin/DeviceStatusRing.vue'
import PowerOverview from '@/components/twin/PowerOverview.vue'
import DeviceExplorer from '@/components/twin/DeviceExplorer.vue'
import AlarmSummary from '@/components/twin/AlarmSummary.vue'
import AlarmPanel from '@/components/twin/AlarmPanel.vue'
import EnergyTrend from '@/components/dashboard/EnergyTrend.vue'
import DeviceDetails from '@/components/twin/DeviceDetails.vue'
import DeviceMonitoring from '@/components/twin/DeviceMonitoring.vue'
import SceneVersionManager from '@/components/twin/SceneVersionManager.vue'
import { usePublishedScene } from '@/composables/usePublishedScene'
import { sceneDevices } from '@/utils/twinPresentation'
import TwinScene from '@/components/twin/TwinScene.vue'
import { demoSites, typeLabel } from '@/data/demo'
import { useSitesStore } from '@/stores/sites'
import { getPublicFacilities, getCityRegions } from '@/services/mapService'
import { createFacilityScene } from '@/services/facilityScene'
import { mapReturnPath } from '@/utils/sceneNavigation'
import type { PublicFacility, CityRegion } from '@/types/map'
import type { AlarmEvent } from '@/types/alarms'
import type { ScaleLevel } from '@/types/domain'
import DashboardSummaryPanel from '@/components/dashboard/DashboardSummaryPanel.vue'
import { useDashboardSummary } from '@/composables/useDashboardSummary'

const route = useRoute()
const router = useRouter()
const store = useSitesStore()
const publicFacilities = ref<PublicFacility[]>([])
const cityRegions = ref<CityRegion[]>([])
const facilityLoading = ref(false)
const facilityError = ref('')
const isPublicPreview = computed(
  () =>
    route.name === 'service-template' ||
    (route.name === 'facility' &&
      !publicFacilities.value.find((item) => item.id === String(route.params.facilityId))
        ?.boundSiteId),
)
const stage = ref<InstanceType<typeof TwinScene>>()
const selectedDeviceId = ref('')
const activeTab = ref('overview')
const category = ref('all')
const feedback = ref('')
const categories = [
  { id: 'all', label: '全部', icon: '◈' },
  { id: '光伏系统', label: '光伏', icon: '☀' },
  { id: '储能系统', label: '储能', icon: '▤' },
  { id: '配电系统', label: '配电', icon: 'ϟ' },
  { id: '充电系统', label: '充电', icon: '↯' },
]
const returnPath = computed(() =>
  route.name === 'service-template' && !route.query.origin
    ? '/overview'
    : mapReturnPath(route.query, site.value?.cityCode),
)
const site = computed(() => {
  if (route.name === 'service-template') {
    const template = demoSites.find((item) => item.type === 'SERVICE')!
    // 模型库是独立预览，无地图位置、无私有站点身份。
    return createFacilityScene(
      {
        id: 'template-service-large',
        name: '大型服务区',
        type: 'SERVICE',
        longitude: 0,
        latitude: 0,
      },
      template,
      '通用模板',
      'L',
    )
  }
  if (route.name !== 'facility')
    return store.sites.find((item) => item.id === String(route.params.siteId))
  const facility = publicFacilities.value.find(
    (item) => item.id === String(route.params.facilityId),
  )
  if (!facility) return undefined
  if (facility.boundSiteId) return store.sites.find((item) => item.id === facility.boundSiteId)
  const cityName =
    cityRegions.value.find((city) => city.code === facility.cityCode)?.name ?? '河南省'
  // 仅未绑定台账的公开位置可用独立通用模板；已绑定站点仍须先从授权store查找。
  // 这里的模板与数值是公开演示素材，不从未授权站点接口读取任何业务信息。
  const template = demoSites.find((item) => item.type === facility.type)
  return template
    ? createFacilityScene(
        facility,
        template,
        cityName,
        route.query.modelScale === 'L' ? 'L' : route.query.modelScale === 'M' ? 'M' : undefined,
      )
    : undefined
})
/** 公开预览切换规模写入URL，刷新后保持选择；不得改变私有场景或设备权限。 */
function selectModelScale(event: Event) {
  const scale = (event.target as HTMLSelectElement).value as ScaleLevel
  void router.replace({ query: { ...route.query, modelScale: scale } })
}
const relatedSite = computed(() =>
  site.value?.complexCode
    ? store.sites.find(
        (item) => item.complexCode === site.value?.complexCode && item.id !== site.value?.id,
      )
    : undefined,
)
const sceneSiteCode = computed(() => site.value?.code ?? '')
const {
  scene: publishedScene,
  loading: sceneLoading,
  error: sceneError,
  reload: reloadScene,
} = usePublishedScene(sceneSiteCode, isPublicPreview)
const {
  data: summaryData,
  source: summarySource,
  loading: summaryLoading,
  error: summaryError,
  reload: reloadSummary,
} = useDashboardSummary(
  computed(() => ({ siteCode: sceneSiteCode.value })),
  computed(() => !isPublicPreview.value && !!sceneSiteCode.value),
)
const interactiveDevices = computed(() =>
  isPublicPreview.value
    ? (site.value?.publicModel?.devices ?? site.value?.devices ?? [])
    : publishedScene.value
      ? sceneDevices(publishedScene.value)
      : [],
)
/** 指定方案的目录数量来自模型清单，不代表在线设备数或MySQL台账数量。 */
const modelFacilityCounts = computed(() =>
  [...new Set(interactiveDevices.value.map((d) => d.category))].map((name) => ({
    name,
    count: interactiveDevices.value.filter((d) => d.category === name).length,
  })),
)
const selectedObject = computed(() =>
  publishedScene.value?.objects.find((o) => o.id === selectedDeviceId.value),
)
const boundPointIds = computed(() => [
  ...new Set(
    publishedScene.value?.bindings
      .filter((b) => b.objectId === selectedObject.value?.id)
      .map((b) => b.pointId) ?? [],
  ),
])
const selectedPublicDevice = computed(() =>
  isPublicPreview.value
    ? site.value?.devices.find((d) => d.id === selectedDeviceId.value)
    : undefined,
)
const selectedDevice = computed(() =>
  interactiveDevices.value.find((device) => device.id === selectedDeviceId.value),
)
const visibleDevices = computed(() =>
  interactiveDevices.value.filter((device) => {
    if (activeTab.value === 'alarms' && isPublicPreview.value && !site.value?.publicModel)
      return device.status !== 'normal'
    if (category.value === '新能源') return ['光伏系统', '储能系统'].includes(device.category)
    return category.value === 'all' || device.category === category.value
  }),
)
const explorerTitle = computed(() =>
  activeTab.value === 'alarms'
    ? '事件关联设备'
    : activeTab.value === 'power'
      ? '光伏 / 储能设备'
      : '能源设备目录',
)
const onlineCount = computed(
  () => site.value?.devices.filter((device) => device.status !== 'offline').length ?? 0,
)

watch(
  site,
  (value) => {
    selectedDeviceId.value = value?.devices[0]?.id ?? ''
    activeTab.value = 'overview'
    category.value = 'all'
    feedback.value = ''
  },
  { immediate: true },
)
watch(
  interactiveDevices,
  (devices) => {
    if (!devices.some((d) => d.id === selectedDeviceId.value))
      selectedDeviceId.value = devices[0]?.id ?? ''
  },
  { immediate: true },
)
onMounted(() => {
  void store.load()
})
watch(
  () => route.name,
  async (name) => {
    if (name !== 'facility' || publicFacilities.value.length) return
    facilityLoading.value = true
    facilityError.value = ''
    try {
      publicFacilities.value = await getPublicFacilities()
    } catch {
      facilityError.value = '公开设施目录加载失败，请刷新重试'
    } finally {
      facilityLoading.value = false
    }
    try {
      cityRegions.value = await getCityRegions()
    } catch {
      /* 名称缺失时保留河南省与参考坐标。 */
    }
  },
  { immediate: true },
)

function selectDevice(id: string) {
  selectedDeviceId.value = id
  if (!visibleDevices.value.some((device) => device.id === id)) category.value = 'all'
  if (
    activeTab.value === 'energy' ||
    (activeTab.value === 'alarms' &&
      site.value?.devices.find((device) => device.id === id)?.status === 'normal')
  )
    activeTab.value = 'devices'
  feedback.value = ''
}
function selectCategory(id: string) {
  activeTab.value = 'devices'
  category.value = id
  selectedDeviceId.value = visibleDevices.value[0]?.id ?? ''
  feedback.value = ''
}
function selectTab(tab: string) {
  activeTab.value = tab
  category.value = tab === 'power' ? '新能源' : 'all'
  selectedDeviceId.value = visibleDevices.value[0]?.id ?? ''
  feedback.value = ''
}
async function focusDevice(id?: string) {
  // 公开模板保留演示定位；私有告警经locateAlarm按真实设备/绑定查对象，不猜固定编码。
  if (id && !interactiveDevices.value.some((d) => d.id === id)) {
    const key = site.value?.devices.find((d) => d.id === id)?.objectKey
    id = interactiveDevices.value.find((d) => d.objectKey === key)?.id
    if (!id) {
      feedback.value = '该演示设备未在当前发布场景关联'
      return
    }
  }
  if (id) selectDevice(id)
  // 等待父级selectedId传入模型组件，再读取对象锚点。
  await nextTick()
  feedback.value = stage.value?.focusSelected()
    ? ''
    : '模型尚未就绪或该设备暂时没有定位锚点，请稍后重试'
}

/** 用事件的真实设备ID匹配当前发布对象；同设备多对象时优先选择绑定该测点的对象。 */
async function locateAlarm(event: AlarmEvent) {
  const scene = publishedScene.value
  if (!scene || scene.siteId !== event.siteId) {
    feedback.value = '本站已发布场景尚未加载，无法定位此事件'
    return
  }
  const candidates = scene.objects.filter((o) => o.deviceId === event.deviceId)
  const object =
    candidates.find((o) =>
      scene.bindings.some((b) => b.objectId === o.id && b.pointId === event.pointId),
    ) ?? candidates[0]
  if (!object) {
    feedback.value = '该事件关联设备尚未绑定到当前发布场景'
    return
  }
  activeTab.value = 'devices'
  category.value = 'all'
  await focusDevice(object.id)
}
</script>

<style scoped>
.service-model-picker {
  display: grid;
  gap: 8px;
  font-size: 14px;
}
.service-model-picker select {
  width: 100%;
  min-width: 0;
  padding: 10px;
  color: #ddf5ff;
  background: #123b5d;
  border: 1px solid #4386a9;
  border-radius: 10px;
  font: inherit;
}
</style>
