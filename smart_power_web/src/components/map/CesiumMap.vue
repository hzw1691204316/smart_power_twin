<template>
  <div class="map-wrap tech-map" :class="{ 'satellite-map': theme === 'satellite' }">
    <div ref="host" class="cesium-host" />
    <div class="map-tech-vignette" />
    <div class="map-corner top-left" />
    <div class="map-corner top-right" />
    <div class="map-corner bottom-left" />
    <div class="map-corner bottom-right" />
    <div v-if="fatal" class="map-fatal">
      <strong>地图暂时不可用</strong>
      <p>{{ fatal }}</p>
      <small>检查浏览器硬件加速，列表与导航仍可使用。</small>
    </div>
    <template v-else>
      <div v-if="!externalControls" class="map-source">
        <span class="status-dot" :class="ready ? 'normal' : 'offline'" />{{ status }}
      </div>
      <div v-if="!externalControls" class="map-theme-switch" aria-label="地图底图风格">
        <button :class="{ active: theme === 'blue' }" @click="theme = 'blue'">科技蓝图</button
        ><button :class="{ active: theme === 'satellite' }" @click="theme = 'satellite'">
          卫星影像
        </button>
      </div>
      <div v-if="!externalControls" class="map-region-hud">
        <span>REGIONAL ENERGY DIGITAL TWIN</span><strong>{{ scopeLabel }}</strong
        ><small>{{
          scope === 'china'
            ? '点击省份选中 · 河南已开放演示'
            : roadsReady
              ? roadIsDemo
                ? '路网示意 · 完整高速数据待接入'
                : `${props.highway ? props.highway + ' · ' : ''}${roadCount.toLocaleString()} 段${props.city ? '市域' : '省域'}高速折线 · ${props.city ? '已按市界裁剪' : '点击地市查看市域路网'}`
              : '省域高速路网加载中…'
        }}</small>
      </div>
      <div v-if="hoverName" class="map-hover-name">⌖ {{ hoverName }}</div>
      <div
        v-if="!externalControls && scope === 'china' && provinceCode === 410000"
        class="map-region-entry"
      >
        <span class="live-dot" />河南省 · 已接入演示站点<button @click="emit('openHenan')">
          进入省域 ↗
        </button>
      </div>
      <div v-if="selectedFacility" class="public-facility-popup">
        <button aria-label="关闭设施信息" @click="selectedFacility = undefined">×</button
        ><span class="eyebrow">PUBLIC FACILITY / OSM</span
        ><strong>{{ selectedFacility.name }}</strong>
        <p>{{ selectedFacility.type === 'SERVICE' ? '服务区' : '收费设施' }} · 公开位置</p>
        <small>未绑定业务台账和三维设备。名称与邻近归并结果需核验。</small>
      </div>
      <div v-if="scope === 'china'" class="south-sea-inset">
        <img src="/maps/south-china-sea.svg" alt="南海诸岛位置示意" /><span>南海诸岛</span>
      </div>
      <div v-if="warning" class="map-warning">{{ warning }}</div>
      <button
        v-if="!externalControls"
        class="map-reset"
        aria-label="恢复全省或全国视野"
        @click="fitScope()"
      >
        ⌖ <span>全域视野</span>
      </button>
      <button
        v-if="!externalControls"
        class="map-perspective"
        :aria-pressed="tilted"
        @click="tilted = !tilted"
      >
        {{ tilted ? '◈ 立体视角' : '▱ 俯视视角' }}
      </button>
      <div v-if="!externalControls" class="map-coordinate">
        {{ scope === 'china' ? 'CHINA' : 'HENAN' }} <span>/</span> SPATIAL ENERGY ATLAS
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Cartesian2,
  Cartesian3,
  Color,
  Credit,
  CustomDataSource,
  Entity,
  DirectionalLight,
  GridImageryProvider,
  HorizontalOrigin,
  ImageryLayer,
  Ion,
  LabelStyle,
  NearFarScalar,
  SceneMode,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  TileMapServiceImageryProvider,
  Viewer,
  buildModuleUrl,
  createWorldImageryAsync,
} from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { mapConfig } from '@/config/map'
import { getMapElevation } from '@/config/mapPresentation'
import { mapFont } from '@/config/typography'
import { flyToRegion } from './cameraView'
import { configureMapWheelZoom } from './mapWheelZoom'
import { createAdministrativeLayers, type AdministrativeLayers } from './administrativeLayer'
import { createRoadLayer } from './roadLayer'
import type { ProvinceSelection, PublicFacility, CityRegion, ProvinceRegion } from '@/types/map'
import type { Site } from '@/types/domain'

