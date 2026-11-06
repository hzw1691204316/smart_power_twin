<template>
  <section class="hud-panel" :class="{ 'hud-panel-accent': accent }">
    <header>
      <span class="hud-panel-diamond" />
      <h2>{{ title }}</h2>
      <small v-if="caption">{{ caption }}</small
      ><span class="hud-panel-stripes"><i /><i /><i /></span><slot name="action" />
    </header>
    <div class="hud-panel-body"><slot /></div>
  </section>
</template>
<script setup lang="ts">
defineProps<{ title: string; caption?: string; accent?: boolean }>()
</script>
