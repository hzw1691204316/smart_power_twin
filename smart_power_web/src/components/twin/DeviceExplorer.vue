<template>
  <div class="hud-device-list">
    <button
      v-for="device in devices"
      :key="device.id"
      :class="{ selected: selectedId === device.id }"
      @click="$emit('select', device.id)"
    >
      <span class="hud-device-symbol">{{
        device.category === '光伏系统' ? '☀' : device.category === '储能系统' ? '▤' : 'ϟ'
      }}</span
      ><span
        >{{ device.name }}<small>{{ device.category }}</small></span
      ><i class="status-dot" :class="device.status" /><b>›</b>
    </button>
    <p v-if="!devices.length" class="hud-empty">该分类暂无设备</p>
  </div>
</template>
<script setup lang="ts">
import type { SceneDevice } from '@/types/domain'
defineProps<{ devices: SceneDevice[]; selectedId: string }>()
defineEmits<{ select: [id: string] }>()
</script>

<style scoped>
.status-dot.unknown {
  background: #829eb4;
  box-shadow: none;
}
</style>
