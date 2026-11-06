<template>
  <section class="panel-card">
    <header class="panel-heading">
      <div>
        <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
      </div>
      <slot name="action" />
    </header>
    <slot />
  </section>
</template>
<script setup lang="ts">
defineProps<{ title: string; eyebrow?: string }>()
</script>
