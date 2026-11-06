<template>
  <details class="map-sidebar-controls">
    <summary>
      <span>地图设置</span><small>{{ title }}</small>
    </summary>
    <div class="map-settings-body">
      <p class="map-status-text" role="status">{{ status }}</p>
      <label v-if="scope === 'henan'" class="sidebar-city-picker"
        >地市路网
        <select
          :value="cityCode ?? ''"
          aria-label="选择地市路网"
          @change="
            $emit(
              'city',
              ($event.target as HTMLSelectElement).value
                ? Number(($event.target as HTMLSelectElement).value)
                : undefined,
            )
          "
        >
          <option value="">河南全省</option>
          <option v-for="city in cities" :key="city.code" :value="city.code">
            {{ city.name }}
          </option>
        </select>
      </label>
      <div class="sidebar-segment" role="group" aria-label="地图底图">
        <button :aria-pressed="theme === 'blue'" @click="theme = 'blue'">科技蓝图</button>
        <button :aria-pressed="theme === 'satellite'" @click="theme = 'satellite'">卫星影像</button>
      </div>
      <div class="sidebar-segment" role="group" aria-label="地图视角">
        <button :aria-pressed="tilted" @click="tilted = !tilted">
          {{ tilted ? '立体视角' : '俯视视角' }}
        </button>
        <button @click="$emit('reset')">全域复位</button>
      </div>
      <div v-if="scope === 'henan'" class="sidebar-layer-controls">
        <label><input v-model="showRoads" type="checkbox" />高速路线</label>
        <label><input v-model="showSites" type="checkbox" />设施站点</label>
      </div>
      <p class="muted-note">
        {{
          scope === 'china'
            ? '点击省份进入省域地图；河南可查看高速路网。'
            : scope === 'province'
              ? '省域轮廓已接入，详细路网与设施待接入。'
              : '点击地市下钻，点击绿色或黄色点进入三维。'
        }}
      </p>
    </div>
  </details>
</template>

<script setup lang="ts">
import type { CityRegion } from '@/types/map'
withDefaults(
  defineProps<{
    scope: 'china' | 'henan' | 'province'
    title: string
    status: string
    cityCode?: number
    cities?: CityRegion[]
  }>(),
  { cities: () => [] },
)
const theme = defineModel<'blue' | 'satellite'>('theme', { default: 'blue' })
const tilted = defineModel<boolean>('tilted', { default: true })
const showRoads = defineModel<boolean>('showRoads', { default: true })
const showSites = defineModel<boolean>('showSites', { default: true })
defineEmits<{ city: [code: number | undefined]; reset: [] }>()
</script>