const props = withDefaults(
  defineProps<{
    scope: 'china' | 'henan' | 'province'
    province?: ProvinceRegion
    sites?: Site[]
    facilities?: PublicFacility[]
    selectedId?: string
    selectedFacilityId?: string
    highway?: string
    provinceCode?: number
    city?: CityRegion
    showRoads?: boolean
    showSites?: boolean
    externalControls?: boolean
    expandedView?: boolean
  }>(),
  { sites: () => [], facilities: () => [], provinceCode: 410000, showRoads: true, showSites: true },
)
const emit = defineEmits<{
  selectSite: [id: string]
  selectFacility: [facility: PublicFacility]
  selectProvince: [province: ProvinceSelection]
  selectCity: [city: ProvinceSelection]
  openHenan: []
  networkReady: [count: number, isDemo: boolean]
  statusChange: [status: string]
}>()
const host = ref<HTMLDivElement>()
const status = ref('科技底图初始化中…')
const warning = ref('')
const fatal = ref('')
const theme = defineModel<'blue' | 'satellite'>('theme', { default: 'blue' })
const tilted = defineModel<boolean>('tilted', { default: true })
const elevation = getMapElevation(
  props.scope,
  !!props.city,
  props.province &&
    Math.max(
      props.province.bounds.east - props.province.bounds.west,
      props.province.bounds.north - props.province.bounds.south,
    ),
)
const ready = ref(false)
const hoverName = ref('')
const roadCount = ref(0)
const roadsReady = ref(false)
const roadIsDemo = ref(true)
const selectedFacility = ref<PublicFacility>()
const scopeLabel = computed(() =>
  props.scope === 'china'
    ? '中国 · 省域选择'
    : props.province
      ? `${props.province.name} · 省域视图`
      : props.city
        ? `${props.city.name} · 高速路网`
        : '河南 · 全省高速路网',
)
let viewer: Viewer | undefined
let handler: ScreenSpaceEventHandler | undefined
let administrative: AdministrativeLayers | undefined
let roadSource: CustomDataSource | undefined
let filterRoads: ((highway: string) => number) | undefined
let localLayer: ImageryLayer | undefined
let onlineLayer: ImageryLayer | undefined
let gridLayer: ImageryLayer | undefined
let onlineLoading = false
let disposed = false
let hoverTime = 0
function fitScope(animate = true) {
  if (!viewer || viewer.isDestroyed()) return
  const region =
    props.province?.bounds ??
    props.city?.bounds ??
    (props.scope === 'china' ? mapConfig.china : mapConfig.henan)
  flyToRegion(
    viewer,
    region,
    elevation.surface,
    tilted.value,
    animate ? 0.9 : 0,
    props.scope === 'china'
      ? props.expandedView
        ? 'country-expanded'
        : 'country'
      : props.expandedView
        ? 'region-expanded'
        : 'region',
  )
}
defineExpose({ resetView: fitScope })
watch(status, (value) => emit('statusChange', value), { immediate: true })

