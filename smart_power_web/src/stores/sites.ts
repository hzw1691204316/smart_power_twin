import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getSites } from '@/services/siteService'
import type { Site } from '@/types/domain'

export const useSitesStore = defineStore('sites', () => {
  const sites = ref<Site[]>([])
  const loading = ref(false)
  const error = ref('')
  let generation = 0
  let loaded = false
  /** 清空账号相关数据；generation使先前未完成的请求不能重新填入旧数据。 */
  function reset() {
    generation++
    loaded = false
    sites.value = []
    loading.value = false
    error.value = ''
  }
  const totalPower = computed(() =>
    sites.value
      .filter((site) => !site.dataPending && site.status !== 'offline')
      .reduce((sum, site) => sum + site.powerKw, 0),
  )
  const totalPv = computed(() =>
    sites.value
      .filter((site) => !site.dataPending && site.status !== 'offline')
      .reduce((sum, site) => sum + site.pvKw, 0),
  )
  const onlineCount = computed(
    () => sites.value.filter((site) => !site.dataPending && site.status !== 'offline').length,
  )
  async function load() {
    if (loaded || loading.value) return
    const current = generation
    loading.value = true
    error.value = ''
    try {
      const result = await getSites()
      if (current === generation) {
        sites.value = result
        loaded = true
      }
    } catch (cause) {
      if (current === generation)
        error.value = cause instanceof Error ? cause.message : '站点数据加载失败，请刷新重试'
    } finally {
      if (current === generation) loading.value = false
    }
  }
  return { sites, loading, error, totalPower, totalPv, onlineCount, load, reset }
})
