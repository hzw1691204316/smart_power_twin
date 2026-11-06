<template>
  <div class="site-list">
    <button
      v-for="facility in facilities.slice(0, limit)"
      :key="facility.id"
      class="site-card"
      :class="{
        selected:
          selectedId === facility.id ||
          (!!selectedSiteId && selectedSiteId === facility.boundSiteId),
      }"
      @click="$emit('select', facility)"
    >
      <div class="site-card-top">
        <span class="site-icon" :class="facility.type">{{
          facility.type === 'SERVICE' ? '服' : '站'
        }}</span>
        <span class="site-card-name"
          >{{ facility.name
          }}<small
            >{{ cities.find((city) => city.code === facility.cityCode)?.name ?? '归属待核验' }} ·
            {{ facility.ref || '路线待核验' }}</small
          ></span
        >
      </div>
      <div class="site-card-bottom">
        <span>{{ facility.boundSiteId ? '已绑定三维样板' : '公开位置 · 尚未接入' }}</span
        ><span>定位 ↗</span>
      </div>
    </button>
    <p v-if="!facilities.length" class="empty-state">
      没有匹配的公开位置；路线不明的设施不参与路线筛选。
    </p>
    <button v-if="facilities.length > limit" class="text-button" @click="$emit('more')">
      再显示40条（已显示{{ limit }} / {{ facilities.length }}）
    </button>
  </div>
</template>

<script setup lang="ts">
import type { PublicFacility, CityRegion } from '@/types/map'
defineProps<{
  facilities: PublicFacility[]
  cities: CityRegion[]
  selectedId: string
  selectedSiteId: string
  limit: number
}>()
defineEmits<{ select: [facility: PublicFacility]; more: [] }>()
</script>
