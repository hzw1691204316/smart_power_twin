<template>
  <div class="site-filters">
    <label class="search-field"
      ><span>⌕</span
      ><input
        :value="query"
        placeholder="名称 / 城市 / 编码，可空格组合"
        aria-label="搜索站点"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
    /></label>
    <div class="filter-row">
      <select
        :value="type"
        aria-label="站点类型"
        @change="emit('update:type', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">全部类型</option>
        <option value="TOLL">收费站</option>
        <option value="SERVICE">服务区</option></select
      ><select
        :value="highway"
        aria-label="高速路线"
        @change="emit('update:highway', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">全部路线</option>
        <option v-for="code in highways" :key="code" :value="code">{{ code }}</option>
      </select>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{ query: string; type: string; highway: string; highways: string[] }>()
const emit = defineEmits<{
  'update:query': [value: string]
  'update:type': [value: string]
  'update:highway': [value: string]
}>()
</script>
