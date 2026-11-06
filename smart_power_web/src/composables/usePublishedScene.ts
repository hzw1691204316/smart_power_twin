/** 私有站点场景状态：切站/换账号/撤权后立即清旧模型，迟到响应不覆盖当前场景。公开模板不查私有API。 */
import { onUnmounted, ref, watch, type Ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { getPublishedScene } from '@/services/twinService'
import { sceneModelUrl } from '@/utils/twinPresentation'
import type { TwinSceneData } from '@/types/twin'

export function usePublishedScene(siteCode: Ref<string>, publicPreview: Ref<boolean>) {
  const auth = useAuthStore()
  const scene = ref<TwinSceneData>(),
    loading = ref(false),
    error = ref('')
  let generation = 0
  async function reload() {
    const current = ++generation
    scene.value = undefined
    error.value = ''
    loading.value = false
    if (publicPreview.value || !siteCode.value) return
    if (!auth.can('twin:read')) {
      error.value = '当前账号没有三维场景权限，请导入权限补丁后重新登录'
      return
    }
    loading.value = true
    try {
      const result = await getPublishedScene(siteCode.value)
      sceneModelUrl(result.modelUrl)
      if (current === generation) scene.value = result
    } catch (cause) {
      if (current === generation)
        error.value = cause instanceof Error ? cause.message : '场景读取失败'
    } finally {
      if (current === generation) loading.value = false
    }
  }
  watch(
    () => [siteCode.value, publicPreview.value, auth.scopeKey, auth.can('twin:read')],
    () => {
      void reload()
    },
    { immediate: true, flush: 'sync' },
  )
  onUnmounted(() => {
    generation++
  })
  return { scene, loading, error, reload }
}
