/** 大屏状态：切地市、站点、来源或账号时立即清空；禁止迟到响应覆盖，不启动自动采集或轮询。 */
import { ref, watch, onUnmounted, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getDashboardSummary } from '@/services/dashboardService'
import type { DashboardScope, DashboardSource, DashboardSummary } from '@/types/dashboard'
/** scope是授权汇总范围，enabled=false用于公开模型或未就绪的城市，绝不查询私有大屏。 */
export function useDashboardSummary(scope: Ref<DashboardScope>, enabled: Ref<boolean>) {
  const auth = useAuthStore()
  const source = ref<DashboardSource>('FIELD')
  const data = ref<DashboardSummary>(),
    loading = ref(false),
    error = ref('')
  let generation = 0
  async function reload() {
    const current = ++generation
    data.value = undefined
    error.value = ''
    loading.value = false
    if (!enabled.value) return
    if (!auth.can('dashboard:read')) {
      error.value = '当前账号没有大屏汇总权限，请导入C08权限脚本并重新登录'
      return
    }
    loading.value = true
    try {
      const result = await getDashboardSummary({ ...scope.value }, source.value)
      if (generation === current) data.value = result
    } catch (cause) {
      if (generation === current)
        error.value = cause instanceof Error ? cause.message : '汇总查询失败'
    } finally {
      if (generation === current) loading.value = false
    }
  }
  watch(
    () => [
      scope.value.provinceCode,
      scope.value.cityName,
      scope.value.siteCode,
      enabled.value,
      source.value,
      auth.scopeKey,
      auth.can('dashboard:read'),
    ],
    () => {
      void reload()
    },
    { immediate: true, flush: 'sync' },
  )
  onUnmounted(() => {
    generation++
  })
  return { data, source, loading, error, reload }
}
