/** 测点管理状态：站点/设备分页、定义读取与新增/编辑；身份或选择变化使旧响应失效。 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { allAssetSites, getAssetDevice, listAssetDevices } from '@/services/assetsService'
import { configurePoint, createPoint, getPoints } from '@/services/monitoringService'
import type { AssetDevice, AssetSite } from '@/types/assets'
import type { ManagedPoint, PointConfigInput, PointCreateInput } from '@/types/monitoring'

/** initialSite/initialDevice是可选数据库ID；仅在授权站点内解析，不能用前端演示路由ID替代。 */
export function usePointMaintenance(initialSite = '', initialDevice = '') {
  const auth = useAuthStore()
  const sites = ref<AssetSite[]>([]),
    siteId = ref(''),
    devices = ref<AssetDevice[]>([])
  const device = ref<AssetDevice>(),
    devicePage = ref(1),
    deviceTotal = ref(0),
    deviceQuery = ref('')
  const points = ref<ManagedPoint[]>([]),
    pointQuery = ref(''),
    pointsLoaded = ref(false)
  const editor = ref<{ record?: ManagedPoint }>(),
    busy = ref(false),
    error = ref(''),
    message = ref('')
  let generation = 0,
    alive = true
  const site = computed(() => sites.value.find((row) => row.id === siteId.value))
  const readable = () =>
    auth.can('site:read') && auth.can('device:read') && auth.can('monitor:read')
  const editable = computed(() => readable() && auth.can('monitor:configure'))
  const visiblePoints = computed(() => {
    const q = pointQuery.value.trim().toLowerCase()
    return points.value.filter(
      (p) => !q || [p.code, p.name, p.unit].some((value) => value.toLowerCase().includes(q)),
    )
  })
  const valid = (g: number) => alive && g === generation

  /** 每次上下文改变先清除旧点表/编辑器；已经发到后端的写入仍可能完成，但结果不串入新选择。 */
  function clearDevice() {
    device.value = undefined
    points.value = []
    pointsLoaded.value = false
    editor.value = undefined
    pointQuery.value = ''
  }
  /** job接收上下文序号；只由同一选择的请求更新消息及忙碌状态，错误保留尚未提交的表单。 */
  async function run(g: number, job: () => Promise<void>) {
    busy.value = true
    error.value = ''
    message.value = ''
    try {
      await job()
    } catch (cause) {
      if (valid(g)) error.value = cause instanceof Error ? cause.message : '测点操作失败'
    } finally {
      if (valid(g)) busy.value = false
    }
  }
  /** 检查定义中的站点与设备身份；响应异常时拒绝安装，防止用错设备目录进行编辑。 */
  function checkPoints(rows: ManagedPoint[], selected: AssetDevice) {
    if (rows.some((p) => p.deviceId !== selected.id || p.siteId !== selected.siteId))
      throw new Error('测点目录归属与当前设备不一致')
    return rows
  }
  async function readPoints(selected: AssetDevice, g: number) {
    const result = await getPoints(selected.id)
    if (valid(g)) {
      points.value = checkPoints(result.data, selected)
      pointsLoaded.value = true
    }
  }
  /** 设备分页只请求本站；指定跳转设备时单独查询其详情，不能因其不在第一页而选错设备。 */
  async function readDevices(g: number, preferredDevice = '') {
    const id = siteId.value
    const list = await listAssetDevices(id, devicePage.value, deviceQuery.value)
    if (!valid(g)) return
    if (list.data.some((row) => row.siteId !== id)) throw new Error('设备目录归属不一致')
    devices.value = list.data
    deviceTotal.value = list.meta.total
    let selected = list.data[0]
    if (preferredDevice) {
      selected = (await getAssetDevice(id, preferredDevice)).data
      if (!valid(g)) return
      if (selected.siteId !== id || selected.id !== preferredDevice)
        throw new Error('设备响应与本站跳转目标不一致')
    }
    device.value = selected
    if (selected) await readPoints(selected, g)
  }
  /** 初始化或换账号时清空所有范围数据；默认第一授权站点，URL选择只在当前授权列表生效。 */
  async function initialize() {
    const g = ++generation
    sites.value = []
    siteId.value = ''
    devices.value = []
    deviceTotal.value = 0
    devicePage.value = 1
    deviceQuery.value = ''
    clearDevice()
    error.value = ''
    message.value = ''
    busy.value = false
    if (!readable()) return
    await run(g, async () => {
      const list = await allAssetSites()
      if (!valid(g)) return
      sites.value = list
      siteId.value = list.some((s) => s.id === initialSite) ? initialSite : (list[0]?.id ?? '')
      if (siteId.value) await readDevices(g, siteId.value === initialSite ? initialDevice : '')
    })
  }
  /** 站点改变时重新分页，设备/测点旧请求立即失效；此操作本身不保存编辑内容。 */
  async function chooseSite() {
    const g = ++generation
    clearDevice()
    devices.value = []
    deviceTotal.value = 0
    devicePage.value = 1
    deviceQuery.value = ''
    busy.value = false
    if (!readable() || !site.value) return
    await run(g, async () => readDevices(g))
  }
  /** 切设备重读定义，不沿用旧设备对象或依赖台账ACTIVE推断在线状态。 */
  async function chooseDevice(selected: AssetDevice) {
    if (!readable() || selected.siteId !== siteId.value) return
    const g = ++generation
    clearDevice()
    device.value = selected
    await run(g, async () => readPoints(selected, g))
  }
  /** 搜索/翻页时清除旧设备和点表，选取新页首台设备；不保存任何业务配置。 */
  async function loadDevices() {
    const g = ++generation
    clearDevice()
    devices.value = []
    deviceTotal.value = 0
    busy.value = false
    if (!readable() || !site.value) return
    await run(g, async () => readDevices(g))
  }
  /** 显式重读当前定义，成功后才能继续编辑；错误时点表保持空态，不伪装成已加载。 */
  async function reloadPoints() {
    if (busy.value || editor.value || !device.value || !readable()) return
    const selected = device.value,
      g = ++generation
    points.value = []
    pointsLoaded.value = false
    await run(g, async () => readPoints(selected, g))
  }
  /** 编辑前重新读取服务器配置，避免直接把旧列表快照保存回去；不存在时提示刷新。 */
  async function open(record?: ManagedPoint) {
    if (!editable.value || busy.value || !device.value || !pointsLoaded.value) return
    const g = generation,
      selected = device.value
    editor.value = undefined
    error.value = ''
    message.value = ''
    if (!record) {
      editor.value = {}
      return
    }
    if (record.deviceId !== selected.id) return
    await run(g, async () => {
      const result = await getPoints(selected.id)
      if (!valid(g)) return
      points.value = checkPoints(result.data, selected)
      pointsLoaded.value = true
      const current = points.value.find((p) => p.id === record.id)
      if (!current) throw new Error('该测点已不存在，请重新查询')
      editor.value = { record: current }
    })
  }
  /** 保存严格区分新增与配置白名单；编辑失败不清空表单，成功后重查定义，不生成采样。 */
  async function save(body: PointCreateInput | PointConfigInput) {
    if (!editable.value || busy.value || !device.value || !editor.value) return
    const g = generation,
      selected = device.value,
      editing = editor.value
    await run(g, async () => {
      const config: PointConfigInput = {
        sampleIntervalMs: body.sampleIntervalMs,
        staleAfterMs: body.staleAfterMs,
        enabled: body.enabled,
        alarmLow: body.alarmLow,
        alarmHigh: body.alarmHigh,
      }
      if (!editing.record && !('code' in body)) throw new Error('新增测点缺少身份字段')
      const response = editing.record
        ? await configurePoint(editing.record.id, config)
        : await createPoint(selected.id, body as PointCreateInput)
      if (!valid(g)) return
      if (response.data.deviceId !== selected.id || response.data.siteId !== selected.siteId)
        throw new Error('保存响应归属异常，请重载后核对，避免重复新增')
      editor.value = undefined
      message.value = `${editing.record ? '已保存配置' : '已新增测点'}：${response.data.name}（ID ${response.data.id}）`
      points.value = []
      pointsLoaded.value = false
      try {
        await readPoints(selected, g)
      } catch {
        if (valid(g)) error.value = '保存已成功，但点表刷新失败；请点击重读测点，不要重复新增。'
      }
    })
  }
  /** 取消仅丢弃本地表单；请求处理中按钮禁用，不尝试撤销已经提交的数据库事务。 */
  function cancel() {
    if (!busy.value) editor.value = undefined
  }
  const stop = watch(
    () => [
      auth.scopeKey,
      auth.can('site:read'),
      auth.can('device:read'),
      auth.can('monitor:read'),
      auth.can('monitor:configure'),
    ],
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
    devices,
    device,
    devicePage,
    deviceTotal,
    deviceQuery,
    points,
    pointsLoaded,
    pointQuery,
    visiblePoints,
    editor,
    editable,
    busy,
    error,
    message,
    initialize,
    chooseSite,
    chooseDevice,
    loadDevices,
    reloadPoints,
    open,
    save,
    cancel,
  }
}
