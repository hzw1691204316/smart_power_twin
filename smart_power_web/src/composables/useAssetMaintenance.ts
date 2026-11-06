/** 台账管理状态：分页/搜索、本站设备、编辑器与保存；换账号/范围或撤权立即清空，迟到响应隔离。 */
import { ref, watch, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useSitesStore } from '@/stores/sites'
import * as api from '@/services/assetsService'
import type { AssetArea, AssetBody, AssetDevice, AssetSite, HighwayOption } from '@/types/assets'
export function useAssetMaintenance() {
  const auth = useAuthStore(),
    mapSites = useSitesStore()
  const sites = ref<AssetSite[]>([]),
    total = ref(0),
    page = ref(1),
    query = ref(''),
    loading = ref(false),
    error = ref(''),
    message = ref('')
  const site = ref<AssetSite>(),
    devices = ref<AssetDevice[]>([]),
    deviceTotal = ref(0),
    devicePage = ref(1),
    deviceQuery = ref(''),
    deviceLoading = ref(false),
    areas = ref<AssetArea[]>([]),
    highways = ref<HighwayOption[]>([])
  const editor = ref<{ kind: 'site' | 'device'; record?: AssetSite | AssetDevice }>(),
    busy = ref(false),
    editLoading = ref(false)
  let context = 0,
    listRun = 0,
    deviceRun = 0,
    editRun = 0
  /** 查询失败清空旧页；接口的范围过滤由后端执行，前端不根据角色推断全库权限。 */
  async function loadSites() {
    const current = ++listRun,
      scope = context
    sites.value = []
    total.value = 0
    error.value = ''
    if (!auth.can('site:read')) return
    loading.value = true
    try {
      const result = await api.listAssetSites(page.value, query.value)
      if (current === listRun && scope === context) {
        sites.value = result.data
        total.value = result.meta.total
      }
    } catch (cause) {
      if (current === listRun && scope === context)
        error.value = cause instanceof Error ? cause.message : '站点查询失败'
    } finally {
      if (current === listRun && scope === context) loading.value = false
    }
  }
  async function loadDevices() {
    const current = ++deviceRun,
      scope = context
    devices.value = []
    deviceTotal.value = 0
    error.value = ''
    if (!site.value || !auth.can('device:read')) return
    const id = site.value.id
    deviceLoading.value = true
    try {
      const result = await api.listAssetDevices(id, devicePage.value, deviceQuery.value)
      if (current === deviceRun && scope === context) {
        devices.value = result.data
        deviceTotal.value = result.meta.total
      }
    } catch (cause) {
      if (current === deviceRun && scope === context)
        error.value = cause instanceof Error ? cause.message : '设备查询失败'
    } finally {
      if (current === deviceRun && scope === context) deviceLoading.value = false
    }
  }
  /** 选择站点后重新查询完整详情与区域，不把上一站的归属选项带入新站。 */
  async function chooseSite(row: AssetSite) {
    const current = ++editRun,
      scope = context
    deviceRun++
    deviceLoading.value = false
    site.value = undefined
    devices.value = []
    deviceTotal.value = 0
    areas.value = []
    editor.value = undefined
    error.value = ''
    devicePage.value = 1
    deviceQuery.value = ''
    editLoading.value = true
    try {
      const [detail, options] = await Promise.all([
        api.getAssetSite(row.id),
        api.listAssetAreas(row.id),
      ])
      if (current !== editRun || scope !== context) return
      site.value = detail.data
      areas.value = options.data
      await loadDevices()
    } catch (cause) {
      if (current === editRun && scope === context)
        error.value = cause instanceof Error ? cause.message : '本站资料查询失败'
    } finally {
      if (current === editRun && scope === context) editLoading.value = false
    }
  }
  /** 开编辑器前重查详情，编码/类型/来源在编辑表单中不提供输入。 */
  async function open(kind: 'site' | 'device', record?: AssetSite | AssetDevice) {
    if (kind === 'site' && !record ? !auth.can('site:create') : !auth.can('asset:manage')) return
    const current = ++editRun,
      scope = context
    editor.value = undefined
    editLoading.value = false
    error.value = ''
    message.value = ''
    if (!record) {
      editor.value = { kind }
      return
    }
    editLoading.value = true
    try {
      const response =
        kind === 'site'
          ? await api.getAssetSite(record.id)
          : await api.getAssetDevice((record as AssetDevice).siteId, record.id)
      if (current === editRun && scope === context) editor.value = { kind, record: response.data }
    } catch (cause) {
      if (current === editRun && scope === context)
        error.value = cause instanceof Error ? cause.message : '详情读取失败'
    } finally {
      if (current === editRun && scope === context) editLoading.value = false
    }
  }
  /** 保存成功再重查；新站仅刷新自身新站授权，不延长令牌期限；失败不乐观修改列表。 */
  async function save(body: AssetBody) {
    const editing = editor.value
    if (!editing || busy.value) return
    const creating = !editing.record
    if (editing.kind === 'site' && creating ? !auth.can('site:create') : !auth.can('asset:manage'))
      return
    const scope = context,
      user = auth.user?.id,
      selectedSite = site.value?.id
    if (editing.kind === 'device' && !selectedSite) return
    let ownerContext = scope
    busy.value = true
    error.value = ''
    message.value = ''
    try {
      const result =
        editing.kind === 'site'
          ? await api.saveAssetSite(editing.record?.id, body)
          : await api.saveAssetDevice(selectedSite!, editing.record?.id, body)
      if (scope !== context) return
      mapSites.reset()
      editor.value = undefined
      message.value = `已保存：${result.data.name}（ID ${result.data.id}）`
      if (editing.kind === 'site' && creating) {
        try {
          await auth.refreshIdentity()
        } catch {
          if (user === auth.user?.id)
            error.value = '新站已保存，请刷新页面重新读取站点授权；不要重复新增'
          return
        }
        if (user !== auth.user?.id || !auth.user?.siteIds.includes(result.data.id)) return
        ownerContext = context
        message.value = `已新增并授权当前账号：${result.data.name}（ID ${result.data.id}）`
      }
      await loadSites()
      if (editing.kind === 'site' && auth.user?.siteIds.includes(result.data.id))
        await chooseSite(result.data as AssetSite)
      else if (editing.kind === 'device' && scope === context) await loadDevices()
    } catch (cause) {
      if (scope === context) error.value = cause instanceof Error ? cause.message : '保存失败'
    } finally {
      if (ownerContext === context) busy.value = false
    }
  }
  function cancel() {
    editRun++
    editor.value = undefined
    editLoading.value = false
  }
  function reset() {
    context++
    listRun++
    deviceRun++
    editRun++
    sites.value = []
    site.value = undefined
    devices.value = []
    areas.value = []
    highways.value = []
    total.value = 0
    deviceTotal.value = 0
    page.value = 1
    devicePage.value = 1
    editor.value = undefined
    loading.value = false
    deviceLoading.value = false
    editLoading.value = false
    busy.value = false
    query.value = ''
    deviceQuery.value = ''
    error.value = ''
    message.value = ''
  }
  watch(
    () => [
      auth.scopeKey,
      auth.can('site:read'),
      auth.can('asset:manage'),
      auth.can('site:create'),
      auth.can('device:read'),
    ],
    () => {
      reset()
      void loadSites()
      const current = context
      if (auth.can('site:read'))
        void api
          .assetHighways()
          .then((rows) => {
            if (current === context) highways.value = rows
          })
          .catch((cause) => {
            if (current === context)
              error.value = cause instanceof Error ? cause.message : '路线读取失败'
          })
    },
    { immediate: true, flush: 'sync' },
  )
  onUnmounted(reset)
  return {
    sites,
    total,
    page,
    query,
    loading,
    error,
    message,
    site,
    devices,
    deviceTotal,
    devicePage,
    deviceQuery,
    deviceLoading,
    editLoading,
    areas,
    highways,
    editor,
    busy,
    loadSites,
    loadDevices,
    chooseSite,
    open,
    save,
    cancel,
  }
}
