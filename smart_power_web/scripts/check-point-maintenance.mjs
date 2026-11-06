/** 测点管理回归：纯表单边界、实际composable异步流程、HTTP协议与编译后的真实Vue分支。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, createSSRApp, h, nextTick, reactive, ref } from 'vue'
import { renderToString } from '@vue/server-renderer'
import {
  pointForm,
  pointConfigPayload,
  pointCreatePayload,
  pointPresets,
} from '../src/utils/pointForms.ts'

const site = { id: '1', name: '测试服务区', siteType: 'SERVICE', scaleLevel: 'M', isDemo: true }
const device = {
  id: '51',
  siteId: '1',
  code: 'ESS_02',
  name: '储能柜02',
  systemType: 'ESS',
  assetStatus: 'ACTIVE',
  isDemo: true,
}
const point = {
  id: '501',
  siteId: '1',
  deviceId: '51',
  code: 'active_power',
  name: '有功功率',
  unit: 'kW',
  valueType: 'NUMERIC',
  aggregationType: 'INSTANT',
  sampleIntervalMs: 5000,
  staleAfterMs: 15000,
  enabled: false,
  alarmLow: -10,
  alarmHigh: 0,
  directionConvention: '正放电、负充电',
}
const form = pointForm(point)
assert.equal(form.alarmHigh, '0')
assert.equal(form.enabled, false)
assert.deepEqual(pointConfigPayload(form), {
  sampleIntervalMs: 5000,
  staleAfterMs: 15000,
  enabled: false,
  alarmLow: -10,
  alarmHigh: 0,
})
form.alarmLow = ''
form.alarmHigh = '0'
assert.equal(pointConfigPayload(form).alarmLow, null)
assert.ok(!('code' in pointConfigPayload(form)) && !('unit' in pointConfigPayload(form)))
for (const changes of [
  { sampleIntervalMs: '' },
  { sampleIntervalMs: '99' },
  { sampleIntervalMs: '101.1' },
  { sampleIntervalMs: '3600001' },
  { staleAfterMs: '86400001' },
  { staleAfterMs: '100' },
  { alarmLow: 'NaN' },
  { alarmHigh: 'Infinity' },
  { alarmLow: '0', alarmHigh: '0' },
])
  assert.throws(() => pointConfigPayload({ ...pointForm(point), ...changes }))
for (const preset of pointPresets) {
  const created = pointCreatePayload({ ...pointForm(), ...preset })
  assert.equal(created.code, preset.code)
  assert.equal(created.alarmHigh, null)
}
assert.throws(() =>
  pointCreatePayload({ ...pointForm(), code: 'BAD Code', name: '名称', unit: 'kW' }),
)
assert.throws(() =>
  pointCreatePayload({
    ...pointForm(),
    code: 'online',
    name: '状态',
    unit: 'BOOL',
    valueType: 'BOOLEAN',
  }),
)
assert.throws(() => pointConfigPayload({ ...pointForm(point), valueType: 'TEXT' }))

const pending = []
const methods = [
  'allAssetSites',
  'listAssetDevices',
  'getAssetDevice',
  'getPoints',
  'createPoint',
  'configurePoint',
]
const auth = reactive({
  scopeKey: 'first',
  permissions: ['site:read', 'device:read', 'monitor:read', 'monitor:configure', 'twin:read'],
  can: (code) => auth.permissions.includes(code),
})
globalThis.__pointAuth = auth
globalThis.__pointApi = Object.fromEntries(
  methods.map((name) => [
    name,
    (...args) => new Promise((resolve, reject) => pending.push({ name, args, resolve, reject })),
  ]),
)
const url = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const authUrl = url('export const useAuthStore=()=>globalThis.__pointAuth')
const apiUrl = url(
  methods
    .map((name) => `export const ${name}=(...args)=>globalThis.__pointApi.${name}(...args)`)
    .join('\n'),
)
function compile(source) {
  return ts
    .transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    })
    .outputText.replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
    .replace(/from (['"])@\/stores\/auth\1/g, `from ${JSON.stringify(authUrl)}`)
    .replace(
      /from (['"])@\/services\/(assetsService|monitoringService)\1/g,
      `from ${JSON.stringify(apiUrl)}`,
    )
}
const last = (name) => {
  const request = pending.filter((p) => p.name === name).at(-1)
  assert.ok(request, name)
  return request
}
const flush = async () => {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
const renderer = createRenderer({
  patchProp() {},
  insert() {},
  remove() {},
  createElement: () => ({}),
  createText: () => ({}),
  createComment: () => ({}),
  setText() {},
  setElementText() {},
  parentNode: () => null,
  nextSibling: () => null,
})
const { usePointMaintenance } = await import(
  url(
    compile(
      readFileSync(new URL('../src/composables/usePointMaintenance.ts', import.meta.url), 'utf8'),
    ),
  )
)
let state
const app = renderer.createApp({
  setup() {
    state = usePointMaintenance('1', '51')
    return () => h('div')
  },
})
async function initialize() {
  last('allAssetSites').resolve([site, { ...site, id: '2' }])
  await flush()
  last('listAssetDevices').resolve({ data: [{ ...device, id: '50' }], meta: { total: 41 } })
  await flush()
  last('getAssetDevice').resolve({ data: device })
  await flush()
  last('getPoints').resolve({ data: [point] })
  await flush()
}
app.mount({})
try {
  const old = last('allAssetSites')
  auth.scopeKey = 'second'
  old.resolve([{ ...site, name: '旧账号' }])
  await flush()
  assert.equal(state.sites.value.length, 0)
  await initialize()
  assert.equal(state.device.value.id, '51') // 跳转目标不在设备第一页仍准确选中。
  assert.deepEqual(last('getAssetDevice').args, ['1', '51'])
  state.pointQuery.value = 'kw'
  assert.equal(state.visiblePoints.value.length, 1)
  state.pointQuery.value = '不存在'
  assert.equal(state.visiblePoints.value.length, 0)
  state.pointQuery.value = ''
  // 打开编辑前重新读取最新配置；PUT白名单不携带身份/归属字段。
  const opening = state.open(point)
  last('getPoints').resolve({ data: [{ ...point, alarmLow: -20 }] })
  await opening
  assert.equal(state.editor.value.record.alarmLow, -20)
  const editBody = {
    ...pointConfigPayload(pointForm(point)),
    code: 'FORGED',
    unit: 'fake',
    deviceId: '99',
  }
  const saving = state.save(editBody)
  assert.deepEqual(
    Object.keys(last('configurePoint').args[1]).sort(),
    ['sampleIntervalMs', 'staleAfterMs', 'enabled', 'alarmLow', 'alarmHigh'].sort(),
  )
  last('configurePoint').reject(new Error('数据库只读'))
  await saving
  assert.ok(state.editor.value)
  assert.match(state.error.value, /只读/)
  state.cancel()
  await state.open()
  const createBody = pointCreatePayload({ ...pointForm(), ...pointPresets[2] })
  const creation = state.save(createBody)
  assert.equal(last('createPoint').args[0], '51')
  const created = { ...point, ...createBody, id: '502' }
  last('createPoint').resolve({ data: created })
  await flush()
  last('getPoints').reject(new Error('离线'))
  await creation
  assert.equal(state.editor.value, undefined)
  assert.match(state.message.value, /已新增/)
  assert.match(state.error.value, /保存已成功/)
  const retry = state.reloadPoints()
  last('getPoints').resolve({ data: [point, created] })
  await retry
  assert.equal(state.points.value.length, 2)
  // 同站快速切设备，旧读数/定义迟到也不能覆盖新设备。
  const oldSelection = state.chooseDevice(device),
    oldPoints = last('getPoints')
  const nextDevice = { ...device, id: '52', name: '其他设备' }
  const nextSelection = state.chooseDevice(nextDevice)
  last('getPoints').resolve({ data: [{ ...point, deviceId: '52', id: '503' }] })
  await nextSelection
  oldPoints.resolve({ data: [point] })
  await oldSelection
  assert.equal(state.points.value[0].deviceId, '52')
  const wrong = state.reloadPoints()
  last('getPoints').resolve({ data: [point] })
  await wrong
  assert.equal(state.points.value.length, 0)
  assert.match(state.error.value, /归属/)
  // 设备搜索及页码传到真实目录协议，翻页清空旧选中设备。
  state.devicePage.value = 2
  state.deviceQuery.value = '储能'
  const paging = state.loadDevices()
  assert.deepEqual(last('listAssetDevices').args, ['1', 2, '储能'])
  last('listAssetDevices').resolve({ data: [], meta: { total: 41 } })
  await paging
  assert.equal(state.device.value, undefined)
  const select = state.chooseDevice(device)
  last('getPoints').resolve({ data: [point] })
  await select
  await state.open()
  const oldSaveTask = state.save(createBody),
    oldSave = last('createPoint')
  auth.scopeKey = 'third'
  oldSave.resolve({ data: created })
  await oldSaveTask
  assert.equal(state.points.value.length, 0)
  assert.equal(state.editor.value, undefined)
  assert.equal(state.message.value, '')
  await initialize()
  auth.permissions = ['site:read', 'device:read', 'monitor:read']
  await initialize()
  const count = pending.length
  await state.open()
  await state.save(createBody)
  assert.equal(state.editable.value, false)
  assert.equal(state.editor.value, undefined)
  assert.equal(pending.length, count)
  auth.permissions = ['site:read']
  assert.equal(state.points.value.length, 0)
  assert.equal(state.sites.value.length, 0)
  auth.permissions = ['site:read', 'device:read', 'monitor:read']
  await initialize()
  const unmountTask = state.reloadPoints(),
    late = last('getPoints')
  app.unmount()
  late.resolve({ data: [point] })
  await unmountTask
  assert.equal(state.points.value.length, 0)
} finally {
  app.unmount()
}

// 请求适配器实际运行，新增和编辑保持不同URL及方法，不读取令牌或调用真实后端。
const calls = []
globalThis.__pointRequest = async (...args) => {
  calls.push(args)
  return { data: {} }
}
const httpUrl = url('export const request=(...args)=>globalThis.__pointRequest(...args)')
const adapter = ts
  .transpileModule(
    readFileSync(new URL('../src/services/monitoringService.ts', import.meta.url), 'utf8'),
    { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } },
  )
  .outputText.replace(/from (['"]).\/http\1/g, `from ${JSON.stringify(httpUrl)}`)
const api = await import(url(adapter))
await api.createPoint('51', { code: 'temperature' })
await api.configurePoint('501', { enabled: false })
assert.equal(calls[0][0], '/api/v1/devices/51/points')
assert.equal(calls[0][1].method, 'POST')
assert.equal(calls[1][0], '/api/v1/points/501/config')
assert.equal(calls[1][1].body.enabled, false)

// SSR检验真实表单零值/停用/身份只读，以及管理页只读分支；不把它当作浏览器视觉验收。
const formUrl = url(
  compile(readFileSync(new URL('../src/utils/pointForms.ts', import.meta.url), 'utf8')),
)
function sfc(path, replacements = []) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  let code = compile(compileScript(descriptor, { id: path, inlineTemplate: true }).content)
  for (const [pattern, replacement] of replacements)
    code = code.replace(pattern, `from ${JSON.stringify(replacement)}`)
  return import(url(code))
}
const Form = (
  await sfc('../src/components/monitoring/PointForm.vue', [
    [/from (['"])@\/utils\/pointForms\1/g, formUrl],
  ])
).default
const editHtml = await renderToString(createSSRApp(Form, { record: point, busy: false }))
assert.ok(editHtml.includes('value="0"') && editHtml.includes('value="-10"'))
assert.ok(!editHtml.includes('placeholder="例如 active_power"') && editHtml.includes('保存配置'))
assert.ok(!/<input[^>]*type="checkbox"[^>]*checked/.test(editHtml))
const newHtml = await renderToString(createSSRApp(Form, { busy: false }))
assert.ok(newHtml.includes('累计电量 / kWh') && newHtml.includes('设备内测点编码'))
globalThis.__pointRender = Object.fromEntries(
  Object.keys(state).map((k) => [k, typeof state[k] === 'function' ? () => {} : ref(undefined)]),
)
Object.assign(globalThis.__pointRender, {
  sites: ref([site]),
  siteId: ref('1'),
  site: ref(site),
  devices: ref([device]),
  device: ref(device),
  devicePage: ref(1),
  deviceTotal: ref(1),
  points: ref([point]),
  visiblePoints: ref([point]),
  pointQuery: ref(''),
  editable: ref(false),
  busy: ref(false),
})
const routeUrl = url('export const useRoute=()=>({query:{}})'),
  composableUrl = url('export const usePointMaintenance=()=>globalThis.__pointRender')
const View = (
  await sfc('../src/views/PointsView.vue', [
    [/from (['"])vue-router\1/g, routeUrl],
    [/from (['"])@\/composables\/usePointMaintenance\1/g, composableUrl],
    [/from (['"])@\/components\/monitoring\/PointForm.vue\1/g, url('export default {}')],
  ])
).default
const view = createSSRApp(View)
view.component('RouterLink', { template: '<a><slot /></a>' })
const html = await renderToString(view)
assert.ok(html.includes('当前账号只读') && html.includes('-10 / 0') && html.includes('已停用'))
assert.ok(!html.includes('＋ 新增测点') && !html.includes('配置 / 启停'))
delete globalThis.__pointAuth
delete globalThis.__pointApi
delete globalThis.__pointRequest
delete globalThis.__pointRender
console.log(
  'Passed: point form periods/types/threshold null-zero-negative/whitelists, create-edit-error-retry, preferred device outside first page, paging/filter, stale account/device/save/unmount isolation, read-only rights, HTTP contracts and real Vue form/page rendering.',
)
