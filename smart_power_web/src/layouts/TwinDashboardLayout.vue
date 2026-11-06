<template>
  <section ref="screen" class="twin-dashboard" :class="{ 'hud-clean': clean }">
    <div class="hud-scene-layer"><slot name="scene" /></div>
    <div class="hud-scene-shade" />
    <header class="hud-header">
      <div class="hud-header-left">
        <UserMenu />
        <RouterLink :to="returnTo">‹ 返回路网</RouterLink
        ><RouterLink to="/overview" class="hud-home-link">全国概览</RouterLink>
      </div>
      <div class="hud-title-frame">
        <span class="hud-title-wing" />
        <div>
          <h1>{{ title }}</h1>
          <p :title="subtitle">{{ subtitle }}</p>
        </div>
        <span class="hud-title-wing right" />
      </div>
      <div class="hud-header-clock">
        <time>{{ time }}</time
        ><span>{{ date }}<small>北京时间</small></span>
      </div>
    </header>
    <div class="hud-summary"><slot name="summary" /></div>
    <aside class="hud-sidebar hud-left"><slot name="left" /></aside>
    <aside class="hud-sidebar hud-right"><slot name="right" /></aside>
    <div class="hud-category-rail"><slot name="categories" /></div>
    <div class="hud-scene-toolbar">
      <slot name="toolbar" /><button :class="{ selected: clean }" @click="clean = !clean">
        <span>▣</span>{{ clean ? '显示面板' : '纯净场景' }}</button
      ><button @click="fullscreen"><span>⛶</span>全屏</button>
    </div>
    <p v-if="screenError" class="hud-toast">{{ screenError }}</p>
    <div class="hud-scene-description">
      <i class="live-dot" /> 可旋转 · 可缩放 · 可点击设备 <span>/</span>
      {{ description ?? '模型模板与演示电力数据' }}
    </div>
    <nav class="hud-bottom-nav" aria-label="站点功能">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="{ active: activeTab === tab.id }"
        :aria-pressed="activeTab === tab.id"
        @click="emit('update:activeTab', tab.id)"
      >
        <span>{{ tab.icon }}</span
        >{{ tab.label }}<i v-if="activeTab === tab.id" />
      </button>
    </nav>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import UserMenu from '@/components/common/UserMenu.vue'
defineProps<{
  title: string
  subtitle: string
  returnTo: string
  activeTab: string
  description?: string
}>()
const emit = defineEmits<{ 'update:activeTab': [tab: string] }>()
const now = ref(new Date())
const clean = ref(false)
const screen = ref<HTMLElement>()
const screenError = ref('')
const time = computed(() =>
  now.value.toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }),
)
const date = computed(() =>
  now.value.toLocaleDateString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }),
)
const tabs = [
  { id: 'overview', label: '站点总览', icon: '◈' },
  { id: 'devices', label: '设备监测', icon: '▤' },
  { id: 'power', label: '光伏储能', icon: 'ϟ' },
  { id: 'energy', label: '能耗分析', icon: '⌁' },
  { id: 'alarms', label: '告警中心', icon: '◇' },
]
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
async function fullscreen() {
  try {
    screenError.value = ''
    if (document.fullscreenElement) await document.exitFullscreen()
    else await screen.value?.requestFullscreen()
  } catch {
    screenError.value = '当前浏览器未允许全屏，可按F11查看'
  }
}
</script>
