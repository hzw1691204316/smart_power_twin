<template>
  <div class="hud-power-values">
    <div>
      <span>示例站点负荷</span
      ><strong
        >{{ site.status === 'offline' ? '—' : site.powerKw.toFixed(1) }}<small>kW</small></strong
      >
    </div>
    <div>
      <span>示例光伏出力</span
      ><strong
        >{{ site.status === 'offline' ? '—' : site.pvKw.toFixed(1) }}<small>kW</small></strong
      >
    </div>
  </div>
  <div class="hud-power-bar">
    <span>负荷</span
    ><i
      ><b :style="{ width: `${site.status === 'offline' ? 0 : (site.powerKw / max) * 100}%` }"
    /></i>
  </div>
  <div class="hud-power-bar photovoltaic">
    <span>光伏</span
    ><i><b :style="{ width: `${site.status === 'offline' ? 0 : (site.pvKw / max) * 100}%` }" /></i>
  </div>
  <div class="hud-daily-energy">
    <span>示例日用电</span
    ><strong
      >{{ site.status === 'offline' ? '—' : site.dailyEnergyKwh.toLocaleString('zh-CN')
      }}<small>kWh</small></strong
    >
  </div>
  <p class="hud-data-caption">独立展示各指标，不表示已完成能量平衡计算</p>
  <details class="hud-provenance">
    <summary>数据与场景说明 · 尚未接入现场</summary>
    <p>读数：固定演示值；采样时间和数据质量尚未提供。顶部时钟为系统时间。</p>
    <p>
      场景：中型通用模型，非本站实景测绘。{{
        site.locationNote || '站点为流程演示样例，位置与设施待现场核验。'
      }}
    </p>
    <p>站点编码：{{ site.code }} · {{ site.highway }}</p>
    <p>参考位置（WGS84）：{{ site.longitude.toFixed(6) }}, {{ site.latitude.toFixed(6) }}</p>
  </details>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Site } from '@/types/domain'
const props = defineProps<{ site: Site }>()
const max = computed(() => Math.max(props.site.powerKw, props.site.pvKw, 1))
</script>
