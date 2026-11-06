<template>
  <div class="hud-alarm-summary">
    <div class="hud-alarm-ring" :class="{ hasWarning: count > 0 }">
      <strong>{{ count }}</strong
      ><span>演示事件</span>
    </div>
    <div>
      <template v-if="site.status === 'offline'"
        ><strong>站点通信离线</strong>
        <p>当前设备读数不可用</p></template
      ><template v-else-if="warnings.length"
        ><strong>设备温度关注</strong>
        <p>{{ warnings[0]?.name }}</p>
        <button @click="emit('locate', warnings[0]!.id)">定位设备 ↗</button></template
      ><template v-else
        ><strong>暂无活动演示事件</strong>
        <p>设备样例状态正常</p></template
      >
    </div>
  </div>
  <p class="hud-data-caption">公开通用模板示意 · 不请求私有站点告警</p>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { Site } from '@/types/domain'
const props = defineProps<{ site: Site }>()
const emit = defineEmits<{ locate: [deviceId: string] }>()
const warnings = computed(() => props.site.devices.filter((device) => device.status === 'warning'))
const count = computed(() => (props.site.status === 'offline' ? 1 : warnings.value.length))
</script>
