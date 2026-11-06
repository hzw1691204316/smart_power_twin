<template>
  <div class="app-shell" :class="{ 'immersive-shell': isScene, 'province-shell': isMapWorkspace }">
    <header v-if="!isScene" class="app-header">
      <RouterLink to="/overview" class="brand"
        ><span class="brand-mark">ϟ</span
        ><span
          ><strong>智慧电力 · 数字孪生</strong><small>SMART POWER / DIGITAL TWIN</small></span
        ></RouterLink
      >
      <div v-if="isMapWorkspace" class="header-page-context">
        <h1>{{ regionTitle }}</h1>
        <div>
          <small>{{
            route.name === 'overview'
              ? '中国 · 点击省份进入'
              : route.name === 'province'
                ? '省域轮廓 · 路网待接入'
                : route.name === 'henan-city'
                  ? '市域视野'
                  : '点击地市下钻'
          }}</small>
          <RouterLink
            v-if="isProvince"
            :to="route.name === 'henan-city' ? '/province/henan' : '/overview'"
            >← {{ route.name === 'henan-city' ? '返回河南全省' : '全国概览' }}</RouterLink
          >
        </div>
      </div>
      <nav class="main-nav" aria-label="主导航">
        <RouterLink to="/overview" :class="{ active: route.name === 'overview' }"
          ><span>01</span> 全国概览</RouterLink
        >
        <RouterLink
          to="/province/henan"
          :class="{ active: route.name === 'henan' || route.name === 'henan-city' }"
          ><span>02</span> 河南路网</RouterLink
        >
        <span class="nav-label" :class="{ active: route.name === 'site' }"
          ><span>03</span> 站点孪生</span
        >
      </nav>
      <div class="header-meta">
        <UserMenu />
        <span class="demo-chip">演示电力数据</span><time>{{ timeText }}</time
        ><span class="timezone">北京时间</span>
      </div>
    </header>
    <main class="app-main"><slot /></main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getCityRegions, getProvinceRegions } from '@/services/mapService'
import type { CityRegion, ProvinceRegion } from '@/types/map'
import UserMenu from '@/components/common/UserMenu.vue'
const route = useRoute()
const isScene = computed(() => route.name === 'site' || route.name === 'facility')
const isProvince = computed(
  () => route.name === 'henan' || route.name === 'henan-city' || route.name === 'province',
)
const isMapWorkspace = computed(() => isProvince.value || route.name === 'overview')
const cities = ref<CityRegion[]>([])
const provinces = ref<ProvinceRegion[]>([])
const regionTitle = computed(() =>
  route.name === 'province'
    ? `${provinces.value.find((item) => item.code === Number(route.params.provinceCode))?.name ?? '省域'}地图`
    : route.name === 'henan-city'
      ? `${cities.value.find((city) => city.code === Number(route.params.cityCode))?.name ?? '地市'}高速路网`
      : route.name === 'overview'
        ? '全国能源运行概览'
        : '河南全省高速路网',
)
watch(
  () => route.name,
  async (name) => {
    try {
      if (name === 'province' && !provinces.value.length)
        provinces.value = await getProvinceRegions()
      if ((name === 'henan' || name === 'henan-city') && !cities.value.length)
        cities.value = await getCityRegions()
    } catch {
      /* 页面内保留目录加载错误提示。 */
    }
  },
  { immediate: true },
)
const now = ref(new Date())
let timer: ReturnType<typeof setInterval> | undefined
const timeText = computed(() =>
  now.value.toLocaleTimeString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' }),
)
onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
