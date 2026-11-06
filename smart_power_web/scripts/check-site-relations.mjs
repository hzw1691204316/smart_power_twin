/** 站内关系回归：表单白名单/父选项、真实状态保存与竞态、HTTP协议及真实Vue只读布局。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, createSSRApp, h, nextTick, reactive, ref } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { areaParents, relationForm, relationPayload } from '../src/utils/relationForms.ts'
const area = {
  id: '11',
  siteId: '1',
  code: 'NORTH',
  name: '北侧能源区',
  parentId: null,
  areaType: 'POWER_ROOM',
}
const child = { ...area, id: '12', code: 'CHILD', parentId: '11' }
const route = {
  id: '21',
  siteId: '1',
  linkCode: 'G4_UP',
  routeId: '8',
  routeCode: 'G4',
  name: '京港澳高速',
  directionCode: 'UP',
  directionLabel: null,
  areaId: '11',
  chainageM: 0,
  accessType: 'DIRECT',
  isPrimary: true,
}
const site = { id: '1', name: '测试站', assetStatus: 'ACTIVE', routes: [route] }
const highway = { id: '8', routeCode: 'G4', name: '京港澳高速', status: 'ACTIVE' }
const body = relationPayload('link', false, relationForm('link', route))
assert.equal(body.chainageM, '0')
assert.ok(!('linkCode' in body))
assert.equal(
  relationPayload('link', false, { ...relationForm('link', route), chainageM: '' }).chainageM,
  null,
)
assert.equal(
  relationPayload('link', false, { ...relationForm('link', route), chainageM: '23456.125' })
    .chainageM,
  '23456.125',
)
for (const value of ['-1', 'NaN', 'Infinity', 'K23+456', '0.0001', '1000000000'])
  assert.throws(() =>
    relationPayload('link', false, { ...relationForm('link', route), chainageM: value }),
  )
const areaEdit = relationPayload('area', false, {
  ...relationForm('area', area),
  code: 'FORGED',
  siteId: '2',
})
assert.ok(!('code' in areaEdit) && !('siteId' in areaEdit))
assert.equal(areaEdit.parentId, null)
assert.deepEqual(areaParents([area, child], '11'), [])
assert.deepEqual(
  areaParents([area, child], '12').map((a) => a.id),
  ['11'],
)
assert.deepEqual(areaParents([{ ...area, parentId: '12' }, child]), [])

const pending = []
const methods = [
  'allAssetSites',
  'assetHighways',
  'getAssetSite',
  'listAssetAreas',
  'saveArea',
  'saveRouteLink',
]
const auth = reactive({
  scopeKey: 'one',
  permissions: ['site:read', 'asset:manage'],
  can: (code) => auth.permissions.includes(code),
})
let resets = 0
globalThis.__relationAuth = auth
globalThis.__relationMap = { reset: () => resets++ }
globalThis.__relationApi = Object.fromEntries(
  methods.map((name) => [
    name,
    (...args) => new Promise((resolve, reject) => pending.push({ name, args, resolve, reject })),
  ]),
)
const url = (s) => `data:text/javascript;base64,${Buffer.from(s).toString('base64')}`
const authUrl = url('export const useAuthStore=()=>globalThis.__relationAuth'),
  mapUrl = url('export const useSitesStore=()=>globalThis.__relationMap')
const apiUrl = url(
  methods
    .map((name) => `export const ${name}=(...args)=>globalThis.__relationApi.${name}(...args)`)
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
const last = (name) => {
  const r = pending.filter((p) => p.name === name).at(-1)
  assert.ok(r, name)
  return r
}
const flush = async () => {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
const { useSiteRelations } = await import(
  url(
    compile(
      readFileSync(new URL('../src/composables/useSiteRelations.ts', import.meta.url), 'utf8'),
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
    state = useSiteRelations('1')
    return () => h('div')
  },
})
async function read(value = site, list = [area, child]) {
  last('getAssetSite').resolve({ data: value })
  last('listAssetAreas').resolve({ data: list })
  await flush()
}
async function boot() {
  last('allAssetSites').resolve([site, { ...site, id: '2', routes: [] }])
  last('assetHighways').resolve([highway])
  await flush()
  await read()
}
app.mount({})
try {
  const oldSites = last('allAssetSites'),
    oldRoutes = last('assetHighways')
  auth.scopeKey = 'two'
  oldSites.resolve([{ ...site, name: '旧身份' }])
  oldRoutes.resolve([highway])
  await flush()
  assert.equal(state.sites.value.length, 0)
  await boot()
  assert.equal(state.loaded.value, true)
  await state.open('area')
  const saving = state.save({
    code: 'NEW',
    name: '新增配电房',
    areaType: 'POWER_ROOM',
    parentId: null,
  })
  last('saveArea').reject(new Error('编码冲突'))
  await saving
  assert.ok(state.editor.value)
  assert.match(state.error.value, /编码冲突/)
  assert.equal(resets, 0)
  state.cancel()
  const opening = state.open('link', route)
  await read()
  await opening
  const saveLink = state.save(body)
  assert.deepEqual(last('saveRouteLink').args, ['1', '21', body])
  last('saveRouteLink').resolve({ data: route })
  await flush()
  await read()
  await saveLink
  assert.equal(resets, 1)
  assert.equal(state.editor.value, undefined)
  assert.match(state.message.value, /已保存/)
  await state.open('area')
  const oldSaveTask = state.save({ name: '旧保存' }),
    oldSave = last('saveArea')
  auth.scopeKey = 'three'
  oldSave.resolve({ data: area })
  await oldSaveTask
  assert.equal(state.site.value, undefined)
  assert.equal(state.message.value, '')
  assert.equal(resets, 1)
  await boot()
  // 快速切站，旧站区域和主方向迟到也不覆盖新站。
  const first = state.loadSite(),
    oldDetail = last('getAssetSite'),
    oldAreas = last('listAssetAreas')
  state.siteId.value = '2'
  const second = state.loadSite()
  await read({ ...site, id: '2', routes: [] }, [])
  await second
  oldDetail.resolve({ data: site })
  oldAreas.resolve({ data: [area] })
  await first
  assert.equal(state.site.value.id, '2')
  assert.equal(state.areas.value.length, 0)
  const reload = state.initialize()
  last('allAssetSites').resolve([site, { ...site, id: '2', routes: [] }])
  last('assetHighways').resolve([highway])
  await flush()
  assert.deepEqual(last('getAssetSite').args, ['2'])
  await read({ ...site, id: '2', routes: [] }, [])
  await reload
  // 已保存但重读失败，需要提示保存完成，不能鼓励重复新增。
  await state.open('link')
  const savedButReadFailed = state.save({ ...body, linkCode: 'NEW_LINK' })
  last('saveRouteLink').resolve({ data: { ...route, siteId: '2' } })
  await flush()
  last('getAssetSite').reject(new Error('离线'))
  last('listAssetAreas').resolve({ data: [] })
  await savedButReadFailed
  assert.equal(state.loaded.value, false)
  assert.match(state.error.value, /保存已成功/)
  auth.permissions = ['site:read']
  await boot()
  const count = pending.length
  await state.open('area')
  await state.save({ name: '越权' })
  assert.equal(state.editable.value, false)
  assert.equal(pending.length, count)
  // 撤销读取权同步清空；卸载后的目录响应也不能安装。
  auth.permissions = []
  assert.equal(state.site.value, undefined)
  assert.equal(state.sites.value.length, 0)
  auth.permissions = ['site:read']
  const lateSites = last('allAssetSites'),
    lateRoutes = last('assetHighways')
  app.unmount()
  lateSites.resolve([site])
  lateRoutes.resolve([highway])
  await flush()
  assert.equal(state.sites.value.length, 0)
} finally {
  app.unmount()
}

// HTTP适配器实际调用：关联ID不能误当路线ID，编辑使用PUT。
const calls = []
globalThis.__relationRequest = async (...args) => {
  calls.push(args)
  return { data: {} }
}
const httpUrl = url('export const request=(...args)=>globalThis.__relationRequest(...args)')
const service = compile(
  readFileSync(new URL('../src/services/assetsService.ts', import.meta.url), 'utf8'),
).replace(/from (['"]).\/http\1/g, `from ${JSON.stringify(httpUrl)}`)
const api = await import(url(service))
await api.saveArea('1', undefined, areaEdit)
await api.saveRouteLink('1', '21', body)
assert.equal(calls[0][0], '/api/v1/sites/1/areas')
assert.equal(calls[0][1].method, 'POST')
assert.equal(calls[1][0], '/api/v1/sites/1/routes/21')
assert.equal(calls[1][1].method, 'PUT')

const formsUrl = url(
  compile(readFileSync(new URL('../src/utils/relationForms.ts', import.meta.url), 'utf8')),
)
async function component(path, replacements = []) {
  const { descriptor } = parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
  let code = compile(compileScript(descriptor, { id: path, inlineTemplate: true }).content)
  for (const [pattern, value] of replacements)
    code = code.replace(pattern, `from ${JSON.stringify(value)}`)
  return (await import(url(code))).default
}
const Form = await component('../src/components/assets/RelationForm.vue', [
  [/from (['"])@\/utils\/relationForms\1/g, formsUrl],
])
const markup = await renderToString(
  createSSRApp(Form, {
    kind: 'link',
    record: route,
    areas: [area],
    highways: [highway],
    busy: false,
  }),
)
assert.ok(markup.includes('value="0"') && markup.includes('关联编码：G4_UP（固定）'))
const areaMarkup = await renderToString(
  createSSRApp(Form, {
    kind: 'area',
    record: area,
    areas: [area, child],
    highways: [],
    busy: false,
  }),
)
assert.ok(
  !areaMarkup.includes('<option value="12"') &&
    !areaMarkup.includes('placeholder="例如 NORTH_POWER"'),
)
globalThis.__relationRender = Object.fromEntries(
  Object.keys(state).map((k) => [k, typeof state[k] === 'function' ? () => {} : ref(undefined)]),
)
Object.assign(globalThis.__relationRender, {
  sites: ref([site]),
  siteId: ref('1'),
  site: ref(site),
  areas: ref([area]),
  loaded: ref(true),
  editable: ref(false),
  busy: ref(false),
})
const routeUrl = url('export const useRoute=()=>({query:{}})'),
  stateUrl = url('export const useSiteRelations=()=>globalThis.__relationRender')
const View = await component('../src/views/SiteRelationsView.vue', [
  [/from (['"])vue-router\1/g, routeUrl],
  [/from (['"])@\/composables\/useSiteRelations\1/g, stateUrl],
  [/from (['"])@\/components\/assets\/RelationForm.vue\1/g, url('export default {}')],
])
const view = createSSRApp(View)
view.component('RouterLink', { template: '<a><slot /></a>' })
const readonly = await renderToString(view)
assert.ok(
  readonly.includes('当前账号只读') &&
    readonly.includes('主关联') &&
    readonly.includes('北侧能源区'),
)
assert.ok(!readonly.includes('＋ 新增区域') && !readonly.includes('＋ 新增关联'))
delete globalThis.__relationAuth
delete globalThis.__relationMap
delete globalThis.__relationApi
delete globalThis.__relationRequest
delete globalThis.__relationRender
console.log(
  'Passed: area parent choices/whitelists, chainage null-zero-decimals, real save/retry/read-only flows, account/site/save/unmount stale isolation, refresh keeps selected site, HTTP IDs and real Vue form/page rendering.',
)
