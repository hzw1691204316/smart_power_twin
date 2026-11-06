<template>
  <article class="metric-card" :style="{ '--metric-accent': accent || '#43d9e6' }">
    <p>{{ label }}</p>
    <div>
      <strong>{{ value }}</strong
      ><span>{{ unit }}</span>
    </div>
    <small>{{ hint }}</small
    ><span class="metric-line" />
  </article>
</template>
<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  unit?: string
  hint?: string
  accent?: string
}>()
</script>
