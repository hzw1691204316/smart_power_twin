<template>
  <section class="sidebar-map-legend" aria-label="地图标记说明">
    <h3>地图图例</h3>
    <div><i class="legend-service" /><span>服务区</span></div>
    <div><i class="legend-toll" /><span>收费站 / 收费设施</span></div>
    <div>
      <i class="legend-road" :style="{ background: mapPalette.roadNational }" /><span
        >高速路线（明亮实线）</span
      >
    </div>
    <div>
      <i class="legend-road" :style="{ background: mapPalette.boundary, height: '1px' }" /><span
        >行政边界（细暗线）</span
      >
    </div>
    <p>点击标记进入三维；未绑定实景的公开位置使用同类型通用模板。</p>
  </section>
</template>
<script setup lang="ts">
import { mapPalette } from '@/config/mapPalette'
</script>
