<template>
  <div class="dashboard-view province-workspace">
    <MapWorkspaceLayout class="province-grid" v-model:panels-visible="panelsVisible">
      <template #left>
        <PanelCard title="省域工作空间" eyebrow="PROVINCE WORKSPACE">
          <h3 class="snapshot-title">{{ province?.name ?? '省域地图' }}</h3>
          <p class="muted-note">独立省域视图 · 主体轮廓自动适配</p>
          <label class="sidebar-city-picker province-switcher"
            >切换省级区域
            <select
              :value="province?.code ?? ''"
              aria-label="切换省级区域"
              @change="
                router.push(provincePath(Number(($event.target as HTMLSelectElement).value)))
              "
            >
              <option disabled value="">选择省级区域</option>
              <option v-for="item in provinces" :key="item.code" :value="item.code">
                {{ item.name }}
              </option>
            </select>
          </label>
          <MapDisplayControls
            scope="province"
            :title="province?.name ?? '省域视图'"
            :status="status"
            v-model:theme="theme"
            v-model:tilted="tilted"
            @reset="stage?.resetView()"
          />
          <RouterLink class="primary-button full-width" to="/overview">← 返回中国地图</RouterLink>
          <p class="muted-note">
            各省采用同一套海蓝配色、立体轮廓与半透明面板。详细高速路线和设施台账将按省逐步接入。
          </p>
          <RouterLink class="text-button" to="/province/henan">查看河南高速与三维实例 ↗</RouterLink>
        </PanelCard>
      </template>
      <template #map>
        <CesiumMap
          v-if="province"
          ref="stage"
          :key="province.code"
          scope="province"
          :expanded-view="!panelsVisible"
          :province="province"
          :province-code="province.code"
          external-controls
          v-model:theme="theme"
          v-model:tilted="tilted"
          @status-change="status = $event"
        />
        <div v-else class="empty-state">
          {{
            error || (provinces.length ? '未找到该省级区域，请返回中国地图选择' : '省域目录加载中…')
          }}
        </div>
      </template>
      <template #right>
        <div class="right-stack">
          <PanelCard title="区域接入状态" eyebrow="DATA COVERAGE">
            <dl class="detail-list">
              <div>
                <dt>省域轮廓</dt>
                <dd>已接入</dd>
              </div>
              <div>
                <dt>显示方式</dt>
                <dd>立体 / 俯视</dd>
              </div>
              <div>
                <dt>详细高速路网</dt>
                <dd>待接入</dd>
              </div>
              <div>
                <dt>服务区 / 收费站</dt>
                <dd>待接入</dd>
              </div>
              <div>
                <dt>本站电力数据</dt>
                <dd>待接入</dd>
              </div>
            </dl>
            <p class="muted-note">
              当前显示省级行政边界，不用河南的线路或演示站点替代其他省份数据。
            </p>
          </PanelCard>
          <PanelCard title="地图说明" eyebrow="REGION ATLAS">
            <p class="muted-note">
              边界来自现有阿里云DataV.GeoAtlas中国省级数据。显示厚度是视觉效果；可在左侧切换卫星影像或俯视。
            </p>
            <p class="muted-note">
              镜头优先适配区域主体。附属岛屿几何仍保留，南海位置可在全国视图查看。
            </p>
          </PanelCard>
        </div>
      </template>
    </MapWorkspaceLayout>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CesiumMap from '@/components/map/CesiumMap.vue'
import MapWorkspaceLayout from '@/layouts/MapWorkspaceLayout.vue'
import MapDisplayControls from '@/components/map/MapDisplayControls.vue'
import PanelCard from '@/components/common/PanelCard.vue'
import { getProvinceRegions } from '@/services/mapService'
import { provincePath } from '@/utils/provinceCatalog'
import type { ProvinceRegion } from '@/types/map'

const route = useRoute()
const router = useRouter()
const provinces = ref<ProvinceRegion[]>([])
const error = ref('')
const province = computed(() =>
  provinces.value.find((item) => item.code === Number(route.params.provinceCode)),
)
const stage = ref<InstanceType<typeof CesiumMap>>()
const panelsVisible = ref(true)
const theme = ref<'blue' | 'satellite'>('blue')
const tilted = ref(true)
const status = ref('地图初始化中…')
onMounted(async () => {
  try {
    provinces.value = await getProvinceRegions()
  } catch {
    error.value = '省域目录加载失败，请刷新重试'
  }
})
</script>
