<template>
  <div class="hud-device-status">
    <div class="hud-ring-orbit">
      <div class="hud-status-ring" :style="{ background: ring }">
        <div>
          <strong>{{ devices.length }}</strong
          ><span>设备对象</span>
        </div>
      </div>
    </div>
    <dl>
      <div>
        <dt><i class="normal" />正常</dt>
        <dd>{{ counts.normal }}</dd>
      </div>
      <div>
        <dt><i class="warning" />关注</dt>
        <dd>{{ counts.warning }}</dd>
      </div>
      <div>
        <dt><i class="offline" />离线</dt>
        <dd>{{ counts.offline }}</dd>
      </div>
    </dl>
  </div>
  <p class="hud-data-caption">当前站点模型绑定对象 · 演示状态</p>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '@/types/domain'
const props = defineProps<{ devices: Device[] }>()
const counts = computed(() => ({
  normal: props.devices.filter((device) => device.status === 'normal').length,
  warning: props.devices.filter((device) => device.status === 'warning').length,
  offline: props.devices.filter((device) => device.status === 'offline').length,
}))
const ring = computed(() => {
  const total = props.devices.length || 1
  const normal = (counts.value.normal / total) * 100
  const warning = normal + (counts.value.warning / total) * 100
  return `conic-gradient(from -90deg, #26c9f0 0% ${normal}%, #f6b460 ${normal}% ${warning}%, #506e86 ${warning}% 100%)`
})
</script>
