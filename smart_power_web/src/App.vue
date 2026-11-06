<template>
  <RouterView v-if="route.name === 'login'" />
  <AppLayout v-else><RouterView /></AppLayout>
</template>

<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue'
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
