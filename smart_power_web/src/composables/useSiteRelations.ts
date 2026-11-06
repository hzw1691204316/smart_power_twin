/** 站内关系状态：站点范围、区域与路线编辑、错误重试、身份/选择/保存迟到响应隔离。 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSitesStore } from '@/stores/sites'
import * as api from '@/services/assetsService'
import type { AssetArea, AssetBody, AssetSite, HighwayOption } from '@/types/assets'
import type { RelationKind, RelationRecord } from '@/utils/relationForms'

/** initialSite仅在授权站点目录中解析，台账页跳转不绕过后端站点范围。 */
export function useSiteRelations(initialSite = '') {
  const auth = useAuthStore(),
    map = useSitesStore()
  const sites = ref<AssetSite[]>([]),
    siteId = ref(''),
    site = ref<AssetSite>(),
    areas = ref<AssetArea[]>([]),
    highways = ref<HighwayOption[]>([])
  const editor = ref<{ kind: RelationKind; record?: RelationRecord }>(),
    busy = ref(false),
    loaded = ref(false),
    error = ref(''),
    message = ref('')
  const editable = computed(() => auth.can('site:read') && auth.can('asset:manage'))
  let generation = 0,
    alive = true
  const valid = (g: number) => alive && generation === g
  function clear() {
    site.value = undefined
    areas.value = []
    editor.value = undefined
    loaded.value = false
    error.value = ''
    message.value = ''
  }
  /** task只在同一上下文更新错误/忙碌；服务端已接收的事务不由前端取消。 */
  async function run(g: number, task: () => Promise<void>) {
    busy.value = true
    error.value = ''
    message.value = ''
    try {
      await task()
    } catch (cause) {
      if (valid(g)) error.value = cause instanceof Error ? cause.message : '站内关系操作失败'
    } finally {
      if (valid(g)) busy.value = false
    }
  }
  /** 两份目录都成功并复核归属后才安装，失败不会沿用另一站点的区域或主关联。 */
  async function read(g: number) {
    const id = siteId.value
    const [detail, list] = await Promise.all([api.getAssetSite(id), api.listAssetAreas(id)])
    if (!valid(g)) return
    if (
      detail.data.id !== id ||
      detail.data.routes.some((r) => r.siteId !== id) ||
      list.data.some((a) => a.siteId !== id)
    )
      throw new Error('站点或区域响应归属不一致')
    site.value = detail.data
    areas.value = list.data
    loaded.value = true
  }
  /** 换账号/授权/编辑权立即清理缓存；共享路线只查询，不在本站权限下修改全局字典。 */
  async function initialize() {
    const preferred = siteId.value || initialSite
    const g = ++generation
    clear()
    sites.value = []
    highways.value = []
    siteId.value = ''
    busy.value = false
    if (!auth.can('site:read')) return
    await run(g, async () => {
      const [list, routes] = await Promise.all([api.allAssetSites(), api.assetHighways()])
      if (!valid(g)) return
      sites.value = list
      highways.value = routes
      siteId.value = list.some((s) => s.id === preferred) ? preferred : (list[0]?.id ?? '')
      if (siteId.value) await read(g)
    })
  }
  /** 切站或显式重读都会清空编辑器；页面编辑期间禁用该操作，离开页面不隐式保存。 */
  async function loadSite() {
    const g = ++generation
    clear()
    busy.value = false
    if (!auth.can('site:read') || !sites.value.some((s) => s.id === siteId.value)) return
    await run(g, async () => read(g))
  }
  /** 编辑前读最新详情；新建只有有效站点可用，保存时服务器还会再次鉴权和验证状态。 */
  async function open(kind: RelationKind, record?: RelationRecord) {
    if (!editable.value || busy.value || !loaded.value || !site.value) return
    if (!record && site.value.assetStatus !== 'ACTIVE') return
    if (record && record.siteId !== site.value.id) return
    editor.value = undefined
    if (!record) {
      error.value = ''
      message.value = ''
      editor.value = { kind }
      return
    }
    const g = generation
    await run(g, async () => {
      await read(g)
      if (!valid(g)) return
      const fresh = (kind === 'area' ? areas.value : site.value!.routes).find(
        (row) => row.id === record.id,
      )
      if (!fresh) throw new Error('记录已不存在，请重读本站关系')
      editor.value = { kind, record: fresh }
    })
  }
  /** 每次只保存一条记录；主关联互斥和区域环由后端原子校验，不在前端假装保存成功。 */
  async function save(body: AssetBody) {
    if (!editable.value || busy.value || !editor.value || !site.value) return
    const g = generation,
      editing = editor.value,
      id = site.value.id
    await run(g, async () => {
      const response =
        editing.kind === 'area'
          ? await api.saveArea(id, editing.record?.id, body)
          : await api.saveRouteLink(id, editing.record?.id, body)
      if (!valid(g)) return
      if (response.data.siteId !== id) throw new Error('保存响应归属异常，请重读核对，勿重复新增')
      editor.value = undefined
      loaded.value = false
      map.reset()
      message.value = '已保存本站关系；区域、设备和其他路线资料均按ID保留。'
      try {
        await read(g)
      } catch {
        if (valid(g)) error.value = '保存已成功，但关系刷新失败，请重读，勿重复新增。'
      }
    })
  }
  function cancel() {
    if (!busy.value) editor.value = undefined
  }
  const stop = watch(
    () => [auth.scopeKey, auth.can('site:read'), auth.can('asset:manage')],
    () => {
      void initialize()
    },
    { immediate: true, flush: 'sync' },
  )
  onUnmounted(() => {
    alive = false
    generation++
    stop()
  })
  return {
    sites,
    siteId,
    site,
    areas,
    highways,
    editor,
    editable,
    busy,
    loaded,
    error,
    message,
    initialize,
    loadSite,
    open,
    save,
    cancel,
  }
}
