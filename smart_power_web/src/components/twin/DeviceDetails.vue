<template>
  <div v-if="device" class="device-details">
    <span class="status-badge" :class="device.status">{{ statusLabel[device.status] }}</span>
    <h3 class="snapshot-title">{{ device.name }}</h3>
    <p class="snapshot-subtitle">{{ device.category }} / {{ device.objectKey }}</p>
    <div class="device-power">
      <span>示例有功功率</span
      ><strong>{{ device.status === 'offline' ? '—' : device.powerKw }}<small>kW</small></strong>
    </div>
    <dl class="detail-list">
      <div v-for="metric in device.metrics" :key="metric.label">
        <dt>{{ metric.label }}</dt>
        <dd>{{ metric.value }} {{ metric.unit }}</dd>
      </div>
    </dl>
    <p v-if="device.status === 'offline'" class="warning-note">
      此站点为离线演示样例，不显示当前测点读数。
    </p>
    <p class="muted-note">{{ device.description }}</p>
  </div>
  <div v-else class="selection-placeholder">
    <span>◇</span>
    <p>选择模型或设备列表</p>
    <small>设备资料与电力指标将在这里展示</small>
  </div>
</template>
<script setup lang="ts">
import { statusLabel } from '@/data/demo'
import type { Device } from '@/types/domain'
defineProps<{ device?: Device }>()
</script>
