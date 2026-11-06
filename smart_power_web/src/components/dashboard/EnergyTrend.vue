<template>
  <div class="energy-trend">
    <div class="trend-caption">
      <span>{{ title || '日内功率趋势' }}</span
      ><small>形态示意 · 非采样数据</small>
    </div>
    <svg viewBox="0 0 420 130" role="img" aria-label="示意功率曲线">
      <path d="M0 25H420M0 65H420M0 105H420" fill="none" stroke="#233c50" stroke-dasharray="3 5" />
      <path
        d="M0 115L28 112L56 110L84 98L112 83L140 67L168 41L196 26L224 37L252 20L280 35L308 55L336 79L364 94L392 105L420 109L420 130L0 130Z"
        fill="rgba(49,211,222,.09)"
      />
      <path
        d="M0 115L28 112L56 110L84 98L112 83L140 67L168 41L196 26L224 37L252 20L280 35L308 55L336 79L364 94L392 105L420 109"
        fill="none"
        stroke="#43d9e6"
        stroke-width="2.5"
      />
    </svg>
    <div class="axis-labels">
      <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ title?: string }>()
</script>
