/** 场景配置回归：运行真实composable与编译后的Vue页面，校验新站流程和迟到响应隔离。 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createRenderer, createSSRApp, h, nextTick, reactive, ref } from 'vue'
import { renderToString } from '@vue/server-renderer'
const pending = []
const defer = (name, args) =>
  new Promise((resolve, reject) => pending.push({ name, args, resolve, reject }))
const methods = [
  'getSceneTemplates',
  'getTemplateObjects',
  'getSceneVersions',
  'getScene',
  'createScene',
  'cloneScene',
  'saveObjects',
  'saveBindings',
  'publishScene',
]
const auth = reactive({
  scopeKey: 'first',
  user: { permissions: ['site:read', 'device:read', 'twin:read', 'twin:publish', 'monitor:read'] },
  can: (code) => auth.user.permissions.includes(code),
})
globalThis.__sceneConfigAuth = auth
globalThis.__sceneConfigApi = Object.fromEntries(
  [...methods, 'allAssetSites', 'listAssetDevices', 'getPoints'].map((name) => [
    name,
    (...args) => defer(name, args),
  ]),
)
const url = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const authUrl = url('export const useAuthStore=()=>globalThis.__sceneConfigAuth')
const exportsUrl = (names) =>
  url(
    names
      .map((name) => `export const ${name}=(...args)=>globalThis.__sceneConfigApi.${name}(...args)`)
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
      /from (['"])@\/services\/twinService\1/g,
      `from ${JSON.stringify(exportsUrl(methods))}`,
    )
    .replace(
      /from (['"])@\/services\/assetsService\1/g,
      `from ${JSON.stringify(exportsUrl(['allAssetSites', 'listAssetDevices']))}`,
    )
    .replace(
      /from (['"])@\/services\/monitoringService\1/g,
      `from ${JSON.stringify(exportsUrl(['getPoints']))}`,
    )
}
const { useSceneConfiguration } = await import(
  url(
    compile(
      readFileSync(new URL('../src/composables/useSceneConfiguration.ts', import.meta.url), 'utf8'),
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
const flush = async () => {
  for (let i = 0; i < 12; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
const last = (name) => {
  const value = pending.filter((p) => p.name === name).at(-1)
  assert.ok(value, name)
  return value
}
const site = {
  id: '1',
  name: '新建服务区',
  siteType: 'SERVICE',
  scaleLevel: 'L',
  assetStatus: 'ACTIVE',
  isDemo: true,
}
const template = {
  id: '7',
  code: 'SERVICE_L',
  siteType: 'SERVICE',
  scaleLevel: 'L',
  version: 2,
  status: 'PUBLISHED',
  modelUrl: '/models/service_large.glb',
}
const draft = {
  id: '100',
  siteId: '1',
  templateId: '7',
  version: 1,
  status: 'DRAFT',
  isDemo: true,
  modelUrl: template.modelUrl,
  publishedAt: null,
  objects: [
    {
      id: '1001',
      objectKey: 'storage_north_01',
      name: '北侧储能柜',
      deviceId: null,
      device: null,
      parentId: null,
      areaId: null,
      isDemo: true,
      transform: null,
    },
  ],
  bindings: [],
}
const device = {
  id: '50',
  siteId: '1',
  name: '储能柜',
  code: 'ESS',
  systemType: 'ESS',
  assetStatus: 'ACTIVE',
  isDemo: true,
}
const point = { id: '500', code: 'active_power', name: '有功功率', unit: 'kW', enabled: true }
let state
const app = renderer.createApp({
  setup() {
    state = useSceneConfiguration()
    return () => h('div')
  },
})
async function directories() {
  last('allAssetSites').resolve([site])
  last('getSceneTemplates').resolve({
    data: [
      template,
      { ...template, id: '8', scaleLevel: 'M' },
      { ...template, id: '9', status: 'DRAFT' },
    ],
  })
  await flush()
  last('getSceneVersions').resolve([])
  last('listAssetDevices').resolve({ data: [device], meta: { hasNext: false } })
  await flush()
}
async function install(value) {
  last('getTemplateObjects').resolve({
    data: { templateId: '7', objectKeys: ['storage_north_01'] },
  })
  await flush()
  if (value.objects.some((o) => o.deviceId)) {
    last('getPoints').resolve({ data: [point] })
    await flush()
  }
}
app.mount({})
try {
  // 账号切换：旧目录与旧保存响应都不能恢复此前身份下的对象。
  const oldSites = last('allAssetSites'),
    oldTemplates = last('getSceneTemplates')
  auth.scopeKey = 'second'
  oldSites.resolve([{ ...site, name: '旧账号站点' }])
  oldTemplates.resolve({ data: [template] })
  await flush()
  assert.equal(state.sites.value.length, 0)
  await directories()
  assert.equal(state.scene.value, undefined)
  assert.equal(state.availableTemplates.value.length, 1)
  const creating = state.create()
  last('getTemplateObjects').resolve({ data: { objectKeys: ['storage_north_01'] } })
  await flush()
  assert.deepEqual(last('createScene').args, [
    '1',
    '7',
    [{ objectKey: 'storage_north_01', name: 'storage_north_01', deviceId: null }],
  ])
  last('createScene').resolve({ data: draft })
  await flush()
  await install(draft)
  last('getSceneVersions').resolve([draft])
  await creating
  assert.equal(state.scene.value.id, '100')
  assert.equal(state.writable.value, true)
  state.objectRows.value[0].deviceId = '50'
  state.objectsDirty.value = true
  const count = pending.length
  await state.publish()
  assert.equal(pending.length, count)
  const assigned = { ...draft, objects: [{ ...draft.objects[0], deviceId: '50', device }] }
  const saving = state.saveObjects()
  last('saveObjects').resolve({ data: assigned })
  await flush()
  await install(assigned)
  await saving
  assert.equal(state.objectsDirty.value, false)
  state.newObjectId.value = '1001'
  state.addBinding()
  assert.equal(state.bindingRows.value[0].pointId, '500')
  assert.equal(state.bindingsDirty.value, true)
  const bound = {
    ...assigned,
    bindings: [
      {
        id: '9',
        objectId: '1001',
        deviceId: '50',
        pointId: '500',
        propertyCode: 'active_power',
        mappingConfig: null,
      },
    ],
  }
  const savingBindings = state.saveBindings()
  last('saveBindings').resolve({ data: bound })
  await flush()
  await install(bound)
  await savingBindings
  const publishing = state.publish()
  const published = { ...bound, status: 'PUBLISHED' }
  last('publishScene').resolve({ data: published })
  await flush()
  await install(published)
  last('getSceneVersions').resolve([published])
  await publishing
  assert.equal(state.scene.value.status, 'PUBLISHED')
  assert.equal(state.writable.value, false)
  // 草稿编辑失败保留本地内容，服务端业务错误有明确提示。
  state.scene.value = assigned
  state.objectRows.value[0].name = '未保存名称'
  state.objectsDirty.value = true
  const failure = state.saveObjects()
  last('saveObjects').reject(new Error('对象已有测点绑定'))
  await failure
  assert.equal(state.objectsDirty.value, true)
  assert.match(state.error.value, /测点绑定/)
  const staleSaving = state.saveObjects()
  const oldSave = last('saveObjects')
  auth.scopeKey = 'third'
  oldSave.resolve({ data: assigned })
  await staleSaving
  assert.equal(state.scene.value, undefined)
  assert.equal(state.message.value, '')
  await directories()
  // 快速切站：旧版本目录晚到，不改变新的空站状态。
  state.siteId.value = '1'
  const first = state.loadSite()
  const oldVersions = last('getSceneVersions'),
    oldDevices = last('listAssetDevices')
  state.siteId.value = '2'
  const second = state.loadSite()
  last('getSceneVersions').resolve([])
  last('listAssetDevices').resolve({ data: [], meta: {} })
  await second
  oldVersions.resolve([assigned])
  oldDevices.resolve({ data: [device], meta: {} })
  await first
  assert.equal(state.siteId.value, '2')
  assert.equal(state.scene.value, undefined)
  // 撤销读取权同步清空，之后按钮动作不发出写请求。
  auth.user.permissions = ['site:read']
  const before = pending.length
  await state.create()
  await state.saveObjects()
  await state.publish()
  assert.equal(state.sites.value.length, 0)
  assert.equal(pending.length, before)
} finally {
  app.unmount()
}

// 编译真实页面做服务端布局/分支验收；不声称完成浏览器视觉检查。
const noop = () => {}
const viewState = Object.fromEntries(
  Object.keys(state).map((k) => [k, typeof state[k] === 'function' ? noop : ref(undefined)]),
)
Object.assign(viewState, {
  sites: ref([site]),
  site: ref(site),
  siteId: ref('1'),
  versions: ref([draft]),
  scene: ref(draft),
  devices: ref([device]),
  objectRows: ref([{ objectKey: 'storage_north_01', name: '北侧储能柜', deviceId: null }]),
  bindingRows: ref([]),
  keys: ref([]),
  availableTemplates: ref([template]),
  writable: ref(true),
  pointsFor: () => [],
  busy: ref(false),
})
globalThis.__sceneConfigRender = viewState
auth.user.permissions = ['site:read', 'device:read', 'twin:read', 'twin:publish', 'monitor:read']
const { descriptor } = parse(
  readFileSync(new URL('../src/views/ScenesView.vue', import.meta.url), 'utf8'),
)
const script = compileScript(descriptor, { id: 'scene-config-test', inlineTemplate: true })
const routeUrl = url('export const useRoute=()=>({query:{}})')
const stateUrl = url('export const useSceneConfiguration=()=>globalThis.__sceneConfigRender')
const View = (
  await import(
    url(
      compile(script.content)
        .replace(/from (['"])vue-router\1/g, `from ${JSON.stringify(routeUrl)}`)
        .replace(
          /from (['"])@\/composables\/useSceneConfiguration\1/g,
          `from ${JSON.stringify(stateUrl)}`,
        ),
    )
  )
).default
const render = async () => {
  const app = createSSRApp(View)
  app.component('RouterLink', { props: ['to'], template: '<a><slot /></a>' })
  return renderToString(app)
}
const html = await render()
assert.ok(
  html.includes('从模板创建草稿') &&
    html.includes('保存对象关系') &&
    html.includes('发布此草稿') &&
    html.includes('北侧储能柜'),
)
auth.user.permissions = ['site:read', 'twin:read']
viewState.writable.value = false
const readonly = await render()
assert.ok(
  !readonly.includes('从模板创建草稿') &&
    !readonly.includes('发布此草稿') &&
    readonly.includes('当前账号仅查看已发布版本'),
)
delete globalThis.__sceneConfigAuth
delete globalThis.__sceneConfigApi
delete globalThis.__sceneConfigRender
console.log(
  'Passed: first scene create/object/point/publish flow, unsaved guards, API errors, account/site/save stale response isolation, revoked rights, real Vue configuration page read-only rendering.',
)
