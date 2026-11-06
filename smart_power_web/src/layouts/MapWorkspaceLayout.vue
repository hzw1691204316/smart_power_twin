<template>
  <div class="map-workspace" :class="{ 'panels-hidden': !panelsVisible }">
    <section class="workspace-map" aria-label="地图工作区"><slot name="map" /></section>
    <aside v-show="panelsVisible" class="workspace-left" aria-label="区域与站点检索">
      <slot name="left" />
    </aside>
    <aside v-show="panelsVisible" class="workspace-right" aria-label="站点与能源信息">
      <slot name="right" />
    </aside>
    <button
      class="workspace-panels-toggle"
      :aria-expanded="panelsVisible"
      @click="panelsVisible = !panelsVisible"
    >
      {{ panelsVisible ? '收起面板' : '显示面板' }}
    </button>
  </div>
</template>

<script setup lang="ts">
/** 面板可见状态可由页面同步；未绑定时仍在组件内部管理。 */
const panelsVisible = defineModel<boolean>('panelsVisible', { default: true })
</script>
