/** 台账回归：真实状态逻辑的权限/范围/迟到响应，表单身份白名单、空值与地图适配。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, createSSRApp, h, nextTick, reactive } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { assetFields, assetForm, assetPayload } from '../src/utils/assetForms.ts'
import { assetSiteToMap } from '../src/utils/assetSiteAdapter.ts'
const fixture = {
  id: '99',
  code: 'NEW',
  name: '新站点',
  siteType: 'SERVICE',
  scaleLevel: 'L',
  provinceCode: '410000',
  cityName: '郑州市',
  longitude: 113.55,
  latitude: 34.84,
  coordinateSystem: 'WGS84',
  locationSource: '测试坐标',
  complexCode: null,
  isDemo: true,
  assetStatus: 'ACTIVE',
  routes: [],
}
const mapped = assetSiteToMap(fixture)
assert.equal(mapped.id, 'db-site-99')
assert.equal(mapped.dataPending, true)
assert.equal(mapped.devices.length, 0)
assert.equal(mapped.city, '郑州')
assert.equal(assetSiteToMap({ ...fixture, longitude: null }), undefined)
assert.equal(assetSiteToMap({ ...fixture, coordinateSystem: 'GCJ02' }), undefined)
assert.equal(assetSiteToMap({ ...fixture, longitude: 999 }), undefined)
assert.ok(!assetFields('site', false).some((f) => ['code', 'siteType', 'isDemo'].includes(f.key)))
assert.ok(
  !assetFields('device', false).some((f) =>
    ['code', 'deviceType', 'systemType', 'isDemo', 'siteId'].includes(f.key),
  ),
)
const form = assetForm('device')
form.ratedPowerKw = '0'
form.ratedEnergyKwh = ''
form.isDemo = 'true'
form.name = ' 柜体 '
form.code = 'TEST'
form.deviceType = 'ESS'
form.forbidden = '1'
const body = assetPayload('device', true, form)
assert.equal(body.ratedPowerKw, '0')
assert.equal(body.ratedEnergyKwh, null)
assert.equal(body.isDemo, true)
assert.equal(body.name, '柜体')
assert.ok(!('forbidden' in body))
const pending = []
const deferred = (method, args) =>
  new Promise((resolve, reject) => pending.push({ method, args, resolve, reject }))
const auth = reactive({
  user: { id: '1', siteIds: ['1', '2'] },
  scopeKey: 'first',
  permissions: ['site:read', 'device:read', 'site:create', 'asset:manage'],
  can: (code) => auth.permissions.includes(code),
  refreshIdentity: async () => {},
})
let mapResets = 0
globalThis.__assetAuth = auth
globalThis.__assetMap = { reset: () => mapResets++ }
const methods = [
  'listAssetSites',
  'listAssetDevices',
  'getAssetSite',
  'getAssetDevice',
  'listAssetAreas',
  'assetHighways',
  'saveAssetSite',
  'saveAssetDevice',
]
globalThis.__assetApi = Object.fromEntries(
  methods.map((name) => [name, (...args) => deferred(name, args)]),
)
const url = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const authUrl = url('export const useAuthStore=()=>globalThis.__assetAuth'),
  mapUrl = url('export const useSitesStore=()=>globalThis.__assetMap'),
  apiUrl = url(
    methods
      .map((name) => `export const ${name}=(...args)=>globalThis.__assetApi.${name}(...args)`)
      .join('\n'),
  )
function compile(source) {
  return ts
    .transpileModule(source, {
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    })
    .outputText.replace(/from (['"])vue\1/g, `from ${JSON.stringify(import.meta.resolve('vue'))}`)
    .replace(/from (['"])@\/stores\/auth\1/g, `from ${JSON.stringify(authUrl)}`)
    .replace(/from (['"])@\/stores\/sites\1/g, `from ${JSON.stringify(mapUrl)}`)
    .replace(/from (['"])@\/services\/assetsService\1/g, `from ${JSON.stringify(apiUrl)}`)
}
const { useAssetMaintenance } = await import(
  url(
    compile(
      readFileSync(new URL('../src/composables/useAssetMaintenance.ts', import.meta.url), 'utf8'),
    ),
  )
)
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
let state
const app = renderer.createApp({
  setup() {
    state = useAssetMaintenance()
    return () => h('div')
  },
})
const flush = async () => {
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
const last = (method) => pending.filter((p) => p.method === method).at(-1)
app.mount({})
try {
  const old = last('listAssetSites')
  auth.scopeKey = 'second'
  old.resolve({ data: [{ ...fixture, name: '旧账号' }], meta: { total: 1 } })
  await flush()
  assert.equal(state.sites.value.length, 0)
  last('listAssetSites').resolve({ data: [fixture], meta: { total: 1 } })
  await flush()
  assert.equal(state.sites.value[0].name, '新站点')
  const first = state.chooseSite({ ...fixture, id: '1' })
  const oldDetail = last('getAssetSite'),
    oldAreas = last('listAssetAreas')
  const second = state.chooseSite({ ...fixture, id: '2' })
  oldDetail.resolve({ data: { ...fixture, id: '1' } })
  oldAreas.resolve({ data: [] })
  await flush()
  assert.equal(state.site.value, undefined)
  last('getAssetSite').resolve({ data: { ...fixture, id: '2' } })
  last('listAssetAreas').resolve({ data: [] })
  await flush()
  last('listAssetDevices').resolve({ data: [], meta: { total: 0 } })
  await Promise.all([first, second])
  assert.equal(state.site.value.id, '2')
  await state.open('device')
  assert.equal(state.editor.value.kind, 'device')
  const saving = state.save(body)
  const oldSave = last('saveAssetDevice')
  auth.scopeKey = 'third'
  oldSave.resolve({ data: { id: '44', name: '旧设备' } })
  await saving
  assert.equal(state.message.value, '')
  assert.equal(mapResets, 0)
  auth.permissions = ['site:read', 'device:read']
  await state.open('site')
  assert.equal(state.editor.value, undefined)
  await state.open('device')
  assert.equal(state.editor.value, undefined)
  auth.permissions = ['site:read', 'device:read', 'asset:manage']
  const loading = state.open('site', fixture)
  const detail = last('getAssetSite')
  auth.permissions = ['site:read']
  detail.resolve({ data: fixture })
  await loading
  assert.equal(state.editor.value, undefined)
  assert.equal(state.editLoading.value, false)
  // 新增成功刷新身份导致scopeKey变化，仍应在新范围内重读并选中本站，不残留busy。
  auth.permissions = ['site:read', 'device:read', 'site:create', 'asset:manage']
  auth.refreshIdentity = async () => {
    auth.user.siteIds = ['1', '2', '99']
    auth.scopeKey = 'created-scope'
  }
  await state.open('site')
  const createdTask = state.save({ code: 'NEW', name: '新站点' })
  last('saveAssetSite').resolve({ data: fixture })
  await flush()
  last('listAssetSites').resolve({ data: [fixture], meta: { total: 1 } })
  await flush()
  last('getAssetSite').resolve({ data: fixture })
  last('listAssetAreas').resolve({ data: [] })
  await flush()
  last('listAssetDevices').resolve({ data: [], meta: { total: 0 } })
  await createdTask
  assert.equal(state.site.value.id, '99')
  assert.equal(state.busy.value, false)
  assert.equal(mapResets, 1)
  assert.ok(state.message.value.includes('已新增并授权'))
} finally {
  app.unmount()
}
const formModule = url(
  compile(readFileSync(new URL('../src/utils/assetForms.ts', import.meta.url), 'utf8')),
)
const { descriptor } = parse(
  readFileSync(new URL('../src/components/assets/AssetForm.vue', import.meta.url), 'utf8'),
)
const script = compileScript(descriptor, { id: 'asset-form-test', inlineTemplate: true })
const Form = (
  await import(
    url(
      compile(script.content).replace(
        /from (['"])@\/utils\/assetForms\1/g,
        `from ${JSON.stringify(formModule)}`,
      ),
    )
  )
).default
const markup = await renderToString(
  createSSRApp(Form, { kind: 'site', record: fixture, busy: false, areas: [], highways: [] }),
)
assert.ok(markup.includes('编码、类型、来源与归属站点在创建后固定'))
assert.ok(!markup.includes('业务编码（创建后固定）'))
assert.ok(markup.includes('保存修改'))
const created = await renderToString(
  createSSRApp(Form, { kind: 'device', busy: true, areas: [], highways: [] }),
)
assert.ok(created.includes('额定储能电量 kWh') && created.includes('正在保存'))
console.log(
  'Passed: asset form whitelist/empty/zero/source, new-site coordinate adapter, account/scope/device/edit/save race isolation, viewer read-only, real form SFC rendering.',
)
