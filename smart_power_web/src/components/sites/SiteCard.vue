<template>
  <button class="site-card" :class="{ selected }" @click="$emit('select', site.id)">
    <div class="site-card-top">
      <span class="site-icon" :class="site.type">{{ site.type === 'TOLL' ? '站' : '服' }}</span
      ><span class="site-card-name"
        >{{ site.name
        }}<small>{{ site.highway }} · {{ site.city }} · {{ typeLabel[site.type] }}</small></span
      ><span
        class="status-dot"
        :class="site.dataPending ? 'unknown' : site.status"
        :title="site.dataPending ? '待接入' : statusLabel[site.status]"
      />
    </div>
    <div class="site-card-bottom">
      <span>{{
        site.dataPending
          ? '运行数据待接入'
          : site.status === 'offline'
            ? '暂无新数据'
            : `${site.powerKw.toFixed(1)} kW`
      }}</span
      ><span>{{ site.dataPending ? '待接入' : statusLabel[site.status] }} <b>↗</b></span>
    </div>
  </button>
</template>
<script setup lang="ts">
import type { Site } from '@/types/domain'
import { statusLabel, typeLabel } from '@/data/demo'
defineProps<{ site: Site; selected?: boolean }>()
defineEmits<{ select: [id: string] }>()
</script>
