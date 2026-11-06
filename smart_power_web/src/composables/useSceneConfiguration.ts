/** 场景配置状态：身份/站点切换使旧请求失效，写入串行；对象与测点保存分开，显式发布。 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { allAssetSites, listAssetDevices } from '@/services/assetsService'
import { getPoints } from '@/services/monitoringService'
import * as api from '@/services/twinService'
import type { AssetDevice, AssetSite } from '@/types/assets'
import type {
  BindingInput,
  ObjectInput,
  SceneSummary,
  SceneTemplate,
  TwinSceneData,
} from '@/types/twin'
import type { PointDefinition } from '@/types/monitoring'

/** initialSite为台账页传来的可选数据库ID，仅在授权列表中匹配；返回页面状态与显式操作方法。 */
export function useSceneConfiguration(initialSite = '') {
  const auth = useAuthStore()
  const sites = ref<AssetSite[]>([]),
    templates = ref<SceneTemplate[]>([]),
    siteId = ref('')
  const versions = ref<SceneSummary[]>([]),
    devices = ref<AssetDevice[]>([])
  const scene = ref<TwinSceneData>(),
    templateId = ref(''),
    selectedVersion = ref('')
  const objectRows = ref<ObjectInput[]>([]),
    bindingRows = ref<BindingInput[]>([])
  const points = ref<Record<string, PointDefinition[]>>({}),
    keys = ref<string[]>([])
  const busy = ref(false),
    error = ref(''),
    message = ref(''),
    warning = ref('')
  const objectsDirty = ref(false),
    bindingsDirty = ref(false)
  const newKey = ref(''),
    newObjectId = ref('')
  let generation = 0,
    alive = true
  const site = computed(() => sites.value.find((s) => s.id === siteId.value))
  const availableTemplates = computed(() =>
    templates.value.filter(
      (t) =>
        t.status === 'PUBLISHED' &&
        t.modelUrl &&
        t.siteType === site.value?.siteType &&
        t.scaleLevel === site.value?.scaleLevel,
    ),
  )
  const writable = computed(() => auth.can('twin:publish') && scene.value?.status === 'DRAFT')
  const dirty = computed(() => objectsDirty.value || bindingsDirty.value)
  const valid = (g: number) => alive && generation === g

  /** 清除当前站点的全部编辑状态；不把旧版本对象ID带入新站点请求。 */
  function clearScene() {
    scene.value = undefined
    objectRows.value = []
    bindingRows.value = []
    points.value = {}
    keys.value = []
    objectsDirty.value = false
    bindingsDirty.value = false
    selectedVersion.value = ''
    newKey.value = ''
    newObjectId.value = ''
    warning.value = ''
  }
  /** task接收本次上下文序号；异常保留本地修改，只有同一上下文才更新错误/忙碌状态。 */
  async function act(task: (g: number) => Promise<void>) {
    if (busy.value) return
    const g = generation
    busy.value = true
    error.value = ''
    message.value = ''
    try {
      await task(g)
    } catch (cause) {
      if (valid(g)) error.value = cause instanceof Error ? cause.message : '场景操作失败'
    } finally {
      if (valid(g)) busy.value = false
    }
  }
  /** 安装服务端版本；测点目录失败时保留场景供检查，但明确阻止把失败误当空目录。 */
  async function install(value: TwinSceneData, g: number) {
    if (!valid(g)) return
    if (value.siteId !== siteId.value) throw new Error('响应场景不属于当前站点')
    const ids = [...new Set(value.objects.flatMap((o) => (o.deviceId ? [o.deviceId] : [])))]
    let definitions: Record<string, PointDefinition[]> = {},
      objectKeys: string[] = [],
      notice = ''
    try {
      objectKeys = (await api.getTemplateObjects(value.templateId)).data.objectKeys
      if (!valid(g)) return
      if (auth.can('monitor:read'))
        definitions = Object.fromEntries(
          await Promise.all(ids.map(async (id) => [id, (await getPoints(id)).data])),
        )
      else notice = '没有monitor:read权限，不能选择测点；请管理员授权。'
    } catch (cause) {
      notice = `目录读取失败，可重载版本重试：${cause instanceof Error ? cause.message : '请求失败'}`
    }
    if (!valid(g)) return
    scene.value = value
    selectedVersion.value = value.id
    keys.value = objectKeys
    objectRows.value = value.objects.map((o) => ({
      objectKey: o.objectKey,
      name: o.name,
      deviceId: o.deviceId,
    }))
    bindingRows.value = value.bindings.map((b) => ({
      objectId: b.objectId,
      pointId: b.pointId,
      propertyCode: b.propertyCode,
      mappingConfig: b.mappingConfig,
    }))
    points.value = definitions
    warning.value = notice
    objectsDirty.value = false
    bindingsDirty.value = false
    newKey.value = ''
    newObjectId.value = ''
  }
  /** 设备目录取全分页；只有device:read时才请求，不能用别站台账填选项。 */
  async function siteDevices(id: string) {
    if (!auth.can('device:read')) return []
    const rows: AssetDevice[] = []
    for (let page = 1; page <= 10000; page++) {
      const response = await listAssetDevices(id, page)
      rows.push(...response.data)
      if (!response.meta.hasNext) return rows
    }
    throw new Error('设备目录超过分页上限')
  }
  /** 切站后重读版本与设备；旧站请求即使稍后成功也不会覆盖新站。 */
  async function loadSite() {
    generation++
    busy.value = false
    clearScene()
    devices.value = []
    versions.value = []
    templateId.value = ''
    error.value = ''
    message.value = ''
    if (!siteId.value) return
    const id = siteId.value
    await act(async (g) => {
      const [list, assets] = await Promise.all([api.getSceneVersions(id), siteDevices(id)])
      if (!valid(g)) return
      if (assets.some((d) => d.siteId !== id)) throw new Error('设备目录归属不一致')
      versions.value = list
      devices.value = assets
      templateId.value = availableTemplates.value[0]?.id ?? ''
      const current = list.find((s) => s.status === 'PUBLISHED') ?? list[0]
      if (current) await install((await api.getScene(current.id)).data, g)
    })
  }
  /** 身份或权限变化时同步清除编辑缓存，再取当前账号的完整授权目录。 */
  async function initialize() {
    generation++
    busy.value = false
    clearScene()
    sites.value = []
    templates.value = []
    siteId.value = ''
    versions.value = []
    devices.value = []
    error.value = ''
    message.value = ''
    if (!auth.can('twin:read') || !auth.can('site:read')) return
    let chosen = ''
    await act(async (g) => {
      const [list, catalog] = await Promise.all([allAssetSites(), api.getSceneTemplates()])
      if (!valid(g)) return
      sites.value = list
      templates.value = catalog.data
      chosen = list.some((s) => s.id === initialSite) ? initialSite : (list[0]?.id ?? '')
    })
    if (alive && chosen) {
      siteId.value = chosen
      await loadSite()
    }
  }
  /** 切换版本不隐式丢弃草稿修改；读取失败时选择器恢复为实际显示的版本。 */
  async function selectVersion() {
    if (dirty.value) {
      selectedVersion.value = scene.value?.id ?? ''
      error.value = '请先保存修改或点击放弃并重载。'
      return
    }
    const id = selectedVersion.value
    if (id)
      await act(async (g) => {
        try {
          await install((await api.getScene(id)).data, g)
        } finally {
          if (valid(g)) selectedVersion.value = scene.value?.id ?? ''
        }
      })
  }
  /** 用户显式重载可放弃未保存输入；不会重新发布或复制场景。 */
  async function refresh() {
    await act(async (g) => {
      const list = await api.getSceneVersions(siteId.value)
      if (!valid(g)) return
      versions.value = list
      const id = scene.value?.id ?? list[0]?.id
      if (id) await install((await api.getScene(id)).data, g)
    })
  }
  /** 从匹配模板创建独立草稿；推荐键初始不绑定设备，创建与发布分离。 */
  async function create() {
    if (
      !auth.can('twin:publish') ||
      site.value?.assetStatus !== 'ACTIVE' ||
      dirty.value ||
      !availableTemplates.value.some((t) => t.id === templateId.value)
    )
      return
    await act(async (g) => {
      const catalog = (await api.getTemplateObjects(templateId.value)).data
      if (!valid(g)) return
      if (catalog.objectKeys.length > 200)
        throw new Error('模板推荐对象超过200个，请先精简模板对象清单后重试。')
      const value = (
        await api.createScene(
          siteId.value,
          templateId.value,
          catalog.objectKeys.map((key) => ({ objectKey: key, name: key, deviceId: null })),
        )
      ).data
      if (!valid(g)) return
      await install(value, g)
      if (!valid(g)) return
      const list = await api.getSceneVersions(siteId.value)
      if (valid(g)) {
        versions.value = list
        message.value = '草稿已创建，请关联本站设备，随后配置测点。'
      }
    })
  }
  /** 复制的是服务器当前发布版本，保持旧克隆接口含义，不复制任意历史版本。 */
  async function clone() {
    if (
      !auth.can('twin:publish') ||
      dirty.value ||
      !versions.value.some((s) => s.status === 'PUBLISHED')
    )
      return
    await act(async (g) => {
      const value = (await api.cloneScene(siteId.value)).data
      if (!valid(g)) return
      await install(value, g)
      if (!valid(g)) return
      const list = await api.getSceneVersions(siteId.value)
      if (valid(g)) versions.value = list
    })
  }
  /** 保存对象白名单；空设备转null，绑定已有未保存修改时禁止覆盖该部分编辑。 */
  async function saveObjects() {
    if (!writable.value || !scene.value || bindingsDirty.value) return
    await act(async (g) => {
      const value = (
        await api.saveObjects(
          scene.value!.id,
          objectRows.value.map((o) => ({ ...o, deviceId: o.deviceId || null })),
        )
      ).data
      await install(value, g)
      if (valid(g)) message.value = '对象已保存，当前发布版本保持不变。'
    })
  }
  /** 保存绑定全集；对象必须先保存取得稳定数据库ID，错误时保留本地输入。 */
  async function saveBindings() {
    if (!writable.value || !scene.value || objectsDirty.value) return
    await act(async (g) => {
      await install((await api.saveBindings(scene.value!.id, bindingRows.value)).data, g)
      if (valid(g)) message.value = '绑定已保存，请检查后显式发布。'
    })
  }
  /** 仅发布已保存的草稿，发布原子校验由后端执行；成功后重新读取版本状态。 */
  async function publish() {
    if (!writable.value || !scene.value || dirty.value) return
    await act(async (g) => {
      await install((await api.publishScene(scene.value!.id)).data, g)
      if (!valid(g)) return
      const list = await api.getSceneVersions(siteId.value)
      if (valid(g)) {
        versions.value = list
        message.value = '已发布。重新进入站点三维页即可读取本版本。'
      }
    })
  }
  /** objectId为场景对象ID；只返回该对象已保存关联设备的测点，绝不混入别的设备。 */
  const pointsFor = (objectId: string) =>
    points.value[scene.value?.objects.find((o) => o.id === objectId)?.deviceId ?? ''] ?? []
  function addObject() {
    if (
      !writable.value ||
      busy.value ||
      bindingsDirty.value ||
      !keys.value.includes(newKey.value) ||
      objectRows.value.some((o) => o.objectKey === newKey.value)
    )
      return
    objectRows.value.push({ objectKey: newKey.value, name: newKey.value, deviceId: null })
    objectsDirty.value = true
  }
  function removeObject(index: number) {
    if (!writable.value || busy.value || bindingsDirty.value) return
    objectRows.value.splice(index, 1)
    objectsDirty.value = true
  }
  function addBinding() {
    if (!writable.value || busy.value || objectsDirty.value) return
    const point = pointsFor(newObjectId.value).find(
      (p) =>
        p.enabled &&
        !bindingRows.value.some(
          (b) => b.objectId === newObjectId.value && b.propertyCode === p.code,
        ),
    )
    if (!point) {
      error.value = '该对象无可用测点；请先配置本站设备的测点，或检查权限/目录读取提示。'
      return
    }
    bindingRows.value.push({
      objectId: newObjectId.value,
      pointId: point.id,
      propertyCode: point.code,
      mappingConfig: null,
    })
    bindingsDirty.value = true
  }
  function removeBinding(index: number) {
    if (!writable.value || busy.value || objectsDirty.value) return
    bindingRows.value.splice(index, 1)
    bindingsDirty.value = true
  }
  const stop = watch(
    () => [auth.scopeKey, auth.user?.permissions.join(',') ?? ''],
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
    versions,
    selectedVersion,
    availableTemplates,
    templateId,
    scene,
    devices,
    objectRows,
    bindingRows,
    keys,
    pointsFor,
    newKey,
    newObjectId,
    busy,
    error,
    message,
    warning,
    objectsDirty,
    bindingsDirty,
    dirty,
    writable,
    loadSite,
    selectVersion,
    refresh,
    create,
    clone,
    saveObjects,
    saveBindings,
    publish,
    addObject,
    removeObject,
    addBinding,
    removeBinding,
  }
}