function drawSites() {
  if (!viewer || viewer.isDestroyed()) return
  viewer.entities.removeAll()
  if (props.scope !== 'henan' || !props.showSites) {
    viewer.scene.requestRender()
    return
  }
  for (const facility of props.facilities) {
    if (facility.boundSiteId && props.sites.some((site) => site.id === facility.boundSiteId))
      continue
    const selected = props.selectedFacilityId === facility.id
    const color = Color.fromCssColorString(facility.type === 'SERVICE' ? '#3cf1d2' : '#ffbc67')
    viewer.entities.add({
      id: `public-${facility.id}`,
      position: Cartesian3.fromDegrees(facility.longitude, facility.latitude, elevation.marker),
      point: {
        pixelSize: selected ? 13 : 6,
        scaleByDistance: new NearFarScalar(30000, 1.2, 1800000, 0.7),
        color: color.withAlpha(0.9),
        outlineColor: selected ? Color.WHITE : Color.fromCssColorString('#061a2b'),
        outlineWidth: 1.5,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
  }
  for (const site of props.sites) {
    const selected = props.selectedId === site.id
    // 点的颜色仅表示设施类型；离线和告警用标签及外环表达。
    const color = Color.fromCssColorString(site.type === 'SERVICE' ? '#3cf1d2' : '#ffbc67')
    viewer.entities.add({
      id: `site-${site.id}`,
      position: Cartesian3.fromDegrees(site.longitude, site.latitude, elevation.marker),
      point: {
        pixelSize: selected ? 15 : 10,
        color,
        outlineColor: selected ? Color.WHITE : Color.fromCssColorString('#061b2d'),
        outlineWidth: selected ? 3 : 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: `${site.name.replace(' · 演示', '')}${site.dataPending ? ' · 待接入' : site.status === 'offline' ? ' · 离线' : site.status === 'warning' ? ' !' : ''}`,
        font: selected ? mapFont(15, 600) : mapFont(13),
        fillColor: Color.fromCssColorString(
          selected ? '#ffffff' : site.type === 'SERVICE' ? '#a0f5e7' : '#f5d7b0',
        ),
        style: LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Color.fromCssColorString('#041726'),
        outlineWidth: 4,
        pixelOffset: site.complexCode
          ? new Cartesian2(site.type === 'SERVICE' ? -12 : 12, site.type === 'SERVICE' ? -26 : 26)
          : new Cartesian2(12, selected ? -26 : -17),
        horizontalOrigin:
          site.complexCode && site.type === 'SERVICE'
            ? HorizontalOrigin.RIGHT
            : HorizontalOrigin.LEFT,
        showBackground: selected,
        backgroundColor: Color.fromCssColorString('#08394b').withAlpha(0.9),
        backgroundPadding: new Cartesian2(8, 6),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    })
    if (selected)
      viewer.entities.add({
        id: `site-ring-${site.id}`,
        position: Cartesian3.fromDegrees(site.longitude, site.latitude),
        ellipse: {
          semiMajorAxis: site.complexCode ? 120 : 500,
          semiMinorAxis: site.complexCode ? 120 : 500,
          material: color.withAlpha(0.08),
          outline: true,
          outlineColor: color.withAlpha(0.7),
          height: elevation.surface + 30,
        },
      })
  }
  viewer.scene.requestRender()
}

function applyTheme() {
  if (!viewer || viewer.isDestroyed()) return
  const satellite = theme.value === 'satellite'
  if (gridLayer) gridLayer.show = !satellite
  if (localLayer) localLayer.show = satellite
  if (onlineLayer) onlineLayer.show = satellite
  administrative?.select(props.city?.code ?? props.provinceCode, theme.value)
  status.value = satellite
    ? onlineLayer
      ? 'Cesium ion 在线影像'
      : mapConfig.token
        ? '正在连接在线影像…'
        : '本地低清影像 · 未配置Token'
    : '科技海蓝 · 立体省市边界'
  viewer.scene.requestRender()
  if (satellite && mapConfig.token && !onlineLayer && !onlineLoading) void loadOnlineImagery()
}

async function loadOnlineImagery() {
  onlineLoading = true
  try {
    const provider = await createWorldImageryAsync()
    if (disposed || !viewer || viewer.isDestroyed()) return
    onlineLayer = viewer.imageryLayers.addImageryProvider(provider)
    provider.errorEvent.addEventListener(() => {
      if (!disposed && theme.value === 'satellite')
        status.value = '在线影像异常 · 检查资源权限或网络'
    })
    applyTheme()
  } catch {
    if (!disposed) status.value = '在线影像不可用 · 本地影像兜底'
  } finally {
    onlineLoading = false
  }
}

async function loadMapLayers() {
  if (!viewer) return
  const target = viewer
  try {
    administrative = await createAdministrativeLayers(
      target,
      props.scope,
      () => disposed,
      !!props.city,
      props.province,
    )
    if (!disposed) {
      administrative?.select(props.city?.code ?? props.provinceCode, theme.value)
      ready.value = true

      target.scene.requestRender()
    }
  } catch {
    if (!disposed) warning.value = '省市边界未加载，请刷新页面重试'
  }
  if (props.scope === 'henan' && !disposed) {
    let road
    try {
      road = await createRoadLayer(props.city?.code)
    } catch (error) {
      warning.value = error instanceof Error ? error.message : '高速路网加载失败'
      return
    }
    if (disposed || target.isDestroyed()) return
    roadSource = road.source
    filterRoads = road.filter
    roadSource.show = props.showRoads
    await target.dataSources.add(roadSource)
    if (disposed || target.isDestroyed()) return
    roadCount.value = road.filter(props.highway ?? '')
    roadsReady.value = true
    roadIsDemo.value = road.isDemo
    emit('networkReady', roadCount.value, road.isDemo)
    target.scene.requestRender()
  }
}

function pickEntity(position: Cartesian2): Entity | undefined {
  const picked = viewer?.scene.pick(position) as { id?: unknown } | undefined
  return picked?.id instanceof Entity ? picked.id : undefined
}

onMounted(() => {
  try {
    if (!host.value) return
    Ion.defaultAccessToken = mapConfig.token
    viewer = new Viewer(host.value, {
      sceneMode: SceneMode.SCENE3D,
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      baseLayer: false,
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity,
      useBrowserRecommendedResolution: true,
    })
    // Cesium此模式默认按CSS像素渲染，乘受控像素比提升清晰度，而不是除以DPR。
    viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 1.75)
    viewer.scene.globe.baseColor = Color.fromCssColorString('#0d2b4b')
    viewer.scene.backgroundColor = Color.fromCssColorString('#0d2b4b')
    if (viewer.scene.skyBox) viewer.scene.skyBox.show = false
    if (viewer.scene.skyAtmosphere) viewer.scene.skyAtmosphere.show = false
    if (viewer.scene.sun) viewer.scene.sun.show = false
    if (viewer.scene.moon) viewer.scene.moon.show = false
    viewer.scene.light = new DirectionalLight({
      direction: new Cartesian3(0.4, -0.7, -0.5),
      intensity: 1.8,
    })
    viewer.scene.screenSpaceCameraController.enableTilt = false
    viewer.scene.screenSpaceCameraController.minimumZoomDistance = elevation.surface + 500
    if (props.scope === 'henan')
      viewer.creditDisplay.addStaticCredit(
        new Credit(
          '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> · ODbL · Geo2Day',
          true,
        ),
      )
    viewer.scene.globe.showGroundAtmosphere = false
    gridLayer = viewer.imageryLayers.addImageryProvider(
      new GridImageryProvider({
        color: Color.fromCssColorString('#2c75a7').withAlpha(props.scope === 'china' ? 0.12 : 0.05),
        backgroundColor: Color.fromCssColorString('#0d2b4b'),
        glowColor: Color.TRANSPARENT,
        glowWidth: 0,
        cells: 5,
      }),
    )
    fitScope(false)
    drawSites()
    applyTheme()
    void loadMapLayers()
    void TileMapServiceImageryProvider.fromUrl(buildModuleUrl('Assets/Textures/NaturalEarthII'))
      .then((provider) => {
        if (disposed || !viewer || viewer.isDestroyed()) return
        localLayer = viewer.imageryLayers.addImageryProvider(provider)
        localLayer.brightness = 0.65
        localLayer.saturation = 0.55
        localLayer.show = theme.value === 'satellite'
        viewer.scene.requestRender()
      })
      .catch(() => {
        /* 科技矢量底图不依赖本地影像。 */
      })
    handler = new ScreenSpaceEventHandler(viewer.scene.canvas)
    configureMapWheelZoom(viewer, handler, props.scope, elevation.surface)

    handler.setInputAction((event: { position: Cartesian2 }) => {
      const entity = pickEntity(event.position)
      if (!entity) return
      if (entity.id.startsWith('public-')) {
        selectedFacility.value = props.facilities.find((item) => `public-${item.id}` === entity.id)
        if (selectedFacility.value) emit('selectFacility', selectedFacility.value)
        return
      }
      selectedFacility.value = undefined
      if (
        props.scope === 'henan' &&
        entity.id.startsWith('site-') &&
        !entity.id.startsWith('site-ring-')
      )
        emit('selectSite', entity.id.slice(5))
      if (props.scope === 'china') {
        const code = Number(entity.properties?.adcode?.getValue())
        const name = String(entity.properties?.name?.getValue() ?? '')
        if (Number.isFinite(code) && name) emit('selectProvince', { code, name })
      }
      if (props.scope === 'henan') {
        const code = Number(entity.properties?.adcode?.getValue())
        const name = String(entity.properties?.name?.getValue() ?? '')
        if (Number.isFinite(code) && name) emit('selectCity', { code, name })
      }
    }, ScreenSpaceEventType.LEFT_CLICK)
    handler.setInputAction((event: { endPosition: Cartesian2 }) => {
      if (performance.now() - hoverTime < 90) return
      hoverTime = performance.now()
      const entity = pickEntity(event.endPosition)
      const name = String(entity?.properties?.name?.getValue() ?? '')
      const clickable = Boolean(
        name || entity?.id.startsWith('site-') || entity?.id.startsWith('public-'),
      )
      hoverName.value = name
      if (host.value) host.value.style.cursor = clickable ? 'pointer' : 'grab'
    }, ScreenSpaceEventType.MOUSE_MOVE)
  } catch (error) {
    fatal.value = `地图初始化失败：${error instanceof Error ? error.message : String(error)}`
    if (viewer && !viewer.isDestroyed()) viewer.destroy()
    viewer = undefined
  }
})

watch(
  () => [
    props.sites,
    props.facilities,
    props.selectedId,
    props.selectedFacilityId,
    props.showSites,
  ],
  () => {
    selectedFacility.value = undefined
    drawSites()
  },
  { deep: true },
)
watch(
  () => props.showRoads,
  (show) => {
    if (roadSource) roadSource.show = show
    viewer?.scene.requestRender()
  },
)
watch(
  () => props.provinceCode,
  () => {
    administrative?.select(props.city?.code ?? props.provinceCode, theme.value)
  },
)
watch(theme, applyTheme)
watch(
  () => props.highway,
  (highway) => {
    if (!filterRoads || !viewer || viewer.isDestroyed()) return
    roadCount.value = filterRoads(highway ?? '')
    emit('networkReady', roadCount.value, roadIsDemo.value)
    viewer.scene.requestRender()
  },
)
watch(tilted, () => fitScope())
// 全国、省市收起侧栏时拉近当前区域；展开恢复标准全域构图，不改变滚轮规则。
watch(
  () => props.expandedView,
  () => {
    fitScope()
  },
)
watch(
  () => props.selectedFacilityId,
  (id) => {
    const facility = props.facilities.find((item) => item.id === id)
    if (!facility || !viewer || viewer.isDestroyed()) return
    flyToRegion(
      viewer,
      {
        west: facility.longitude - 0.025,
        south: facility.latitude - 0.02,
        east: facility.longitude + 0.025,
        north: facility.latitude + 0.02,
      },
      elevation.surface,
      tilted.value,
      0.75,
    )
  },
)
watch(
  () => props.selectedId,
  (id) => {
    const site = props.sites.find((item) => item.id === id)
    if (!site || !viewer || viewer.isDestroyed()) return
    const group = site.complexCode
      ? props.sites.filter((item) => item.complexCode === site.complexCode)
      : [site]
    const lonPadding = site.complexCode ? 0.009 : 0.025
    const latPadding = site.complexCode ? 0.008 : 0.02
    flyToRegion(
      viewer,
      {
        west: Math.min(...group.map((item) => item.longitude)) - lonPadding,
        south: Math.min(...group.map((item) => item.latitude)) - latPadding,
        east: Math.max(...group.map((item) => item.longitude)) + lonPadding,
        north: Math.max(...group.map((item) => item.latitude)) + latPadding,
      },
      elevation.surface,
      tilted.value,
      0.75,
    )
  },
)
onUnmounted(() => {
  disposed = true
  if (handler && !handler.isDestroyed()) handler.destroy()
  if (viewer && !viewer.isDestroyed()) viewer.destroy()
})
</script>
